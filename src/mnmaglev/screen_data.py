"""`mnmaglev screen-data`: measure the screen corridors' built-up km and build their travel market.

1. Built-up km: Census TIGER/Line 2023 urban areas (2020 criteria; public domain), sampled every
   250 m along the straight line between neighbouring points of each corridor line. The share of
   the samples inside an urban area, outside the stations' approach km, is the segment's built-up
   share (priced as urban viaduct, like the built-up km the GIS measures on Minnesota's lines).
   Written to network/screen/measured.yaml.
2. Travel market: the same NHTS 2022 OD build as `mnmaglev demand-data`, for the screen's markets
   (CBSAs; their NHTS zones found from the CBSA's counties), pairs within each corridor only.
   Written to network/screen/demand_base.yaml.
"""

from __future__ import annotations

import itertools
import struct
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import yaml

from . import NETWORK_DIR, ROOT
from .geo import haversine_km

UA_URL = "https://www2.census.gov/geo/tiger/TIGER2023/UAC/tl_2023_us_uac20.zip"
RAW = ROOT / "data" / "raw" / "screen"
SCREEN_DIR = NETWORK_DIR / "screen"
STEP_KM = 0.25


def _download(url: str, folder: Path) -> Path:
    path = folder / url.rsplit("/", 1)[1]
    if path.exists() and path.stat().st_size > 1000:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev screen"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                path.write_bytes(r.read())
            return path
        except OSError as e:
            print(f"  download failed (try {k + 1}): {e}", flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError(f"could not download {url}")


def shp_rings(data: bytes, bbox: tuple[float, float, float, float] | None = None) -> list[np.ndarray]:
    """Every ring of every polygon record in an ESRI shapefile (.shp bytes) as (n, 2) lon/lat
    arrays, keeping records whose bounding box meets bbox (xmin, ymin, xmax, ymax)."""
    rings = []
    pos = 100
    while pos + 8 <= len(data):
        _, words = struct.unpack(">ii", data[pos:pos + 8])
        content = data[pos + 8: pos + 8 + 2 * words]
        pos += 8 + 2 * words
        (shape_type,) = struct.unpack("<i", content[:4])
        if shape_type not in (5, 15, 25):  # polygon, polygonZ, polygonM
            continue
        xmin, ymin, xmax, ymax = struct.unpack("<4d", content[4:36])
        if bbox and (xmax < bbox[0] or xmin > bbox[2] or ymax < bbox[1] or ymin > bbox[3]):
            continue
        nparts, npoints = struct.unpack("<2i", content[36:44])
        parts = list(struct.unpack(f"<{nparts}i", content[44:44 + 4 * nparts])) + [npoints]
        start = 44 + 4 * nparts
        pts = np.frombuffer(content[start:start + 16 * npoints], dtype="<f8").reshape(npoints, 2)
        for a, b in zip(parts, parts[1:]):
            rings.append(pts[a:b])
    return rings


class UrbanAreas:
    """Point-in-urban-area test by the even-odd rule over all rings (outer rings and holes)."""

    def __init__(self, rings: list[np.ndarray]):
        from shapely import Polygon, STRtree

        self.polys = [Polygon(r) for r in rings if len(r) >= 4]
        self.tree = STRtree(self.polys)

    def inside(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        from shapely import points

        pts = points(np.column_stack([lon, lat]))
        idx_pt, _ = self.tree.query(pts, predicate="within")
        counts = np.bincount(idx_pt, minlength=len(pts))
        return counts % 2 == 1


def load_urban_areas(bbox) -> UrbanAreas:
    path = _download(UA_URL, RAW)
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".shp"))
        return UrbanAreas(shp_rings(z.read(name), bbox))


def built_up_share(a: dict, b: dict, ua: UrbanAreas, skip_a_km: float, skip_b_km: float) -> tuple[float, float]:
    """(share of the straight line from a to b inside urban areas, leaving out skip km at each end;
    straight-line km). a and b are dicts with lat and lon."""
    km = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    n = max(int(km / STEP_KM), 2)
    t = (np.arange(n) + 0.5) / n
    keep = (t * km >= skip_a_km) & ((1 - t) * km >= skip_b_km)
    if not keep.any():
        return 0.0, km
    lat = a["lat"] + (b["lat"] - a["lat"]) * t[keep]
    lon = a["lon"] + (b["lon"] - a["lon"]) * t[keep]
    return float(ua.inside(lon, lat).mean()), km


