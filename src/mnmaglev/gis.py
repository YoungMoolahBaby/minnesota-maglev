"""GIS phase, slices 1-3: a real alignment for a line from elevation, land cover, flood zones,
built-up land and freeways.

1. Data (cached in data/raw/gis, gitignored): USGS 3DEP elevation (ImageServer exportImage) and
   NLCD 2021 land cover (MRLC WCS, 30 m class codes), both in EPSG:5070 (CONUS Albers, metres),
   on a 210 m grid = exactly 7 x 7 land-cover pixels per cell, so every cell gets class fractions.
   FEMA NFHL flood zones (MapServer layer 28, queried per 25 km tile): 1% and 0.2% annual-chance
   zones and regulatory floodways, rasterised at 30 m and averaged per cell, plus whether FEMA has
   digital maps for the tile at all. NLCD 2021 impervious surface and its descriptor (roads by
   class, buildings): how built-up each cell is with roads left out, and where interstates run.
2. Cost surface: what a km of guideway through each cell costs, priced with the model's own
   nominal parameters: structure (rural elevated / urban viaduct / bridge over water), right-of-way
   land by cover class and zone, wetland mitigation, and a terrain penalty for steep ground;
   floodways are priced as bridge, other flood zones get the floodplain adder; built-up cells
   (ramp on non-road impervious %) as urban viaduct; in interstate right-of-way the land costs
   land.corridor.price_factor x the land around it and building beside traffic gets an adder.
3. Route: least-cost path between the line's stations (skimage MCP), then simplified and given
   circular curves no tighter than the minimum radius (cruise speed in the country, urban speed near
   stations); vertices too sharp for a curve are dropped and the line re-simplified.
4. Measure along the final alignment: length, detour, land shares, wetland, water crossings
   and floodways (bridges), floodplain share, built-up share, km beside freeways, urban km, grades. Written to network/alignments/<line>.geojson and network/measured/<line>.yaml.

Not yet (later slices): SSURGO peat, parcels and single buildings, rail corridors,
public and tribal land, and the at-grade / elevated choice per cell.
Requires the optional extra: uv sync --extra gis
"""

from __future__ import annotations

import math
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from . import ROOT
from .geo import min_curve_radius_m, haversine_km
from .network import Line

CELL = 210.0  # m, 7 x 30 m NLCD pixels
NLCD_PX = 30.0
RAW = ROOT / "data" / "raw" / "gis"
DEM_URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
           "?bbox={x0},{y0},{x1},{y1}&bboxSR=5070&imageSR=5070&size={w},{h}&format=tiff&pixelType=F32"
           "&interpolation=RSP_BilinearInterpolation&f=image")
MRLC_URL = ("https://www.mrlc.gov/geoserver/mrlc_download/{cov}/wcs?service=WCS"
            "&version=2.0.1&request=GetCoverage&coverageid=mrlc_download__{cov}"
            "&subset=X({x0},{x1})&subset=Y({y0},{y1})&format=image/geotiff")
NLCD_URL = MRLC_URL.replace("{cov}", "NLCD_2021_Land_Cover_L48")
# NLCD 2021 impervious descriptor: 20 primary road (interstates, freeways), 21 secondary road,
# 22 tertiary road, 24 non-road non-energy impervious (buildings, parking), ... (2018 NavStreets roads)
HIGHWAY_CODES = (20,)
MAJOR_ROAD_CODES = (20, 21)

# NLCD class -> our groups
GROUPS = {
    "water": (11, 12),
    "suburban": (21, 22),          # developed open space, low intensity
    "urban": (23, 24),             # developed medium, high intensity
    "forest": (41, 42, 43),
    "open": (31, 52, 71, 81, 82),  # barren, shrub, grassland, pasture, crops
    "wetland": (90, 95),
}


@dataclass
class Grid:
    x0: float
    y0: float  # lower-left, EPSG:5070
    nx: int
    ny: int

    @property
    def x1(self):
        return self.x0 + self.nx * CELL

    @property
    def y1(self):
        return self.y0 + self.ny * CELL

    def rc(self, x, y):
        return int((self.y1 - y) // CELL), int((x - self.x0) // CELL)

    def xy(self, r, c):
        return self.x0 + (c + 0.5) * CELL, self.y1 - (r + 0.5) * CELL


def _to_5070():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)


def _to_4326():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)


