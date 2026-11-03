"""Icing hours and icing nights in Minnesota from hourly ASOS weather reports (2006-2025).

Data: NWS / FAA ASOS routine hourly METAR reports (the observations behind NOAA's hourly records),
fetched from the Iowa Environmental Mesonet archive (mesonet.agron.iastate.edu, request/asos.py),
which serves them as CSV with temperature and present-weather codes.

Counts per station and year (local time, America/Chicago):
  freezing_precip  freezing rain or drizzle (FZRA, FZDZ)
  ice_pellets      PL
  freezing_fog     FZFG (rime icing)
  unknown_precip   UP at <= +1 C (ASOS reports UP for mixed / freezing precipitation it can't classify)
  wet_snow         snow (SN, not freezing rain) at -2..+1 C, the sticky kind
  icing            any of the above in that hour
  icing_nights     nights (18:00-06:00) with at least one icing hour, when overnight warming runs
  fz_nights        nights with freezing rain or drizzle only (strict)

Usage: uv run python scripts/icing_hours.py [--years 2006 2025] [--raw data/raw/noaa_asos]
Writes reference/icing.yaml (small, committed). Raw CSVs stay in data/raw (gitignored).
"""

from __future__ import annotations

import argparse
import csv
import io
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
STATIONS = {"DLH": "north", "MSP": "central", "STC": "central", "RST": "south"}
URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st}&data=tmpf&data=wxcodes"
       "&year1={y}&month1=1&day1=1&year2={y2}&month2=1&day2=1&tz=America/Chicago&format=onlycomma"
       "&latlon=no&missing=M&trace=T&direct=no&report_type=3")


def fetch(st: str, year: int, raw: Path) -> Path:
    path = raw / f"{st}_{year}.csv"
    if not path.exists() or path.stat().st_size < 1000:
        req = urllib.request.Request(URL.format(st=st, y=year, y2=year + 1),
                                     headers={"User-Agent": "minnesota-maglev icing study"})
        with urllib.request.urlopen(req, timeout=300) as r:
            path.write_bytes(r.read())
        time.sleep(1.0)  # be gentle with the archive
    return path


def classify(tmpf: str, wx: str) -> set[str]:
    if wx in ("M", ""):
        return set()
    try:
        tc = (float(tmpf) - 32) / 1.8
    except ValueError:
        tc = None
    tokens = wx.split()
    out = set()
    for t in tokens:
        core = t.lstrip("+-")
        if "FZRA" in core or "FZDZ" in core:
            out.add("freezing_precip")
        if "PL" in core:
            out.add("ice_pellets")
        if "FZFG" in core:
            out.add("freezing_fog")
        if "UP" in core and tc is not None and tc <= 1.0:
            out.add("unknown_precip")
        if "SN" in core and "FZ" not in core and tc is not None and -2.0 <= tc <= 1.0:
            out.add("wet_snow")
    if out:
        out.add("icing")
    return out


def station_year(path: Path) -> dict:
    hours = defaultdict(set)  # category -> set of local hours
    for row in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8", errors="replace"))):
        if not row.get("valid"):
            continue
        t = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M")
        key = t.replace(minute=0)
        for c in classify(row.get("tmpf", "M"), row.get("wxcodes", "M")):
            hours[c].add(key)
    out = {c: len(h) for c, h in hours.items()}

    def nights(cat: str) -> int:
        n = set()
        for h in hours.get(cat, ()):
            if h.hour >= 18:
                n.add(h.date())
            elif h.hour < 6:
                n.add((h - timedelta(days=1)).date())
        return len(n)

    out["icing_nights"] = nights("icing")
    out["fz_nights"] = nights("freezing_precip")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs=2, type=int, default=[2006, 2025])
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw" / "noaa_asos"))
    ap.add_argument("--out", default=str(ROOT / "reference" / "icing.yaml"))
    args = ap.parse_args()
    raw = Path(args.raw)
    raw.mkdir(parents=True, exist_ok=True)
    cats = ["freezing_precip", "ice_pellets", "freezing_fog", "unknown_precip", "wet_snow", "icing",
            "icing_nights", "fz_nights"]
    result = {}
    for st, zone in STATIONS.items():
        per_year = {}
        for y in range(args.years[0], args.years[1] + 1):
            per_year[y] = station_year(fetch(st, y, raw))
            print(st, y, per_year[y].get("icing", 0), "icing h,", per_year[y].get("icing_nights", 0), "nights")
        summary = {}
        for c in cats:
            v = np.array([per_year[y].get(c, 0) for y in per_year], dtype=float)
            summary[c] = {"mean": round(float(v.mean()), 1), "p10": round(float(np.percentile(v, 10)), 1),
                          "p90": round(float(np.percentile(v, 90)), 1), "max": int(v.max())}
        result[st] = {"zone": zone, "years": f"{args.years[0]}-{args.years[1]}", "summary": summary,
                      "per_year": {y: {c: per_year[y].get(c, 0) for c in cats} for y in per_year}}
    header = (
        "# Icing hours and nights per year from hourly ASOS reports (NWS/FAA; via the Iowa Environmental\n"
        "# Mesonet archive), written by scripts/icing_hours.py. Local time. Categories in the script's\n"
        "# docstring. 'icing' = any icing condition in the hour; icing_nights = 18:00-06:00 windows with one.\n"
    )
    Path(args.out).write_text(header + yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
