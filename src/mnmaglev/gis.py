"""GIS phase, slices 1-6: a real alignment for a line from elevation, land cover, flood zones,
built-up land, freeways, peat soils, buildings, county parcels, and public and tribal land.

1. Data (cached in data/raw/gis, gitignored): USGS 3DEP elevation (ImageServer exportImage) and
   NLCD 2021 land cover (MRLC WCS, 30 m class codes), both in EPSG:5070 (CONUS Albers, metres),
   on a 210 m grid = exactly 7 x 7 land-cover pixels per cell, so every cell gets class fractions.
   FEMA NFHL flood zones (MapServer layer 28, queried per 25 km tile): 1% and 0.2% annual-chance
   zones and regulatory floodways, rasterised at 30 m and averaged per cell, plus whether FEMA has
   digital maps for the tile at all. NLCD 2021 impervious surface and its descriptor (roads by
   class, buildings): how built-up each cell is with roads left out, and where interstates run.
   gSSURGO soils (30 m map unit keys from SoilWeb's WCS, components from USDA Soil Data Access):
   the share of each cell in Histosols (peat and muck) and how much of it the survey covers.
2. Cost surface: what a km of guideway through each cell costs, priced with the model's own
   nominal parameters: structure (rural elevated / urban viaduct / bridge over water), right-of-way
   land by cover class and zone, wetland mitigation, the peat adder on Histosols (wetland where the
   soil survey is incomplete), and a terrain penalty for steep ground;
   floodways are priced as bridge, other flood zones get the floodplain adder; built-up cells
   (ramp on non-road impervious %) as urban viaduct; in interstate right-of-way the land costs
   land.corridor.price_factor x the land around it and building beside traffic gets an adder.
3. Route: least-cost path between the line's stations (skimage MCP), then simplified and given
   circular curves no tighter than the minimum radius (cruise speed in the country, urban speed near
   stations); vertices too sharp for a curve are dropped and the line re-simplified.
4. Measure along the final alignment: length, detour, land shares, wetland, water crossings
   and floodways (bridges), floodplain share, built-up share, km beside freeways, peat share and
   soil survey coverage, urban km, grades. Written to network/alignments/<line>.geojson and
   network/measured/<line>.yaml.

5. Buildings and parcels (slice 5): FEMA USA Structures centroids, occupancy and footprint (ArcGIS
   feature service, 10 km tiles within 15 km of the line's last alignment; land cover stands in
   further out) give the buildings a right-of-way takes per km through each cell; MnGeo's open
   county parcels give assessed land value per acre where counties publish them.
6. Public and tribal land (slice 6): USGS PAD-US 4.1 fee lands, split into Section 4(f) land
   (public parks, recreation areas, refuges, conservation and historic areas) and other public
   land (forests); Census TIGER reservations and off-reservation trust land. The route search pays
   to stay out of 4(f) and tribal land; where it crosses them it buys replacement land (4(f)) or
   pays a negotiated premium (tribal). The named units crossed are listed per line.

Not yet (later slices): rail corridors, and the at-grade / elevated
choice per cell.
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
PIER_REFS_M = (5, 10, 15, 20, 25, 30)  # reference pier heights the measured excess is recorded for
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
# gSSURGO 30 m map unit keys (EPSG:5070) from UC Davis SoilWeb's WCS (as soilDB::mukey.wcs uses);
# component tables from USDA Soil Data Access. gSSURGO, not gNATSGO: SoilWeb's gNATSGO keys
# didn't match SDA's live tables (44% of a Pine County test tile unknown), gSSURGO's all did.
SOIL_WCS = ("http://casoilresource.lawr.ucdavis.edu/cgi-bin/mapserv?map=mukey-wcs&SERVICE=WCS"
            "&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=gssurgo&FORMAT=image/tiff"
            "&GEOTIFF:COMPRESSION=DEFLATE&SUBSETTINGCRS=EPSG:5070&FORMAT=GEOTIFF_FLOAT"
            "&SUBSET=x({x0},{x1})&SUBSET=y({y0},{y1})&RESOLUTION=x(30)&RESOLUTION=y(30)")
SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/tabular/post.rest"
NOT_SURVEYED = ("NOTCOM", "AREA NOT SURVEYED")

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


TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def _get(url: str, path: Path, tries: int = 6) -> Path:
    """Download url to path once (cached). Servers sometimes answer with an HTML error or
    firewall captcha page instead of the raster, so a .tif is only kept if it is a TIFF."""
    tif = path.suffix == ".tif"
    if path.exists() and path.stat().st_size >= 1000:
        with open(path, "rb") as f:
            if not tif or f.read(4) in TIFF_MAGIC:
                return path
    req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev GIS"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
            if not tif or data[:4] in TIFF_MAGIC:
                path.write_bytes(data)
                time.sleep(0.5)
                return path
            print(f"  not a TIFF from the server (try {k + 1}): {data[:80]!r}", flush=True)
        except OSError as e:  # URLError, timeouts, dropped connections
            print(f"  download failed (try {k + 1}): {e}", flush=True)
        time.sleep(min(30 * (k + 1), 120))
    raise RuntimeError(f"no valid download for {path.name} after {tries} tries: {url}")


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
    yield from _wcs_blocks(g, folder, MRLC_URL.replace("{cov}", cov), prefix)


def _wcs_blocks(g: Grid, folder: Path, url: str, prefix: str):
    """Yield (r0, c0, blocks) per tile of a 30 m EPSG:5070 WCS coverage (url with {x0} {y0} {x1}
    {y1}); blocks[i, 7, j, 7] = the 7 x 7 pixels of cell (r0 + i, c0 + j)."""
    import rasterio
    tile = 300  # cells per request side (2100 x 2100 pixels)
    for r0 in range(0, g.ny, tile):
        for c0 in range(0, g.nx, tile):
            h, w = min(tile, g.ny - r0), min(tile, g.nx - c0)
            x0 = g.x0 + c0 * CELL
            y1 = g.y1 - r0 * CELL
            p = _get(url.format(x0=x0, y0=y1 - h * CELL, x1=x0 + w * CELL, y1=y1),
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


def _sda(query: str, tries: int = 6) -> list:
    """Rows from USDA Soil Data Access (tabular SQL over SSURGO)."""
    import json
    body = json.dumps({"query": query, "format": "JSON"}).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(SDA_URL, data=body, headers={
                "Content-Type": "application/json", "User-Agent": "minnesota-maglev GIS"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read()).get("Table", [])
        except OSError as e:
            if k == tries - 1:
                raise
            print(f"  SDA query failed (try {k + 1}): {e}", flush=True)
            time.sleep(min(15 * (k + 1), 90))
    return []


def soil_mukeys(keys, path: Path) -> dict[int, tuple[float, bool]]:
    """{mukey: (peat share, surveyed)}: peat = share of the map unit's components that are
    Histosols (organic soil >= 40 cm: peat and muck); surveyed = the survey is complete there
    (not NOTCOM, and the key is known to Soil Data Access). Cached as JSON in path."""
    import json
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [int(k) for k in keys if str(int(k)) not in cache]
    for i in range(0, len(todo), 1000):
        chunk = todo[i:i + 1000]
        info = {str(k): [0.0, False] for k in chunk}  # unknown to SDA = not surveyed
        for m, name, pct, order in _sda("SELECT mukey, compname, comppct_r, taxorder FROM component "
                                        f"WHERE mukey IN ({','.join(map(str, chunk))})"):
            e = info[str(m)]
            if name not in NOT_SURVEYED:
                e[1] = True
            if order == "Histosols":
                e[0] = min(e[0] + float(pct or 0) / 100, 1.0)
        cache.update(info)
        path.write_text(json.dumps(cache), encoding="utf-8")
    return {int(k): (v[0], v[1]) for k, v in cache.items()}


def soil_cells(blocks: np.ndarray, info: dict[int, tuple[float, bool]]) -> tuple[np.ndarray, np.ndarray]:
    """Per cell from 7 x 7 blocks of 30 m map unit keys: (peat share of the surveyed pixels,
    share of pixels surveyed). Key 0 = no data."""
    keys = np.array(sorted(info), dtype=np.int64)
    peat = np.array([info[k][0] for k in keys])
    surv = np.array([info[k][1] for k in keys], dtype=float)
    b = blocks.astype(np.int64)
    i = np.clip(np.searchsorted(keys, b), 0, max(len(keys) - 1, 0))
    known = (keys[i] == b) & (b > 0) if len(keys) else np.zeros(b.shape, bool)
    s = np.where(known, surv[i], 0.0) if len(keys) else np.zeros(b.shape)
    p = np.where(known, peat[i], 0.0) if len(keys) else np.zeros(b.shape)
    n = s.sum(axis=(1, 3))
    return (p * s).sum(axis=(1, 3)) / np.maximum(n, 1), n / 49.0


def fetch_soils(g: Grid, folder: Path) -> dict[str, np.ndarray]:
    """Per 210 m cell from gSSURGO (30 m map unit keys, SoilWeb WCS) and Soil Data Access:
    peat = Histosol share of the surveyed pixels, coverage = share of the cell surveyed."""
    tiles = list(_wcs_blocks(g, folder, SOIL_WCS, "soil"))
    keys = np.unique(np.concatenate([np.unique(b.astype(np.int64)) for _, _, b in tiles]))
    info = soil_mukeys(keys[keys > 0], folder / "soil_mukeys.json")
    peat = np.zeros((g.ny, g.nx), dtype=np.float32)
    cov = np.zeros((g.ny, g.nx), dtype=np.float32)
    for r0, c0, b in tiles:
        hh, ww = b.shape[0], b.shape[2]
        peat[r0:r0 + hh, c0:c0 + ww], cov[r0:r0 + hh, c0:c0 + ww] = soil_cells(b, info)
    return {"peat": peat, "coverage": cov}


def soft_ground(frac: dict, soil: dict | None) -> np.ndarray:
    """Peat share per cell: SSURGO Histosols where the soil survey is complete, the wetland share
    (the old proxy) where it isn't."""
    if soil is None:
        return frac["wetland"]
    return soil["coverage"] * soil["peat"] + (1.0 - soil["coverage"]) * frac["wetland"]