def grid_for(line: Line, buffer_km: float = 30.0) -> Grid:
    t = _to_5070()
    xs, ys = zip(*(t.transform(p.lon, p.lat) for p in line.points))
    b = buffer_km * 1000
    x0 = math.floor((min(xs) - b) / CELL) * CELL
    y0 = math.floor((min(ys) - b) / CELL) * CELL
    nx = math.ceil((max(xs) + b - x0) / CELL)
    ny = math.ceil((max(ys) + b - y0) / CELL)
    return Grid(x0, y0, nx, ny)


def _get(url: str, path: Path) -> Path:
    if not path.exists() or path.stat().st_size < 1000:
        req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev GIS"})
        with urllib.request.urlopen(req, timeout=600) as r:
            path.write_bytes(r.read())
        time.sleep(0.5)
    return path


def fetch_dem(g: Grid, folder: Path) -> np.ndarray:
    import rasterio
    tile = 2000  # cells per request side
    dem = np.full((g.ny, g.nx), np.nan, dtype=np.float32)
    for r0 in range(0, g.ny, tile):
        for c0 in range(0, g.nx, tile):
            h, w = min(tile, g.ny - r0), min(tile, g.nx - c0)
            x0 = g.x0 + c0 * CELL
            y1 = g.y1 - r0 * CELL
            p = _get(DEM_URL.format(x0=x0, y0=y1 - h * CELL, x1=x0 + w * CELL, y1=y1, w=w, h=h),
                     folder / f"dem_{r0}_{c0}.tif")
            with rasterio.open(p) as src:
                dem[r0:r0 + h, c0:c0 + w] = src.read(1)[:h, :w]
    dem[dem < -1000] = np.nan
    return dem


def _mrlc_blocks(g: Grid, folder: Path, cov: str, prefix: str):
    """Yield (r0, c0, blocks) per tile of a 30 m MRLC coverage; blocks[i, 7, j, 7] = the 7 x 7
    pixels of cell (r0 + i, c0 + j)."""
    import rasterio
    tile = 300  # cells per request side (2100 x 2100 NLCD pixels)
    for r0 in range(0, g.ny, tile):
        for c0 in range(0, g.nx, tile):
            h, w = min(tile, g.ny - r0), min(tile, g.nx - c0)
            x0 = g.x0 + c0 * CELL
            y1 = g.y1 - r0 * CELL
            p = _get(MRLC_URL.format(cov=cov, x0=x0, y0=y1 - h * CELL, x1=x0 + w * CELL, y1=y1),
                     folder / f"{prefix}_{r0}_{c0}.tif")
            with rasterio.open(p) as src:
                a = src.read(1)
                # align: the WCS may pad by a pixel; cut from the tile's top-left corner
                col = int(round((x0 - src.bounds.left) / NLCD_PX))
                row = int(round((src.bounds.top - y1) / NLCD_PX))
                a = a[row:row + h * 7, col:col + w * 7]
            hh, ww = a.shape[0] // 7, a.shape[1] // 7
            yield r0, c0, a[: hh * 7, : ww * 7].reshape(hh, 7, ww, 7)


def fetch_landcover_fractions(g: Grid, folder: Path) -> dict[str, np.ndarray]:
    """Fraction of each group per 210 m cell from 30 m NLCD (7 x 7 blocks)."""
    frac = {k: np.zeros((g.ny, g.nx), dtype=np.float32) for k in GROUPS}
    for r0, c0, blocks in _mrlc_blocks(g, folder, "NLCD_2021_Land_Cover_L48", "nlcd"):
        hh, ww = blocks.shape[0], blocks.shape[2]
        for k, codes in GROUPS.items():
            frac[k][r0:r0 + hh, c0:c0 + ww] = np.isin(blocks, codes).mean(axis=(1, 3))
    return frac


