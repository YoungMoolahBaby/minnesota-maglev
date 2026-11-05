"""`mnmaglev demand-data`: build the base travel market (network/demand_base.yaml) from public data.

Downloads (cached in data/raw/demand/, public domain US government data, see docs/SOURCES.md):
- FHWA NextGen NHTS National Passenger OD, 2022 annual (trips between 583 zones by mode and
  distance band, from passive location data).
- FHWA county -> NextGen OD zone lookup (Revised_County_fhwa583_UMD).
- Census Vintage 2025 population estimates: counties (zone populations), CBSAs (market
  populations) and Minnesota sub-county places (the Iron Range).

For every pair of markets in network/markets.yaml it writes the 2022 trips at least `min_miles` long
(both directions), by mode, the work share, and each market's population and share of its zone.
"""

from __future__ import annotations

import csv
import io
import itertools
import struct
import time
import urllib.request
import zipfile
from pathlib import Path

import yaml

from . import NETWORK_DIR, ROOT

RAW = ROOT / "data" / "raw" / "demand"
URLS = {
    "od": "https://nhts.ornl.gov/od/assets/data/2022_Passenger_OD_Annual.zip",
    "zones": "https://www.fhwa.dot.gov/policyinformation/analysisframework/zip/Revised_County_fhwa583_UMD.zip",
    "counties": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv",
    "cbsa": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv",
    "places_27": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/totals/sub-est2025_27.csv",
}
BANDS = [(0, 10), (10, 25), (25, 50), (50, 75), (75, 100), (100, 150), (150, 300), (300, 10_000)]
BAND_COLS = ["0_10", "10_25", "25_50", "50_75", "75_100", "100_150", "150_300", "gt300"]
MODES = ("air", "rail", "vehicle")


def _get(key: str) -> Path:
    url = URLS[key]
    path = RAW / url.rsplit("/", 1)[1]
    if path.exists() and path.stat().st_size > 1000:
        return path
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "minnesota-maglev demand"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                path.write_bytes(r.read())
            return path
        except OSError as e:
            print(f"  download failed (try {k + 1}): {e}", flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError(f"could not download {url}")


def _dbf_rows(data: bytes):
    """Rows of a dBASE III table as dicts of stripped strings (no extra dependencies)."""
    n, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode()
        fields.append((name, data[pos + 16]))
        pos += 32
    for i in range(n):
        rec = data[header_len + i * record_len: header_len + (i + 1) * record_len]
        out, p = {}, 1
        for name, length in fields:
            out[name] = rec[p:p + length].decode("latin-1").strip()
            p += length
        yield out


def _csv(path: Path):
    return csv.DictReader(io.StringIO(path.read_bytes().decode("latin-1")))


def county_zones() -> dict[str, str]:
    """County FIPS (5 digits) -> NextGen OD zone id, e.g. '27109' -> '40340_MN'."""
    with zipfile.ZipFile(_get("zones")) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".dbf"))
        rows = _dbf_rows(z.read(name))
        return {r["STATEFP"] + r["COUNTY_FIP"]: f"{r['CBSAFP2']}_{r['STATE_ABB']}" for r in rows}


def populations(markets: dict) -> tuple[dict[str, int], dict[str, int], dict[str, list[str]]]:
    """2025 populations: of each market, of each zone, and the counties behind each CBSA market."""
    county_pop = {r["STATE"] + r["COUNTY"]: int(r["POPESTIMATE2025"])
                  for r in _csv(_get("counties")) if r["SUMLEV"] == "050"}
    zones = county_zones()
    zone_pop: dict[str, int] = {}
    for fips, z in zones.items():
        zone_pop[z] = zone_pop.get(z, 0) + county_pop.get(fips, 0)
    cbsa_pop, cbsa_counties = {}, {}
    for r in _csv(_get("cbsa")):
        if r["LSAD"] in ("Metropolitan Statistical Area", "Micropolitan Statistical Area"):
            cbsa_pop[r["CBSA"]] = int(r["POPESTIMATE2025"])
        elif r["LSAD"] == "County or equivalent":
            cbsa_counties.setdefault(r["CBSA"], []).append(r["STCOU"])
    places = {(r["STATE"], r["NAME"]): int(r["POPESTIMATE2025"])
              for r in _csv(_get("places_27")) if r["SUMLEV"] == "162"}
    pop: dict[str, int] = {}
    for mid, m in markets.items():
        if "places" in m:
            pop[mid] = sum(places[(m["state"], f"{p} city")] for p in m["places"])
        else:
            pop[mid] = cbsa_pop[m["cbsa"]]
    for mid, m in markets.items():
        for other in m.get("less", []):
            pop[mid] -= pop[other]
    # check: a CBSA market's counties should all lie in the market's zones
    counties = {mid: cbsa_counties.get(m.get("cbsa", ""), []) for mid, m in markets.items()}
    for mid, m in markets.items():
        stray = [c for c in counties[mid] if zones.get(c) not in m["zones"]]
        if stray:
            print(f"  note: {mid}: counties {stray} lie in zones {[zones.get(c) for c in stray]}, not {m['zones']}")
    return pop, zone_pop, counties