def measure(cfg: dict) -> Path:
    st = cfg["stations"]
    lats = [s["lat"] for s in st.values()]
    lons = [s["lon"] for s in st.values()]
    ua = load_urban_areas((min(lons) - 1, min(lats) - 1, max(lons) + 1, max(lats) + 1))
    out: dict = {}
    for cid, c in cfg["corridors"].items():
        for line in c["lines"]:
            segs = {}
            for a, b in zip(line["points"], line["points"][1:]):
                share, km = built_up_share(st[a], st[b], ua, st[a].get("approach_km", 0.0), st[b].get("approach_km", 0.0))
                segs[f"{a}-{b}"] = {"built_up_share": round(share, 4), "crow_km": round(km, 1)}
            out[line["id"]] = segs
            print(f"  {cid} {line['id']}: " + ", ".join(f"{k} {v['built_up_share']:.0%}" for k, v in segs.items()))
    path = SCREEN_DIR / "measured.yaml"
    path.write_text(
        "# Built-up share of each screen segment (Census TIGER/Line 2023 urban areas, 2020 criteria), outside\n"
        "# the stations' approach km, sampled every 250 m on the straight line. Written by `mnmaglev screen-data`.\n"
        + yaml.safe_dump(out, sort_keys=False), encoding="utf-8")
    return path


def screen_markets(cfg: dict) -> dict:
    """All screen markets (id -> {cbsa, stations, corridors}), merged across corridors."""
    out: dict = {}
    for cid, c in cfg["corridors"].items():
        for mid, m in c["markets"].items():
            e = out.setdefault(mid, {"cbsa": m["cbsa"], "stations": [], "corridors": []})
            if e["cbsa"] != m["cbsa"]:
                raise ValueError(f"market {mid}: CBSA {m['cbsa']} in {cid}, {e['cbsa']} elsewhere")
            e["stations"] = sorted(set(e["stations"]) | set(m["stations"]))
            e["corridors"].append(cid)
    return out


def demand_base(cfg: dict, min_miles: float = 10.0, min_zone_share: float = 0.05) -> Path:
    """NHTS trips between the markets of each corridor, by band and mode (network/screen/demand_base.yaml)."""
    from . import demand_data as dd

    markets = screen_markets(cfg)
    zones = dd.county_zones()
    county_pop = {r["STATE"] + r["COUNTY"]: int(r["POPESTIMATE2025"])
                  for r in dd._csv(dd._get("counties")) if r["SUMLEV"] == "050"}
    cbsa_counties: dict[str, list[str]] = {}
    for r in dd._csv(dd._get("cbsa")):
        if r["LSAD"] == "County or equivalent":
            cbsa_counties.setdefault(r["CBSA"], []).append(r["STCOU"])
    for mid, m in markets.items():
        by_zone: dict[str, int] = {}
        for c in cbsa_counties[m["cbsa"]]:
            if c in zones:
                by_zone[zones[c]] = by_zone.get(zones[c], 0) + county_pop.get(c, 0)
        total = sum(by_zone.values())
        m["zones"] = sorted(z for z, p in by_zone.items() if total and p / total >= min_zone_share)
        if not m["zones"]:
            raise ValueError(f"market {mid}: no NHTS zone for CBSA {m['cbsa']}")
    pairs = {tuple(sorted((a, b))) for c in cfg["corridors"].values() for a, b in itertools.combinations(c["markets"], 2)}
    out = dd.build_base(min_miles, {k: {"cbsa": v["cbsa"], "zones": v["zones"]} for k, v in markets.items()},
                        sorted(pairs))
    out["market_zones"] = {k: v["zones"] for k, v in markets.items()}
    path = SCREEN_DIR / "demand_base.yaml"
    path.write_text("# Generated by `mnmaglev screen-data`; do not edit by hand.\n"
                    + yaml.safe_dump(out, sort_keys=False, width=110, default_flow_style=None), encoding="utf-8")
    return path


def build(min_miles: float = 10.0) -> tuple[Path, Path]:
    from .screen import load_corridors

    cfg = load_corridors()
    return measure(cfg), demand_base(cfg, min_miles)