def fetch_development(g: Grid, folder: Path) -> dict[str, np.ndarray]:
    """Per 210 m cell from NLCD 2021 impervious surface (% per 30 m pixel) and its descriptor:
    imp_nonroad = mean impervious % not counting interstates / highways (how built-up the
    surroundings are), highway = share of the cell's pixels on a primary road (interstate,
    freeway), corridor = 1 where a freeway runs through the cell (>= 7 pixels, one cell length)."""
    imp = np.zeros((g.ny, g.nx), dtype=np.float32)
    hwy = np.zeros((g.ny, g.nx), dtype=np.float32)
    tiles = {}
    for r0, c0, b in _mrlc_blocks(g, folder, "NLCD_2021_Impervious_L48", "imp"):
        tiles[(r0, c0)] = b.astype(np.float32)
    for r0, c0, d in _mrlc_blocks(g, folder, "NLCD_2021_Impervious_descriptor_L48", "impd"):
        b = tiles.pop((r0, c0))
        hh, ww = min(b.shape[0], d.shape[0]), min(b.shape[2], d.shape[2])
        b, d = b[:hh, :, :ww, :], d[:hh, :, :ww, :]
        b = np.where(b > 100, 0, b)  # nodata
        imp[r0:r0 + hh, c0:c0 + ww] = np.where(np.isin(d, MAJOR_ROAD_CODES), 0, b).mean(axis=(1, 3))
        hwy[r0:r0 + hh, c0:c0 + ww] = np.isin(d, HIGHWAY_CODES).mean(axis=(1, 3))
    return {"imp_nonroad": imp, "highway": hwy, "corridor": (hwy * 49 >= 7).astype(np.float32)}


def built_up(dev: dict, frac: dict, P: dict) -> np.ndarray:
    """Share of each cell to price as built-up (urban viaduct): a ramp on non-road impervious %."""
    lo, hi = P["land.developed.impervious_low"], P["land.developed.impervious_high"]
    return np.maximum(frac["urban"], np.clip((dev["imp_nonroad"] - lo) / (hi - lo), 0.0, 1.0))


def zone_of_lat(lat: float) -> str:
    return "north" if lat >= 46.0 else ("central" if lat >= 44.6 else "south")


def cost_surface(g: Grid, frac: dict, dem: np.ndarray, P: dict, flood: dict | None = None,
                 dev: dict | None = None) -> np.ndarray:
    """MUSD per km of route through each cell (nominal parameters)."""
    gw = "costs.guideway."
    t = _to_4326()
    rows = np.arange(g.ny)
    lat_row = np.array([t.transform(g.x0 + g.nx * CELL / 2, g.y1 - (r + 0.5) * CELL)[1] for r in rows])
    crop = np.where(lat_row >= 44.6, P["land.price_per_acre.cropland_central"],
                    P["land.price_per_acre.cropland_south"])[:, None]
    forest = P["land.price_per_acre.forest_north"]
    acres_per_km = P["land.row_width.elevated"] * 1000 / 4046.86
    # bridge over open water and over the regulatory floodway (piers there are restricted)
    span = np.maximum(frac["water"], flood["floodway"]) if flood else frac["water"]
    # built-up (urban viaduct): dense NLCD classes, and suburbs by how much of them is paved or built
    built = np.minimum(built_up(dev, frac, P) if dev else frac["urban"], 1.0 - span)
    rural = np.clip(1.0 - span - built, 0.0, 1.0)
    # wetland stands in for peat / soft ground until SSURGO: deep piles, the peat adder
    soft = 1.0 + frac["wetland"] * P["costs.adders.peat_soft_ground"]
    # floodplain: piers above the 500-year flood with freeboard, scour protection;
    # beside a freeway: pier crash protection, traffic control while building
    corridor = dev["corridor"] if dev else 0.0
    adders = (1.0 + (flood["flood"] if flood else 0.0) * P["costs.adders.floodplain"]
              + corridor * P["costs.adders.highway_corridor"])
    structure = (span * P[gw + "bridge_per_m"] * 1000
                 + (built * P[gw + "urban_viaduct"] + rural * P[gw + "elevated"] * soft) * adders)
    # in a freeway's right-of-way the land costs a share of what the land around it would
    land = acres_per_km * P["land.acquisition_multiplier"] * (1.0 - corridor * (1.0 - P["land.corridor.price_factor"])) * (
        frac["suburban"] * P["land.price_per_acre.suburban"] + frac["urban"] * P["land.price_per_acre.urban_core"]
        + frac["forest"] * forest + frac["open"] * crop + frac["wetland"] * P["land.price_per_acre.wetland"])
    wetland = (frac["wetland"] * acres_per_km * P["land.wetlands.impact_fraction_elevated"]
               * P["land.wetlands.replacement_ratio"] * P["land.wetlands.credit_price"])
    gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), CELL)
    slope = np.hypot(gx, gy)
    terrain = P[gw + "elevated"] * 0.5 * np.minimum(slope / P["system.geometry.max_gradient"], 1.0)
    cost = structure + land + wetland + terrain
    return np.where(np.isnan(dem), np.nanmax(cost) * 10, cost).astype(np.float64)