def od_pairs(markets: dict) -> dict[tuple[str, str], dict]:
    """2022 trips between the zones our markets use (both directions summed), by distance band and mode."""
    wanted = {z for m in markets.values() for z in m["zones"]}
    out: dict[tuple[str, str], dict] = {}
    with zipfile.ZipFile(_get("od")) as z:
        name = next(n for n in z.namelist() if n.endswith("_Data.csv"))
        with z.open(name) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                a, b = r["origin_zone_id"], r["destination_zone_id"]
                if a not in wanted or b not in wanted:
                    continue
                key = tuple(sorted((a, b)))
                d = out.setdefault(key, {"bands": [0.0] * len(BANDS), "work": [0.0] * len(BANDS),
                                         **{m: [0.0] * len(BANDS) for m in MODES}})
                for i, c in enumerate(BAND_COLS):
                    d["bands"][i] += float(r[f"distance_{c}"])
                    d["work"][i] += float(r[f"work_{c}mi"])
                    for m in MODES:
                        d[m][i] += float(r.get(f"{m}_{c}mi") or 0.0)
    return out


def build_base(min_miles: float, markets: dict, pairs: list[tuple[str, str]] | None = None) -> dict:
    """Trips by distance band (from min_miles up) and mode between pairs of markets in different
    zones (all pairs unless given); the model runs its mode choice per band, so a 30-mile exurb trip
    across a zone border gets a 30-mile car trip and no maglev, and no cutoff rule is needed."""
    pop, zone_pop, _ = populations(markets)
    od = od_pairs(markets)
    first = next(i for i, (lo, _) in enumerate(BANDS) if lo >= min_miles)

    mk = {}
    for mid, m in markets.items():
        zp = sum(zone_pop.get(z, 0) for z in m["zones"])
        mk[mid] = {"population": pop[mid], "zone_population": zp, "zone_share": round(min(pop[mid] / zp, 1.0), 4)}
    trips = {}
    for a, b in pairs if pairs is not None else itertools.combinations(markets, 2):
        if set(markets[a]["zones"]) & set(markets[b]["zones"]):
            continue  # inside one zone: the gravity model estimates it
        share = mk[a]["zone_share"] * mk[b]["zone_share"]
        tot = {k: [0.0] * (len(BANDS) - first) for k in ("all", "work", *MODES)}
        for x, y in itertools.product(markets[a]["zones"], markets[b]["zones"]):
            d = od.get(tuple(sorted((x, y))))
            if d:
                for k, src in (("all", d["bands"]), ("work", d["work"]), *((m, d[m]) for m in MODES)):
                    for i in range(first, len(BANDS)):
                        tot[k][i - first] += src[i]
        trips[f"{a}|{b}"] = {k: [round(v * share) for v in vals] for k, vals in tot.items()}
    return {
        "source": ("FHWA NextGen NHTS National Passenger OD 2022 (annual trips, both directions, by distance "
                   "band and mode), split to markets by 2025 population share of each zone; Census Vintage 2025 "
                   "estimates (CBSAs, counties, MN places). Built "
                   f"on {time.strftime('%Y-%m-%d')}."),
        "bands_miles": [list(b) for b in BANDS[first:]],
        "markets": mk,
        "trips_2022": trips,
    }


def build(min_miles: float = 10.0) -> Path:
    """network/demand_base.yaml for the Minnesota network's markets (network/markets.yaml)."""
    markets = yaml.safe_load((NETWORK_DIR / "markets.yaml").read_text(encoding="utf-8"))
    out = build_base(min_miles, markets)
    out["source"] = out["source"].replace("Built on", "Built by `mnmaglev demand-data` on")
    path = NETWORK_DIR / "demand_base.yaml"
    path.write_text("# Generated by `mnmaglev demand-data`; do not edit by hand.\n"
                    + yaml.safe_dump(out, sort_keys=False, width=110, default_flow_style=None), encoding="utf-8")
    return path