def built_up(dev: dict, frac: dict, P: dict) -> np.ndarray:
    """Share of each cell to price as built-up (urban viaduct): a ramp on non-road impervious %."""
    lo, hi = P["land.developed.impervious_low"], P["land.developed.impervious_high"]
    return np.maximum(frac["urban"], np.clip((dev["imp_nonroad"] - lo) / (hi - lo), 0.0, 1.0))


def zone_of_lat(lat: float) -> str:
    return "north" if lat >= 46.0 else ("central" if lat >= 44.6 else "south")


def cost_surface(g: Grid, frac: dict, dem: np.ndarray, P: dict, flood: dict | None = None,
                 dev: dict | None = None, soil: dict | None = None, bldg: dict | None = None,
                 parcels: dict | None = None, public: dict | None = None) -> np.ndarray:
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
    # peat (SSURGO Histosols; wetland where the soil survey is incomplete): deep piles, the peat adder
    soft = 1.0 + soft_ground(frac, soil) * P["costs.adders.peat_soft_ground"]
    # floodplain: piers above the 500-year flood with freeboard, scour protection;
    # beside a freeway: pier crash protection, traffic control while building
    corridor = dev["corridor"] if dev else 0.0
    adders = (1.0 + (flood["flood"] if flood else 0.0) * P["costs.adders.floodplain"]
              + corridor * P["costs.adders.highway_corridor"])
    structure = (span * P[gw + "bridge_per_m"] * 1000
                 + (built * P[gw + "urban_viaduct"] + rural * P[gw + "elevated"] * soft) * adders)
    # land price per acre: by cover class, or the counties' assessed land value where they publish parcels
    per_acre = (frac["suburban"] * P["land.price_per_acre.suburban"] + frac["urban"] * P["land.price_per_acre.urban_core"]
                + frac["forest"] * forest + frac["open"] * crop + frac["wetland"] * P["land.price_per_acre.wetland"])
    if parcels:
        cov = parcels["coverage"]
        per_acre = (cov * (1.0 - frac["water"]) * parcels["price"] / 1e6 * P["land.parcels.emv_to_market"]
                    + (1.0 - cov) * per_acre)
    # in a freeway's right-of-way the land costs a share of what the land around it would
    land = (acres_per_km * P["land.acquisition_multiplier"]
            * (1.0 - corridor * (1.0 - P["land.corridor.price_factor"])) * per_acre)
    # buildings the right-of-way takes (not in dense urban cells, which run in streets, nor over water
    # or in freeway right-of-way)
    takes = 0.0
    if bldg:
        from .costs import building_cost
        width = built * P["land.row_width.urban"] + (1.0 - built) * P["land.row_width.elevated"]
        t = building_takes(bldg, width)
        takes = (building_cost({k: v["n"] for k, v in t.items()}, {k: v["m2"] for k, v in t.items()}, P)
                 * (1.0 - frac["urban"]) * (1.0 - span) * (1.0 - corridor))
    wetland = (frac["wetland"] * acres_per_km * P["land.wetlands.impact_fraction_elevated"]
               * P["land.wetlands.replacement_ratio"] * P["land.wetlands.credit_price"])
    gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), CELL)
    slope = np.hypot(gx, gy)
    terrain = P[gw + "elevated"] * 0.5 * np.minimum(slope / P["system.geometry.max_gradient"], 1.0)
    # public and tribal land: Section 4(f) land is bought plus replacement land; tribal land at a
    # negotiated premium. The route search also pays to stay out of both (avoidance, below)
    avoid = 0.0
    if public:
        # beside a freeway the guideway sits in highway right-of-way, not in the park next to it
        s4f = public["section_4f"] * (1.0 - corridor)
        land = land * (1.0 + s4f * P["land.public.section_4f_replacement"]
                       + public["tribal"] * (P["land.tribal.consent_multiplier"] - 1.0))
        avoid = (s4f * P["land.public.section_4f_avoidance_km"]
                 + public["tribal"] * P["land.tribal.avoidance_km"]) * P[gw + "elevated"]
    cost = structure + land + takes + wetland + terrain + avoid
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