def _fillet_ok(pts: np.ndarray, radii: np.ndarray) -> np.ndarray:
    """For each interior vertex: does a curve of its radius fit between its neighbours?"""
    ok = np.ones(len(pts), dtype=bool)
    for i in range(1, len(pts) - 1):
        a, b = pts[i] - pts[i - 1], pts[i + 1] - pts[i]
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        cosang = np.clip(np.dot(a, b) / (la * lb), -1, 1)
        theta = math.acos(cosang)  # deflection
        tangent = radii[i] * math.tan(theta / 2)
        ok[i] = tangent <= 0.5 * min(la, lb) + 1e-6
    return ok


def _simplify(pts: np.ndarray, tol: float) -> np.ndarray:
    from shapely.geometry import LineString
    return np.array(LineString(pts).simplify(tol, preserve_topology=False).coords)


def smooth(pts: np.ndarray, stations_xy: np.ndarray, P: dict) -> tuple[np.ndarray, dict]:
    """Polyline -> alignment with circular curves >= minimum radius (urban radius near stations)."""
    r_cruise = min_curve_radius_m(P["system.vehicle.cruise_speed"], P["system.geometry.superelevation_max"],
                                  P["system.geometry.unbalanced_lateral"])
    r_urban = min_curve_radius_m(P["system.vehicle.urban_speed"], P["system.geometry.superelevation_max"],
                                 P["system.geometry.unbalanced_lateral"])
    near = 15000.0  # m from a station where trains run at or below urban speed
    tol = 300.0
    for _ in range(40):
        s = _simplify(pts, tol)
        d = np.min(np.linalg.norm(s[:, None, :] - stations_xy[None, :, :], axis=2), axis=1)
        radii = np.where(d < near, r_urban, r_cruise)
        ok = _fillet_ok(s, radii)
        if ok.all():
            break
        tol *= 1.3
    # discretise the curves
    out = [s[0]]
    for i in range(1, len(s) - 1):
        a, b = s[i] - s[i - 1], s[i + 1] - s[i]
        ua, ub = a / np.linalg.norm(a), b / np.linalg.norm(b)
        theta = math.acos(np.clip(np.dot(ua, ub), -1, 1))
        if theta < 1e-4:
            out.append(s[i])
            continue
        T = radii[i] * math.tan(theta / 2)
        p0, p1 = s[i] - ua * T, s[i] + ub * T
        n = max(int(theta / math.radians(1)), 2)
        for k in range(n + 1):  # quadratic Bezier through the corner approximates the arc closely
            u = k / n
            out.append((1 - u) ** 2 * p0 + 2 * (1 - u) * u * s[i] + u ** 2 * p1)
    out.append(s[-1])
    return np.array(out), {"r_cruise_m": r_cruise, "r_urban_m": r_urban, "simplify_tol_m": tol,
                           "all_curves_fit": bool(ok.all())}


def route(line: Line, P: dict, cache: Path | None = None) -> dict:
    """Least-cost, curve-feasible alignment through the line's stations, and its measurements."""
    from skimage.graph import MCP_Geometric

    g = grid_for(line)
    folder = cache or (RAW / line.id)
    folder.mkdir(parents=True, exist_ok=True)
    dem = fetch_dem(g, folder)
    frac = fetch_landcover_fractions(g, folder)
    (folder / "nfhl").mkdir(exist_ok=True)
    flood = fetch_floodplain(g, folder / "nfhl")
    dev = fetch_development(g, folder)
    cost = cost_surface(g, frac, dem, P, flood, dev)
    cell_km = CELL / 1000.0
    to5070 = _to_5070()
    stops = [p for p in line.points if p.is_station]
    st_xy = np.array([to5070.transform(p.lon, p.lat) for p in stops])
    legs = []
    for (a, b), (pa, pb) in zip(zip(st_xy, st_xy[1:]), zip(stops, stops[1:])):
        mcp = MCP_Geometric(cost * cell_km, fully_connected=True)
        start, end = g.rc(*a), g.rc(*b)
        mcp.find_costs([start], [end])
        path = mcp.traceback(end)
        xy = np.array([g.xy(r, c) for r, c in path])
        xy[0], xy[-1] = a, b
        legs.append((pa, pb, xy))
    full = np.vstack([legs[0][2]] + [l[2][1:] for l in legs[1:]])
    align, curve_info = smooth(full, st_xy, P)
    layers = {**frac, **{f"fl_{k}": v for k, v in flood.items()},
              "dev_built": built_up(dev, frac, P), "dev_corridor": dev["corridor"]}
    meas = measure(align, st_xy, stops, g, layers, dem, P["system.geometry.max_gradient"])
    return {"grid": g, "alignment": align, "curves": curve_info, "measured": meas, "stations": stops}


