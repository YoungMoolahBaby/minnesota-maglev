"""Climate normals for the US corridor screen's climate zones (params/climate.yaml).

Data: NOAA NCEI U.S. Climate Normals 1991-2020, monthly, per station
(https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/access/<GHCN id>.csv): mean temperature
(MLY-TAVG-NORMAL, degF) and snowfall (MLY-SNOW-NORMAL, inches) where the station measures it.

Per station: Nov-Mar and Apr-Oct mean temperature (degC, the model's winter / summer seasons) and
annual snowfall (cm). Writes reference/climate_screen.yaml (small, committed); raw CSVs stay in
data/raw/noaa_normals (gitignored).

Usage: uv run python scripts/climate_normals.py
"""

from __future__ import annotations

import csv
import io
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/access/{id}.csv"
# ASOS id -> (climate zone, GHCN-Daily id of the same airport's first-order station)
STATIONS = {
    "DFW": ("texas", "USW00003927"), "IAH": ("texas", "USW00012960"), "AUS": ("texas", "USW00013904"),
    "SJC": ("california", "USW00023293"), "FAT": ("california", "USW00093193"), "LAX": ("california", "USW00023174"),
    "LAS": ("mojave", "USW00023169"), "DAG": ("mojave", "USW00023161"),
    "BWI": ("northeast", "USW00093721"), "PHL": ("northeast", "USW00013739"),
    "LGA": ("northeast", "USW00014732"), "BOS": ("northeast", "USW00014739"),
    "ATL": ("piedmont", "USW00013874"), "GSP": ("piedmont", "USW00003870"), "CLT": ("piedmont", "USW00013881"),
    "MIA": ("florida", "USW00012839"), "MCO": ("florida", "USW00012815"), "TPA": ("florida", "USW00012842"),
    "SEA": ("cascadia", "USW00024233"), "PDX": ("cascadia", "USW00024229"),
    "ORD": ("great_lakes", "USW00094846"), "DTW": ("great_lakes", "USW00094847"),
}
WINTER = (11, 12, 1, 2, 3)


def fetch(ghcn: str, raw: Path) -> str:
    path = raw / f"{ghcn}.csv"
    if not path.exists() or path.stat().st_size < 500:
        req = urllib.request.Request(URL.format(id=ghcn), headers={"User-Agent": "minnesota-maglev climate"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
        time.sleep(0.5)
    return path.read_text(encoding="utf-8")


def _num(v: str) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x <= -7777 else x


def station(text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    tavg = {int(r["month"]): _num(r.get("MLY-TAVG-NORMAL")) for r in rows}
    snow = {int(r["month"]): _num(r.get("MLY-SNOW-NORMAL")) for r in rows}
    c = lambda f: (f - 32) / 1.8  # noqa: E731
    win = [tavg[m] for m in WINTER if tavg.get(m) is not None]
    summ = [tavg[m] for m in range(4, 11) if tavg.get(m) is not None]
    out = {"name": rows[0].get("NAME", ""),
           "winter_mean_temp_c": round(c(sum(win) / len(win)), 1) if len(win) == 5 else None,
           "summer_mean_temp_c": round(c(sum(summ) / len(summ)), 1) if len(summ) == 7 else None}
    if all(snow.get(m) is not None for m in range(1, 13)):
        out["snowfall_in"] = round(sum(snow.values()), 1)
        out["snowfall_cm"] = round(sum(snow.values()) * 2.54)
    else:
        out["snowfall_in"] = out["snowfall_cm"] = None
    return out


def main() -> None:
    raw = ROOT / "data" / "raw" / "noaa_normals"
    raw.mkdir(parents=True, exist_ok=True)
    result = {}
    for st, (zone, ghcn) in STATIONS.items():
        try:
            result[st] = {"zone": zone, "ghcn": ghcn, **station(fetch(ghcn, raw))}
        except OSError as e:
            result[st] = {"zone": zone, "ghcn": ghcn, "error": str(e)}
        print(st, result[st])
    header = ("# NOAA NCEI U.S. Climate Normals 1991-2020 (monthly), written by scripts/climate_normals.py.\n"
              "# winter = Nov-Mar mean of monthly TAVG, summer = Apr-Oct; snowfall = sum of monthly normals.\n")
    out = ROOT / "reference" / "climate_screen.yaml"
    out.write_text(header + yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