def path_cost(pts: np.ndarray, cost: np.ndarray, g: Grid) -> float:
    """MUSD along a polyline over the cost surface (MUSD per km), sampled every half cell."""
    total = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        L = float(np.linalg.norm(b - a))
        n = max(int(L / (CELL / 2)), 1)
        u = (np.arange(n) + 0.5) / n
        x, y = a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])
        r = np.clip(((g.y1 - y) // CELL).astype(int), 0, g.ny - 1)
        c = np.clip(((x - g.x0) // CELL).astype(int), 0, g.nx - 1)
        total += float(cost[r, c].sum()) * L / n / 1000.0
    return total


def _refine(pts: list, fixed: list, radius, chord, g: Grid, steps=(2000.0, 1000.0, 500.0, 250.0),
            passes: int = 6, min_gain: float = 0.5) -> tuple[list, int]:
    """Lower the alignment's cost on the cost surface while every curve keeps fitting: coarse to
    fine, insert a bend at the middle of a chord (offset sideways) and move free vertices in eight
    directions, keeping a change when it saves at least min_gain MUSD. Stations stay fixed."""
    pts, fixed = [np.asarray(p, dtype=float) for p in pts], list(fixed)
    lo, hi = np.array([g.x0 + CELL, g.y0 + CELL]), np.array([g.x1 - CELL, g.y1 - CELL])
    dirs = [np.array([math.cos(a), math.sin(a)]) for a in np.arange(8) * math.pi / 4]
    moves = 0

    def fits(q: list, idx) -> bool:
        for i in idx:
            if 0 < i < len(q) - 1:
                a, b = q[i] - q[i - 1], q[i + 1] - q[i]
                la, lb = np.linalg.norm(a), np.linalg.norm(b)
                if la < 1 or lb < 1:
                    return False
                theta = math.acos(float(np.clip(np.dot(a, b) / (la * lb), -1, 1)))
                if radius(q[i]) * math.tan(theta / 2) > 0.5 * min(la, lb) + 1e-6:
                    return False
        return True

    for step in steps:
        for _ in range(passes):
            improved = False
            i = 0
            while i < len(pts) - 1:  # gentle bends on long chords
                a, b = pts[i], pts[i + 1]
                v = b - a
                L = float(np.linalg.norm(v))
                best = None
                if L > 4 * step:
                    n = np.array([-v[1], v[0]]) / L
                    base = chord(a, b)
                    for off in (step, -step):
                        m = (a + b) / 2 + n * off
                        if (m < lo).any() or (m > hi).any():
                            continue
                        q = pts[:i + 1] + [m] + pts[i + 1:]
                        c = chord(a, m) + chord(m, b)
                        if c < base - min_gain and (best is None or c < best[0]) and fits(q, (i, i + 1, i + 2)):
                            best = (c, m)
                if best:
                    pts.insert(i + 1, best[1])
                    fixed.insert(i + 1, False)
                    moves += 1
                    improved = True
                    continue
                i += 1
            for j in range(1, len(pts) - 1):  # move corners
                if fixed[j]:
                    continue
                base = chord(pts[j - 1], pts[j]) + chord(pts[j], pts[j + 1])
                best = None
                for dvec in dirs:
                    p = pts[j] + dvec * step
                    if (p < lo).any() or (p > hi).any():
                        continue
                    c = chord(pts[j - 1], p) + chord(p, pts[j + 1])
                    if c < base - min_gain and (best is None or c < best[0]):
                        q = pts[:j] + [p] + pts[j + 1:]
                        if fits(q, (j - 1, j, j + 1)):
                            best = (c, p)
                if best:
                    pts[j] = best[1]
                    moves += 1
                    improved = True
            if not improved:
                break
    return pts, moves


def smooth(legs: list[np.ndarray], stations_xy: np.ndarray, P: dict, cost: np.ndarray, g: Grid,
           tol: float = 300.0) -> tuple[np.ndarray, dict]:
    """Least-cost path (one polyline per station-to-station leg) -> alignment with circular curves
    >= minimum radius (urban radius near stations).

    Each leg is simplified finely (Douglas-Peucker, tol), then, while some curve doesn't fit between
    its neighbours, the vertex (a failing one or a neighbour) whose removal adds the least cost on
    the cost surface is dropped. Stations stay fixed. One global tolerance (slices 1-3) straightened
    the whole line for its tightest spot and cut across lakes the least-cost path went around.
    Dropping vertices alone can still leave long chords across lakes where the least-cost path
    threads gaps too tight for the curves, so the result is then refined (_refine): corners moved
    and gentle bends added wherever that lowers the cost and every curve still fits.
    """
    r_cruise = min_curve_radius_m(P["system.vehicle.cruise_speed"], P["system.geometry.superelevation_max"],
                                  P["system.geometry.unbalanced_lateral"])
    r_urban = min_curve_radius_m(P["system.vehicle.urban_speed"], P["system.geometry.superelevation_max"],
                                 P["system.geometry.unbalanced_lateral"])
    near = 15000.0  # m from a station where trains run at or below urban speed
    pts, fixed = [], []
    for k, leg in enumerate(legs):
        sl = _simplify(leg, tol)
        if k:
            sl = sl[1:]
        pts += list(sl)
        fixed += ([True] if not k else []) + [False] * (len(sl) - (1 if k else 2)) + [True]
    memo: dict = {}

    def chord(a, b) -> float:
        key = (a.tobytes(), b.tobytes())
        if key not in memo:
            memo[key] = path_cost(np.array([a, b]), cost, g)
        return memo[key]

    removed = 0
    while True:
        s = np.array(pts)
        d = np.min(np.linalg.norm(s[:, None, :] - stations_xy[None, :, :], axis=2), axis=1)
        radii = np.where(d < near, r_urban, r_cruise)
        ok = _fillet_ok(s, radii)
        cands = {j for i in np.where(~ok)[0] for j in (i - 1, i, i + 1)
                 if 0 < j < len(pts) - 1 and not fixed[j]}
        if not cands:
            break
        best = min(cands, key=lambda j: chord(pts[j - 1], pts[j + 1])
                   - chord(pts[j - 1], pts[j]) - chord(pts[j], pts[j + 1]))
        del pts[best], fixed[best]
        removed += 1

    def radius(p) -> float:
        return r_urban if np.min(np.linalg.norm(stations_xy - p, axis=1)) < near else r_cruise

    pts, moves = _refine(pts, fixed, radius, chord, g)
    s = np.array(pts)
    d = np.min(np.linalg.norm(s[:, None, :] - stations_xy[None, :, :], axis=2), axis=1)
    radii = np.where(d < near, r_urban, r_cruise)
    ok = _fillet_ok(s, radii)
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
    out = np.array(out)
    raw = np.vstack([legs[0]] + [l[1:] for l in legs[1:]])
    return out, {"r_cruise_m": r_cruise, "r_urban_m": r_urban, "simplify_tol_m": tol,
                 "vertices": len(s), "vertices_removed_for_curves": removed, "refinement_moves": moves,
                 "all_curves_fit": bool(ok.all()),
                 "cost_least_cost_path_musd": round(path_cost(raw, cost, g)),
                 "cost_smoothed_musd": round(path_cost(out, cost, g))}


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
    soil = fetch_soils(g, folder)
    bldg = fetch_buildings(g, line, folder / "buildings", frac)
    parcels = fetch_parcels(g, line, folder / "parcels")
    public = fetch_public_land(g, folder / "public")
    cost = cost_surface(g, frac, dem, P, flood, dev, soil, bldg, parcels, public)
    cell_km = CELL / 1000.0
    to5070 = _to_5070()
    stops = [p for p in line.points if p.is_station]
    st_xy = np.array([to5070.transform(p.lon, p.lat) for p in stops])
    # legs run between stations and via points (points the route must pass, e.g. to follow a corridor)
    route_pts = [p for p in line.points if p.is_station or p.type == "via"]
    rp_xy = np.array([to5070.transform(p.lon, p.lat) for p in route_pts])
    legs = []
    for (a, b), (pa, pb) in zip(zip(rp_xy, rp_xy[1:]), zip(route_pts, route_pts[1:])):
        mcp = MCP_Geometric(cost * cell_km, fully_connected=True)
        start, end = g.rc(*a), g.rc(*b)
        mcp.find_costs([start], [end])
        path = mcp.traceback(end)
        xy = np.array([g.xy(r, c) for r, c in path])
        xy[0], xy[-1] = a, b
        legs.append((pa, pb, xy))
    align, curve_info = smooth([l[2] for l in legs], st_xy, P, cost, g)
    layers = {**frac, **{f"fl_{k}": v for k, v in flood.items()},
              "dev_built": built_up(dev, frac, P), "dev_corridor": dev["corridor"],
              "soil_peat": soil["peat"], "soil_coverage": soil["coverage"],
              "pc_price": parcels["price"], "pc_coverage": parcels["coverage"],
              **{f"pl_{k}": public[k] for k in PUBLIC_KINDS},
              **{f"bl_{grp}_{k}": bldg[f"{grp}_{k}"] / (CELL ** 2 / 1e6)  # per km2
                 for grp in BUILDING_GROUPS for k in BUILDING_SUMS}}
    meas = measure(align, st_xy, stops, g, layers, dem, P["system.geometry.max_gradient"])
    return {"grid": g, "alignment": align, "curves": curve_info, "measured": meas, "stations": stops,
            "public_land_crossed": public_land_crossed(align, public["features"])}


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
        # buildings beside the km where the right-of-way can take them (not the urban ends, bridges or
        # freeway right-of-way); the model multiplies by those km and the right-of-way width
        w = rest * (1.0 - f["dev_corridor"][m])
        if "bl_residential_n" in f and w.sum() > 0:
            dev["buildings_per_km2"] = {
                grp: {k: round(float((f[f"bl_{grp}_{k}"][m] * w).sum() / w.sum()), 1) for k in BUILDING_SUMS}
                for grp in BUILDING_GROUPS}
    if "pc_coverage" in f:
        cov = f["pc_coverage"][m]
        dev["parcel_coverage"] = round(float(cov.mean()), 3)
        dev["parcel_land_usd_per_acre"] = round(float((f["pc_price"][m] * cov).sum() / cov.sum())) if cov.sum() else 0
    if "pl_section_4f" in f:
        # 4(f) land outside freeway right-of-way (beside a freeway the guideway uses highway land)
        s4f = f["pl_section_4f"][m] * (1.0 - f["dev_corridor"][m]) if "dev_corridor" in f else f["pl_section_4f"][m]
        dev["public_land_shares"] = {"section_4f": round(float(s4f.mean()), 3),
                                     **{k: round(float(f[f"pl_{k}"][m].mean()), 3) for k in PUBLIC_KINDS[1:]}}
        dev["section_4f_km"] = round(float(s4f.sum() * step / 1000), 2)
        dev["tribal_km"] = round(float(f["pl_tribal"][m].sum() * step / 1000), 2)
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
        # SSURGO Histosols on the surveyed part of the piece, and how much of it is surveyed
        **({"peat_share": round(float((f["soil_peat"][m] * f["soil_coverage"][m]).sum()
                                      / max(f["soil_coverage"][m].sum(), 1e-9)), 3),
            "soil_survey_coverage": round(float(f["soil_coverage"][m].mean()), 3)} if "soil_peat" in f else {}),
        "urban_km": round(float(urban.sum() * step / 1000), 1),
        "urban_start_km": round(float(urban[:half].sum() * step / 1000), 1),
        "urban_end_km": round(float(urban[half:].sum() * step / 1000), 1),
        "bridges_m": [round(b) for b in bridges if b >= 100],
        "max_ground_grade_1km": round(float(np.nanmax(grades)), 4),
        "elev_range_m": [round(float(np.nanmin(zz))), round(float(np.nanmax(zz)))],
        "guideway_max_height_m": round(float(np.nanmax(height)), 1),
        "km_over_25m_high": round(float((height > 25).sum() * step / 1000), 2),
        # m x km of guideway above each reference height (the model interpolates for
        # costs.guideway.pier_height_ref and prices every metre above it)
        "pier_excess_m_km": {t: round(float(np.clip(height - t, 0, None).sum() * step / 1000), 2)
                             for t in PIER_REFS_M},
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
              "# Guideway height = lowest profile at or above the ground within the grade limit;\n"
              "# pier_excess_m_km = metres above each reference height x km (tall piers are priced\n"
              "# above costs.guideway.pier_height_ref). gSSURGO soils: peat_share = Histosols (peat,\n"
              "# muck) on the surveyed part, soil_survey_coverage = share surveyed (wetland stands in\n"
              "# for peat elsewhere). Buildings (FEMA USA Structures): buildings_per_km2 by group beside\n"
              "# the takeable km (n = count, side = sum sqrt(m2), area = sum m2, aside = sum m2^1.5).\n"
              "# County parcels (MnGeo open counties): parcel_land_usd_per_acre = assessed land EMV per\n"
              "# acre where parcel_coverage says the parcels cover the route. Public land (USGS PAD-US 4.1\n"
              "# fee) and tribal land (Census TIGER reservations, off-reservation trust land):\n"
              "# public_land_shares = section_4f (public parks, recreation areas, refuges, conservation\n"
              "# and historic areas; outside freeway right-of-way), public_other (forests, other public\n"
              "# land), tribal; the named units\n"
              "# crossed are listed in public_land_crossed.\n"
              "# Not yet: rail corridors. Land shares: NLCD groups (water, suburban = developed\n"
              "# open/low, urban = developed medium/high, forest, open = crops/pasture/grass/shrub/barren,\n"
              "# wetland).\n" % (line.id, line.id))
    data = {"line": line.id, "curves": res["curves"], "pieces": res["measured"]}
    if res.get("public_land_crossed") is not None:
        data["public_land_crossed"] = res["public_land_crossed"]
    mpath.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return gpath, mpath


# --- FEMA National Flood Hazard Layer (slice 2) -------------------------------------------------

NFHL_QUERY = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
FLOOD_WHERE = "SFHA_TF='T' OR ZONE_SUBTY LIKE '0.2 PCT%' OR ZONE_SUBTY LIKE '%FLOODWAY%'"


def _get_json(params: dict, path: Path | None, tries: int = 10, url: str = NFHL_QUERY,
              pause: float = 1.0) -> dict:
    """ArcGIS REST query (GET), cached at path unless path is None."""
    import json
    import urllib.parse

    if path is not None and path.exists() and path.stat().st_size > 20:
        return json.loads(path.read_text(encoding="utf-8"))
    url = url + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev GIS"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            if "error" in data:
                raise RuntimeError(data["error"])
            break
        except (OSError, ValueError, RuntimeError):  # servers drop requests or answer errors now and then
            if k == tries - 1:
                raise
            time.sleep(min(10 * (k + 1), 60))
    if path is not None:  # outside the retry loop: a local write error is not a server hiccup
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(pause)
    return data


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


# --- Buildings (FEMA USA Structures) and parcels (MnGeo open counties), slice 5 ------------------

STRUCTURES_QUERY = ("https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
                    "USA_Structures_View/FeatureServer/0/query")
PARCELS_URL = ("https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_mngeo/"
               "plan_parcels_open/FeatureServer")
# USA Structures occupancy class -> pricing group; every other class (commercial, industrial,
# government, education, assembly, utility, unclassified) is nonresidential
BUILDING_GROUPS = ("residential", "nonresidential", "agriculture")
OCC_GROUP = {"Residential": 0, "Agriculture": 2}
BUILDING_SUMS = ("n", "side", "area", "aside")  # per cell: count, sum sqrt(m2), sum m2, sum m2 x sqrt(m2)
BAND_KM = 15.0        # buildings and parcels are fetched for tiles this close to the line's last alignment
POINT_TILE_KM = 10.0
PARCEL_SMOOTH_CELLS = 2.0  # Gaussian sigma for land value per acre (rural parcels are 400-800 m across)


def _band_tiles(g: Grid, line: Line, tile_km: float = POINT_TILE_KM, band_km: float = BAND_KM):
    """(r0, c0, h, w) grid tiles within band_km of the line's previous GIS alignment
    (network/alignments/<id>.geojson), or of the straight lines between its points without one."""
    import json
    from shapely.geometry import LineString, box

    path = ROOT / "network" / "alignments" / f"{line.id}.geojson"
    t = _to_5070()
    if path.exists():
        coords = json.loads(path.read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"]
    else:
        coords = [(p.lon, p.lat) for p in line.points]
    ref = LineString([t.transform(lon, lat) for lon, lat in coords])
    tc = int(tile_km * 1000 / CELL)
    tiles = []
    for r0 in range(0, g.ny, tc):
        for c0 in range(0, g.nx, tc):
            h, w = min(tc, g.ny - r0), min(tc, g.nx - c0)
            x0, y1 = g.x0 + c0 * CELL, g.y1 - r0 * CELL
            if ref.distance(box(x0, y1 - h * CELL, x0 + w * CELL, y1)) <= band_km * 1000:
                tiles.append((r0, c0, h, w))
    return tiles


def _tile_mask(g: Grid, tiles) -> np.ndarray:
    m = np.zeros((g.ny, g.nx), dtype=bool)
    for r0, c0, h, w in tiles:
        m[r0:r0 + h, c0:c0 + w] = True
    return m


def _fetch_points(url: str, tiles, g: Grid, folder: Path, prefix: str, fields: list[str], oid: str,
                  columns: tuple[str, ...], convert, workers: int = 4) -> dict[str, np.ndarray]:
    """Centroids (EPSG:5070) of the features of an ArcGIS feature layer, with attributes turned into
    numbers by convert(attributes) -> one value per column. A feature belongs to the tile its
    centroid lies in (features crossing tile edges are kept once). Cached per tile as .npz."""
    from concurrent.futures import ThreadPoolExecutor

    def one(tile):
        r0, c0, h, w = tile
        path = folder / f"{prefix}_{r0}_{c0}.npz"
        if path.exists():
            with np.load(path) as z:
                return {k: z[k] for k in z.files}
        x0, y1 = g.x0 + c0 * CELL, g.y1 - r0 * CELL
        x1, y0 = x0 + w * CELL, y1 - h * CELL
        base = {"where": "1=1", "geometry": f"{x0},{y0},{x1},{y1}", "geometryType": "esriGeometryEnvelope",
                "inSR": 5070, "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(fields),
                "returnGeometry": "false", "returnCentroid": "true", "outSR": 5070,
                "orderByFields": oid, "resultRecordCount": 2000, "f": "json"}
        rows, offset = [], 0
        while True:
            data = _get_json({**base, "resultOffset": offset}, None, url=url, pause=0.2)
            feats = data.get("features", [])
            for f in feats:
                c = f.get("centroid")
                if c and x0 <= c["x"] < x1 and y0 < c["y"] <= y1:
                    rows.append((c["x"], c["y"], *convert(f["attributes"])))
            if not data.get("exceededTransferLimit") or not feats:
                break
            offset += len(feats)
        arr = np.array(rows, dtype=np.float64).reshape(-1, 2 + len(columns))
        out = {"x": arr[:, 0], "y": arr[:, 1], **{k: arr[:, 2 + i] for i, k in enumerate(columns)}}
        np.savez_compressed(path, **out)
        return out

    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(one, tiles))
    keys = ("x", "y", *columns)
    return {k: np.concatenate([p[k] for p in parts]) if parts else np.zeros(0) for k in keys}


def _cell_sums(g: Grid, x: np.ndarray, y: np.ndarray, weights: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    r = np.floor((g.y1 - y) / CELL).astype(int)
    c = np.floor((x - g.x0) / CELL).astype(int)
    ok = (r >= 0) & (r < g.ny) & (c >= 0) & (c < g.nx)
    idx = r[ok] * g.nx + c[ok]
    return {k: np.bincount(idx, weights=w[ok], minlength=g.ny * g.nx).reshape(g.ny, g.nx)
            for k, w in weights.items()}


def _by_cover(v: np.ndarray, frac: dict, mask: np.ndarray) -> np.ndarray:
    """v outside mask, estimated from inside it: the mean of v per unit of each NLCD group, mixed by
    each cell's own land cover."""
    out = np.zeros(v.shape, dtype=np.float64)
    for f in frac.values():
        w = f[mask].sum()
        if w > 0:
            out += f * (v[mask] * f[mask]).sum() / w
    return out


def fetch_buildings(g: Grid, line: Line, folder: Path, frac: dict) -> dict[str, np.ndarray]:
    """Per cell and pricing group: number of buildings (USA Structures, footprints > 450 sq ft) and
    sums of sqrt(footprint), footprint and footprint x sqrt(footprint), which give the buildings a
    right-of-way of any width takes (building_takes). Fetched near the line; elsewhere estimated from
    the land cover."""
    folder.mkdir(parents=True, exist_ok=True)
    tiles = _band_tiles(g, line)
    p = _fetch_points(STRUCTURES_QUERY, tiles, g, folder, "bldg", ["OCC_CLS", "SQMETERS"], "OBJECTID",
                      ("group", "m2"),
                      lambda a: (OCC_GROUP.get(a.get("OCC_CLS"), 1), float(a.get("SQMETERS") or 0.0)))
    band = _tile_mask(g, tiles)
    out = {}
    for gi, name in enumerate(BUILDING_GROUPS):
        m = p["group"] == gi
        a = p["m2"][m]
        s = np.sqrt(a)
        sums = _cell_sums(g, p["x"][m], p["y"][m], {"n": np.ones_like(a), "side": s, "area": a, "aside": a * s})
        for k, v in sums.items():
            out[f"{name}_{k}"] = np.where(band, v, _by_cover(v, frac, band))
    out["band"] = band.astype(np.float32)
    return out


def building_takes(b: dict, width) -> dict[str, dict[str, np.ndarray]]:
    """Buildings taken and their footprint (m2) per km of route through each cell, by group.

    A building of side s (sqrt of its footprint) is hit by a right-of-way of width W when its
    centre lies within (W + s) / 2 of the centreline (route and building axis-aligned; a random
    orientation would widen s by up to ~27%), so a km of route through a cell holding buildings
    i takes sum_i (W + s_i) x 1000 / CELL^2 of them and sum_i a_i (W + s_i) x 1000 / CELL^2 m2.
    """
    k = 1000.0 / CELL ** 2
    return {name: {"n": (width * b[f"{name}_n"] + b[f"{name}_side"]) * k,
                   "m2": (width * b[f"{name}_area"] + b[f"{name}_aside"]) * k} for name in BUILDING_GROUPS}


def _parcel_counties(g: Grid, folder: Path) -> np.ndarray:
    """Cells inside counties that publish parcels as open data (MnGeo gac_open_approval)."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    data = _get_json({"where": "gac_open_approval='true'", "outFields": "countyname", "returnGeometry": "true",
                      "outSR": 5070, "maxAllowableOffset": 100, "f": "json"},
                     folder / "parcel_counties.json", url=PARCELS_URL + "/0/query")
    polys = [p for f in data.get("features", []) for p in _esri_polygons(f.get("geometry") or {})]
    if not polys:
        return np.zeros((g.ny, g.nx), dtype=bool)
    return rasterize(((p, 1) for p in polys), out_shape=(g.ny, g.nx),
                     transform=from_origin(g.x0, g.y1, CELL, CELL), fill=0, dtype="uint8").astype(bool)


def fetch_parcels(g: Grid, line: Line, folder: Path) -> dict[str, np.ndarray]:
    """Assessed land value per acre (estimated market value of the land alone, USD/acre) from the
    county parcels MnGeo compiles (counties that publish them as open data), smoothed over ~400 m,
    and where it is known ('coverage'). Out of state, in closed counties and far from the line: 0."""
    from scipy.ndimage import gaussian_filter

    folder.mkdir(parents=True, exist_ok=True)
    open_c = _parcel_counties(g, folder)
    tiles = [t for t in _band_tiles(g, line) if open_c[t[0]:t[0] + t[2], t[1]:t[1] + t[3]].any()]
    p = _fetch_points(PARCELS_URL + "/1/query", tiles, g, folder, "parcel",
                      ["emv_land", "emv_bldg", "acres_poly", "useclass1"], "objectid",
                      ("emv_land", "emv_bldg", "acres", "residential"),
                      lambda a: (float(a.get("emv_land") or 0.0), float(a.get("emv_bldg") or 0.0),
                                 float(a.get("acres_poly") or 0.0),
                                 1.0 if str(a.get("useclass1") or "").lower().startswith("res") else 0.0))
    use = (p["emv_land"] > 0) & (p["acres"] > 0)
    s = _cell_sums(g, p["x"][use], p["y"][use], {"emv": p["emv_land"][use], "acres": p["acres"][use]})
    emv = gaussian_filter(s["emv"], PARCEL_SMOOTH_CELLS, mode="constant")
    acres = gaussian_filter(s["acres"], PARCEL_SMOOTH_CELLS, mode="constant")
    cover = open_c & _tile_mask(g, tiles) & (acres > 0.5)
    price = np.where(cover, emv / np.maximum(acres, 1e-9), 0.0)
    return {"price": price, "coverage": cover.astype(np.float32)}


# --- Public and tribal land (USGS PAD-US 4.1, Census TIGER), slice 6 -----------------------------

PADUS_QUERY = "https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer/0/query"
TRIBAL_QUERY = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/AIANNHA/MapServer/{}/query"
TRIBAL_LAYERS = (2, 3)  # federal American Indian reservations, off-reservation trust land
PUBLIC_OWNERS = ("FED", "STAT", "LOC", "DIST", "JNT")  # Section 4(f) covers publicly owned land only
# PAD-US designation types that are parks, recreation areas, refuges and conservation or historic areas
# (Section 4(f)); the rest of public land (national, state and county forests, other) is multiple-use
SECTION_4F_TYPES = ("NP", "NM", "NWR", "NRA", "NCA", "NLS", "NT", "WSR", "WA", "WSA", "RNA",
                    "SP", "SW", "SCA", "SREC", "SHCA", "LP", "LCA", "LREC", "LHCA", "REC")
SECTION_4F_MANAGERS = ("FWS",)  # waterfowl production areas are refuge land (FWS 'RMA' in PAD-US)
# county and state forests are multiple-use (timber) even where PAD-US calls them conservation areas
# (Wisconsin's county forests are 'LCA'); Illinois forest preserves are parks and stay 4(f)
MULTIPLE_USE_NAMES = ("County Forest", "State Forest")
PUBLIC_KINDS = ("section_4f", "public_other", "tribal")


def public_kind(a: dict) -> str | None:
    """PAD-US fee record -> 'section_4f', 'public_other' or None (private, NGO, unknown owner)."""
    if a.get("Own_Type") not in PUBLIC_OWNERS:
        return None
    if any(n in (a.get("Unit_Nm") or "") for n in MULTIPLE_USE_NAMES):
        return "public_other"
    if a.get("Des_Tp") in SECTION_4F_TYPES or a.get("Mang_Name") in SECTION_4F_MANAGERS:
        return "section_4f"
    return "public_other"


def _rasterize_share(g: Grid, polys: list, sub: int = 7, band_rows: int = 100) -> np.ndarray:
    """Share of each cell covered by any of the polygons (rasterised at CELL / sub)."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    out = np.zeros((g.ny, g.nx), dtype=np.float32)
    if not polys:
        return out
    b = np.array([p.bounds for p in polys])
    for r0 in range(0, g.ny, band_rows):
        h = min(band_rows, g.ny - r0)
        top, bottom = g.y1 - r0 * CELL, g.y1 - (r0 + h) * CELL
        pick = [p for p, (_, y0, _, y1) in zip(polys, b) if y1 >= bottom and y0 <= top]
        if not pick:
            continue
        fine = rasterize(((p, 1) for p in pick), out_shape=(h * sub, g.nx * sub),
                         transform=from_origin(g.x0, top, CELL / sub, CELL / sub), fill=0, dtype="uint8")
        out[r0:r0 + h] = fine.reshape(h, sub, g.nx, sub).mean(axis=(1, 3))
    return out


def fetch_public_land(g: Grid, folder: Path, tile_km: float = 50.0, batch: int = 100) -> dict:
    """Per 210 m cell: share in Section 4(f) land (public parks, recreation areas, refuges,
    conservation and historic areas; PAD-US 4.1 fee), other public land (forests, multiple-use), and
    tribal land (reservations and off-reservation trust land, TIGER). Also the polygons with their
    names ('features': (kind, name, polygon)) to list what a route crosses."""
    folder.mkdir(parents=True, exist_ok=True)
    tcells = int(tile_km * 1000 / CELL)
    ids = set()
    for r0 in range(0, g.ny, tcells):
        for c0 in range(0, g.nx, tcells):
            h, w = min(tcells, g.ny - r0), min(tcells, g.nx - c0)
            x0, y1 = g.x0 + c0 * CELL, g.y1 - r0 * CELL
            d = _get_json({"geometry": f"{x0},{y1 - h * CELL},{x0 + w * CELL},{y1}",
                           "geometryType": "esriGeometryEnvelope", "inSR": 5070,
                           "spatialRel": "esriSpatialRelIntersects", "where": "1=1",
                           "returnIdsOnly": "true", "f": "json"},
                          folder / f"padus_ids_{r0}_{c0}.json", url=PADUS_QUERY, pause=0.2)
            ids.update(d.get("objectIds") or [])
    ids = sorted(ids)
    feats = []
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        d = _get_json({"objectIds": ",".join(map(str, chunk)), "outFields": "Own_Type,Des_Tp,Mang_Name,Unit_Nm",
                       "returnGeometry": "true", "outSR": 5070, "maxAllowableOffset": 15,
                       "geometryPrecision": 0, "f": "json"},
                      folder / f"padus_{chunk[0]}_{chunk[-1]}.json", url=PADUS_QUERY, pause=0.2)
        for f in d.get("features", []):
            kind = public_kind(f["attributes"])
            if kind:
                feats += [(kind, f["attributes"].get("Unit_Nm") or "", p.buffer(0))
                          for p in _esri_polygons(f.get("geometry") or {})]
    env = f"{g.x0},{g.y1 - g.ny * CELL},{g.x0 + g.nx * CELL},{g.y1}"
    for layer in TRIBAL_LAYERS:
        d = _get_json({"geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 5070,
                       "spatialRel": "esriSpatialRelIntersects", "where": "1=1", "outFields": "NAME",
                       "returnGeometry": "true", "outSR": 5070, "maxAllowableOffset": 15,
                       "geometryPrecision": 0, "f": "json"},
                      folder / f"tribal_{layer}.json", url=TRIBAL_QUERY.format(layer), pause=0.2)
        feats += [("tribal", f["attributes"].get("NAME") or "", p.buffer(0))
                  for f in d.get("features", []) for p in _esri_polygons(f.get("geometry") or {})]
    out = {k: _rasterize_share(g, [p for kind, _, p in feats if kind == k]) for k in PUBLIC_KINDS}
    # one kind per cell share: tribal first, then 4(f), then the rest of public land
    out["section_4f"] = np.minimum(out["section_4f"], 1.0 - out["tribal"])
    out["public_other"] = np.clip(out["public_other"] - out["section_4f"] - out["tribal"], 0.0, None)
    out["features"] = feats
    return out


def public_land_crossed(align: np.ndarray, feats: list, min_km: float = 0.1) -> list[dict]:
    """Named public and tribal land units the alignment runs through: km inside each (polygons with
    the same kind and name are merged, so a unit PAD-US lists twice, e.g. by two managers, counts once)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    if not feats:
        return []
    line = LineString(align)
    groups: dict[tuple[str, str], list] = {}
    for i in STRtree([p for _, _, p in feats]).query(line):
        kind, name, poly = feats[int(i)]
        groups.setdefault((kind, name), []).append(poly)
    rows = [{"kind": k, "name": n, "km": round(line.intersection(unary_union(ps)).length / 1000.0, 2)}
            for (k, n), ps in groups.items()]
    return sorted((r for r in rows if r["km"] >= min_km), key=lambda r: (PUBLIC_KINDS.index(r["kind"]), -r["km"]))


# --- Long lines in sections ---------------------------------------------------------------------

def line_sections(line: Line) -> list[Line]:
    """The line split at its gis_split_at stations: sub-lines sharing the split stations."""
    from dataclasses import replace

    ids = [p.id for p in line.points]
    cuts = [0] + [ids.index(s) for s in line.gis_split_at] + [len(ids) - 1]
    return [replace(line, points=line.points[i:j + 1], segments=line.segments[i:j])
            for i, j in zip(cuts, cuts[1:])]


def _section_folder(line: Line, k: int, sec: Line) -> Path:
    return RAW / line.id / f"s{k}_{sec.points[0].id}_{sec.points[-1].id}"


def route_section(line: Line, P: dict, k: int) -> dict:
    """Route section k on its own grid; save the result (alignment, curves, pieces, crossings)."""
    import json

    sec = line_sections(line)[k]
    folder = _section_folder(line, k, sec)
    res = route(sec, P, cache=folder)
    out = {"alignment": res["alignment"].tolist(), "curves": res["curves"], "measured": res["measured"],
           "public_land_crossed": res["public_land_crossed"], "stations": [s.id for s in res["stations"]]}
    (folder / "section_result.json").write_text(json.dumps(out), encoding="utf-8")
    return res


def route_sections(line: Line, P: dict, reuse: bool = False) -> dict:
    """Route a long line section by section and join them at the split stations: one alignment, the
    pieces in order (waypoint ids prefixed by section), curve stats summed, crossings merged."""
    import json

    secs = line_sections(line)
    parts = []
    for k, sec in enumerate(secs):
        path = _section_folder(line, k, sec) / "section_result.json"
        if not (reuse and path.exists()):
            route_section(line, P, k)
        parts.append(json.loads(path.read_text(encoding="utf-8")))
    align = np.vstack([np.array(parts[0]["alignment"])] + [np.array(r["alignment"])[1:] for r in parts[1:]])
    measured = []
    for k, r in enumerate(parts):
        for piece in r["measured"]:
            piece = dict(piece)
            for end in ("from", "to"):
                if isinstance(piece[end], dict):
                    piece[end] = {**piece[end], "id": f"s{k}_{piece[end]['id']}"}
            measured.append(piece)
    cs = [r["curves"] for r in parts]
    curves = {"r_cruise_m": cs[0]["r_cruise_m"], "r_urban_m": cs[0]["r_urban_m"], "sections": len(cs),
              "split_at": list(line.gis_split_at),
              **{k: sum(c[k] for c in cs) for k in ("vertices", "vertices_removed_for_curves", "refinement_moves",
                                                    "cost_least_cost_path_musd", "cost_smoothed_musd")},
              "all_curves_fit": all(c["all_curves_fit"] for c in cs)}
    km: dict[tuple[str, str], float] = {}
    for r in parts:
        for c in r["public_land_crossed"]:
            km[(c["kind"], c["name"])] = km.get((c["kind"], c["name"]), 0.0) + c["km"]
    crossed = sorted(({"kind": k, "name": n, "km": round(v, 2)} for (k, n), v in km.items()),
                     key=lambda c: (PUBLIC_KINDS.index(c["kind"]), -c["km"]))
    return {"grid": None, "alignment": align, "curves": curves, "measured": measured,
            "stations": [p for p in line.points if p.is_station], "public_land_crossed": crossed}