def _sample(align: np.ndarray, step: float = CELL / 2):
    seg = np.diff(align, axis=0)
    lens = np.linalg.norm(seg, axis=1)
    s = np.concatenate([[0], np.cumsum(lens)])
    d = np.arange(0, s[-1], step)
    x = np.interp(d, s, align[:, 0])
    y = np.interp(d, s, align[:, 1])
    return d, x, y


def guideway_profile(z: np.ndarray, step: float, g_max: float) -> np.ndarray:
    """Lowest guideway profile at or above the ground whose grade never exceeds g_max.

    Forward and backward passes (like the speed profile): the guideway may not drop faster than
    g_max going either way, so it rides over ground that falls away too steeply, on taller piers.
    Height above ground (profile - z) shows where that happens.
    """
    p = np.nan_to_num(z, nan=np.nanmean(z)).astype(float).copy()
    dz = g_max * step
    for i in range(1, len(p)):
        p[i] = max(p[i], p[i - 1] - dz)
    for i in range(len(p) - 2, -1, -1):
        p[i] = max(p[i], p[i + 1] - dz)
    return p


def measure(align, st_xy, stops, g: Grid, frac, dem, g_max: float = 0.10, min_piece_km: float = 5.0) -> list[dict]:
    """Pieces of the alignment: station to station, split where the climate zone changes (by latitude).

    Each piece: from / to (a station id, or a waypoint with lat/lon at a zone break), zone, length,
    straight-line km and detour, land shares, urban km at each end, water crossings (bridges),
    ground grades and how tall the guideway must stand to keep grades within g_max.
    """
    d, x, y = _sample(align)
    rr = np.clip(((g.y1 - y) // CELL).astype(int), 0, g.ny - 1)
    cc = np.clip(((x - g.x0) // CELL).astype(int), 0, g.nx - 1)
    f = {k: v[rr, cc] for k, v in frac.items()}
    z = dem[rr, cc]
    lon, lat = _to_4326().transform(x, y)
    lon, lat = np.asarray(lon), np.asarray(lat)
    zone = np.array([zone_of_lat(v) for v in lat])
    st_i = [int(np.argmin(np.hypot(x - sx, y - sy))) for sx, sy in st_xy]
    step = d[1] - d[0]
    min_n = int(min_piece_km * 1000 / step)
    pieces = []
    for k in range(len(stops) - 1):
        a, b = st_i[k], st_i[k + 1]
        cuts = [a] + [i for i in range(a + 1, b) if zone[i] != zone[i - 1]] + [b]
        merged = [cuts[0]]  # drop breaks that would make pieces shorter than min_piece_km
        for c in cuts[1:-1]:
            if c - merged[-1] >= min_n and b - c >= min_n:
                merged.append(c)
        merged.append(b)
        for j, (i0, i1) in enumerate(zip(merged, merged[1:])):
            start = stops[k].id if j == 0 else {"id": f"wp_{k}_{j}", "lat": round(float(lat[i0]), 5),
                                                "lon": round(float(lon[i0]), 5)}
            end = stops[k + 1].id if i1 == b else {"id": f"wp_{k}_{j + 1}", "lat": round(float(lat[i1]), 5),
                                                   "lon": round(float(lon[i1]), 5)}
            pieces.append(_piece(slice(i0, i1), start, end, f, z, lat, lon, zone, step, g_max))
    return pieces


def _piece(m, start, end, f, z, lat, lon, zone, step, g_max) -> dict:
    n = m.stop - m.start
    km = n * step / 1000
    bridges, run = [], 0
    span = f["water"][m] > 0.5
    if "fl_floodway" in f:
        span = span | (f["fl_floodway"][m] > 0.5)
    for w in span:
        if w:
            run += 1
        elif run:
            bridges.append(run * step)
            run = 0
    if run:
        bridges.append(run * step)
    zz = z[m]
    win = max(int(1000 / step), 1)  # grade over 1 km
    grades = np.abs(zz[win:] - zz[:-win]) / (win * step) if len(zz) > win else np.array([0.0])
    height = guideway_profile(zz, step, g_max) - zz
    crow = haversine_km(lat[m.start], lon[m.start], lat[m.stop - 1], lon[m.stop - 1])
    urban = f["urban"][m] > 0.5
    half = n // 2
    dev = {}
    if "dev_built" in f:
        rest = ~urban & ~span  # the km the model prices by structure mix (not dense urban, not bridge)
        dev = {"built_up_share": round(float(f["dev_built"][m][rest].mean()), 3) if rest.any() else 0.0,
               "highway_corridor_share": round(float(f["dev_corridor"][m].mean()), 3),
               "highway_corridor_km": round(float(f["dev_corridor"][m].sum() * step / 1000), 1)}
    zones, counts = np.unique(zone[m], return_counts=True)
    return {
        "from": start, "to": end, "zone": str(zones[np.argmax(counts)]),
        "length_km": round(float(km), 1), "crow_km": round(float(crow), 1),
        "detour": round(float(km / crow), 3) if crow > 0 else 1.0,
        "land_shares": {k: round(float(f[k][m].mean()), 3)
                        for k in ("suburban", "urban", "forest", "open", "wetland", "water")},
        **({"floodplain_share": round(float(f["fl_flood"][m].mean()), 3),
            "floodplain_1pct_share": round(float(f["fl_sfha"][m].mean()), 3),
            "floodway_km": round(float((f["fl_floodway"][m] > 0.5).sum() * step / 1000), 2),
            "flood_map_coverage": round(float(f["fl_covered"][m].mean()), 3)} if "fl_flood" in f else {}),
        **dev,
        "urban_km": round(float(urban.sum() * step / 1000), 1),
        "urban_start_km": round(float(urban[:half].sum() * step / 1000), 1),
        "urban_end_km": round(float(urban[half:].sum() * step / 1000), 1),
        "bridges_m": [round(b) for b in bridges if b >= 100],
        "max_ground_grade_1km": round(float(np.nanmax(grades)), 4),
        "elev_range_m": [round(float(np.nanmin(zz))), round(float(np.nanmax(zz)))],
        "guideway_max_height_m": round(float(np.nanmax(height)), 1),
        "km_over_25m_high": round(float((height > 25).sum() * step / 1000), 2),
    }


def write_outputs(line: Line, res: dict) -> tuple[Path, Path]:
    import json
    t = _to_4326()
    coords = [list(t.transform(px, py)) for px, py in res["alignment"]]
    gj = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"line": line.id, **res["curves"]},
        "geometry": {"type": "LineString", "coordinates": [[round(a, 6), round(b, 6)] for a, b in coords]}}]}
    a_dir = ROOT / "network" / "alignments"
    m_dir = ROOT / "network" / "measured"
    a_dir.mkdir(parents=True, exist_ok=True)
    m_dir.mkdir(parents=True, exist_ok=True)
    gpath = a_dir / f"{line.id}.geojson"
    gpath.write_text(json.dumps(gj), encoding="utf-8")
    mpath = m_dir / f"{line.id}.yaml"
    header = ("# Measured along the GIS alignment (network/alignments/%s.geojson) by `mnmaglev gis %s`:\n"
              "# USGS 3DEP elevation + NLCD 2021 land cover on a 210 m grid, FEMA NFHL flood zones\n"
              "# (floodplain_share = 1%% + 0.2%% annual chance; floodway runs counted as bridge;\n"
              "# flood_map_coverage = share of the piece where FEMA has digital maps), NLCD 2021\n"
              "# impervious surface + descriptor (built_up_share = share of the piece's non-urban,\n"
              "# non-bridge km priced as built-up viaduct; highway_corridor = beside a freeway).\n"
              "# Not yet: peat, parcels, rail corridors. Land shares: NLCD groups (water, suburban = developed\n"
              "# open/low, urban = developed medium/high, forest, open = crops/pasture/grass/shrub/barren,\n"
              "# wetland).\n" % (line.id, line.id))
    mpath.write_text(header + yaml.safe_dump({"line": line.id, "curves": res["curves"], "pieces": res["measured"]},
                                             sort_keys=False), encoding="utf-8")
    return gpath, mpath


# --- FEMA National Flood Hazard Layer (slice 2) -------------------------------------------------

NFHL_QUERY = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
FLOOD_WHERE = "SFHA_TF='T' OR ZONE_SUBTY LIKE '0.2 PCT%' OR ZONE_SUBTY LIKE '%FLOODWAY%'"


def _get_json(params: dict, path: Path, tries: int = 10) -> dict:
    import json
    import urllib.parse

    if path.exists() and path.stat().st_size > 20:
        return json.loads(path.read_text(encoding="utf-8"))
    url = NFHL_QUERY + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev GIS"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            if "error" in data:
                raise RuntimeError(data["error"])
            path.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(1.0)
            return data
        except Exception:  # the FEMA server drops requests now and then
            if k == tries - 1:
                raise
            time.sleep(min(10 * (k + 1), 60))
    return {}


def _esri_polygons(geom: dict):
    """Esri rings -> shapely polygons (exterior rings clockwise, holes counter-clockwise)."""
    from shapely.geometry import LinearRing, Polygon

    ext, holes = [], []
    for ring in geom.get("rings", []):
        if len(ring) < 4:
            continue
        (holes if LinearRing(ring).is_ccw else ext).append(ring)
    polys = [Polygon(e) for e in ext]
    out = [[p, []] for p in polys]
    for h in holes:
        hp = Polygon(h).representative_point()
        for item in out:
            if item[0].contains(hp):
                item[1].append(h)
                break
    return [Polygon(p.exterior.coords, hs) for p, hs in out]


def fetch_floodplain(g: Grid, folder: Path, tile_km: float = 25.0) -> dict[str, np.ndarray]:
    """Per 210 m cell: share in the 1% annual-chance floodplain, the 0.2% (500-yr) zone, the
    regulatory floodway; and whether FEMA's digital flood maps cover the cell's tile at all."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    tcells = int(tile_km * 1000 / CELL)
    out = {k: np.zeros((g.ny, g.nx), dtype=np.float32) for k in ("sfha", "x500", "floodway")}
    covered = np.zeros((g.ny, g.nx), dtype=bool)
    sub = 7  # rasterise at 30 m, average to the 210 m cell
    for r0 in range(0, g.ny, tcells):
        for c0 in range(0, g.nx, tcells):
            h, w = min(tcells, g.ny - r0), min(tcells, g.nx - c0)
            x0, y1 = g.x0 + c0 * CELL, g.y1 - r0 * CELL
            env = f"{x0},{y1 - h * CELL},{x0 + w * CELL},{y1}"
            base = {"geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 5070,
                    "spatialRel": "esriSpatialRelIntersects", "f": "json"}
            n_all = _get_json({**base, "where": "1=1", "returnCountOnly": "true"},
                              folder / f"nfhl_count_{r0}_{c0}.json").get("count", 0)
            if not n_all:
                continue
            covered[r0:r0 + h, c0:c0 + w] = True
            feats, offset, page = [], 0, 0
            while True:
                data = _get_json({**base, "where": FLOOD_WHERE, "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
                                  "returnGeometry": "true", "outSR": 5070, "maxAllowableOffset": 15,
                                  "geometryPrecision": 0, "resultOffset": offset, "resultRecordCount": 400},
                                 folder / f"nfhl_{r0}_{c0}_p{page}.json")
                feats += data.get("features", [])
                if not data.get("exceededTransferLimit"):
                    break
                offset += len(data.get("features", []))
                page += 1
            if not feats:
                continue
            tr = from_origin(x0, y1, CELL / sub, CELL / sub)
            shapes = {"sfha": [], "x500": [], "floodway": []}
            for f in feats:
                a = f["attributes"]
                sub_t = (a.get("ZONE_SUBTY") or "").upper()
                polys = _esri_polygons(f.get("geometry") or {})
                if a.get("SFHA_TF") == "T":
                    shapes["sfha"] += polys
                if sub_t.startswith("0.2 PCT"):
                    shapes["x500"] += polys
                if "FLOODWAY" in sub_t:
                    shapes["floodway"] += polys
            for k, polys in shapes.items():
                if not polys:
                    continue
                fine = rasterize(((p, 1) for p in polys), out_shape=(h * sub, w * sub), transform=tr,
                                 fill=0, dtype="uint8")
                out[k][r0:r0 + h, c0:c0 + w] = fine.reshape(h, sub, w, sub).mean(axis=(1, 3))
    out["covered"] = covered.astype(np.float32)
    out["flood"] = np.maximum(out["sfha"], out["x500"])
    return out
