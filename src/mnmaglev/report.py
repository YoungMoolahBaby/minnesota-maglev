"""Run the network, Monte Carlo the costs, and write report.md, results.json and map.html."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

from .benchmarks import benchmark_table
from .costs import curve_radius_note, line_capital, line_materials, line_operating
from .kinematics import line_summary
from .network import Line
from .params import Param, nominal, sample


def _pct(x) -> dict[str, float]:
    a = np.asarray(x, dtype=float)
    return {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)),
            "p90": float(np.percentile(a, 90))}


def _ranks(a: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(a)).astype(float)


def sensitivity(params: dict[str, Param], samples: dict[str, np.ndarray], total: np.ndarray, top: int = 12):
    """Spearman rank correlation of each varying parameter with the total."""
    rt = _ranks(total)
    out = []
    for k, p in params.items():
        if not p.varies:
            continue
        r = np.corrcoef(_ranks(samples[k]), rt)[0, 1]
        if np.isfinite(r):
            out.append((k, float(r), p.conf))
    out.sort(key=lambda t: -abs(t[1]))
    return out[:top]


def run_network(lines: list[Line], params: dict[str, Param], n: int = 5000, seed: int = 1,
                local_supply: bool = False) -> dict:
    P0 = nominal(params)
    PS = sample(params, n, seed)
    seen: set[str] = set()
    results = []
    net_total = np.zeros(n)
    for line in sorted(lines, key=lambda l: l.phase):
        new = [c for c in line.stations if c.id not in seen]
        seen |= {c.id for c in new}
        kin = line_summary(line, P0)
        cap0 = line_capital(line, P0, new, kin["end_to_end_s"], local_supply)
        capS = line_capital(line, PS, new, kin["end_to_end_s"], local_supply)
        alt = line_capital(line, PS, new, kin["end_to_end_s"], not local_supply)["total"]
        local_saving = (alt - capS["total"]) if local_supply else (capS["total"] - alt)
        lease0 = cap0["reserve"]["lease_income"] if line.reserve else 0.0
        leaseS = capS["reserve"]["lease_income"] if line.reserve else 0.0
        ops0 = line_operating(line, P0, cap0["trains"], kin["kwh_per_train_km"], lease0)
        opsS = line_operating(line, PS, capS["trains"], kin["kwh_per_train_km"], leaseS)
        net_total = net_total + capS["total"]
        results.append({
            "line": line, "new_stations": new, "kin": kin,
            "cap0": cap0, "capS": capS, "ops0": ops0, "opsS": opsS,
            "materials": line_materials(line, P0, local_supply),
            "local_saving": local_saving,
        })
    return {
        "P0": P0, "results": results, "n": n, "seed": seed,
        "sensitivity": sensitivity(params, PS, net_total),
        "phase_totals": {
            ph: _pct(sum(r["capS"]["total"] for r in results if r["line"].phase <= ph))
            for ph in sorted({r["line"].phase for r in results})
        },
        "min_radius_m": curve_radius_note(P0),
        "benchmarks": benchmark_table(params),
        "conf_counts": Counter(p.conf for p in params.values()),
        "local_supply": local_supply,
    }


def _hm(seconds: float) -> str:
    m = int(round(seconds / 60))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


def _bn(musd: float) -> str:
    return f"${musd / 1000:,.1f} bn"


def write_markdown(net: dict, path: Path) -> None:
    R = net["results"]
    L = []
    variant = net.get("variant")
    L.append("# Minnesota maglev: network estimate" + (f" (variant: {variant})" if variant else "") + "\n")
    L.append(f"Generated {date.today().isoformat()} by `mnmaglev report` "
             f"({net['n']:,} Monte Carlo samples, seed {net['seed']}). USD 2026.\n")
    L.append(f"Local supply policy: **{'on' if net.get('local_supply') else 'off'}** "
             "(network/lines.yaml settings.local_supply; `--local-supply on|off` overrides).\n")
    cc = net["conf_counts"]
    L.append("> Concept-stage numbers. Parameters by confidence: "
             + ", ".join(f"{k} {cc.get(k, 0)}" for k in ("high", "medium", "low", "placeholder"))
             + ". Segment shares (structure, land, floodplain, peat) are planner estimates until the "
               "GIS phase measures them. See docs/RESEARCH.md for what to firm up first.\n")

    L.append("## Lines\n")
    L.append("| Line | Phase | Route km | Stations (new) | End to end | Capital P10 / P50 / P90 | P50 per km | Opex P50 / yr | Second-system reserve P50 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in R:
        line, cs, os_ = r["line"], _pct(r["capS"]["total"]), _pct(r["opsS"]["total"])
        rs = _pct(r["capS"]["reserve"]["total"])["p50"]
        held = "held, in total" if line.reserve else "not held"
        L.append(
            f"| {line.name} | {line.phase} | {line.length_km:,.0f} | {len(line.stations)} ({len(r['new_stations'])}) "
            f"| {_hm(r['kin']['end_to_end_s'])} | {_bn(cs['p10'])} / {_bn(cs['p50'])} / {_bn(cs['p90'])} "
            f"| ${cs['p50'] / line.length_km:,.0f} M | ${os_['p50']:,.0f} M "
            f"| {_bn(rs)} ({rs / _pct(r['capS']['total_without_reserve'])['p50']:.1%}), {held} |"
        )
    L.append("")
    L.append("**Second-system reserve**: land beside each line for a next-generation system, plus "
             "build-for-two provisions at urban structures, long bridges and stations (params: "
             "`land.reserve.*`, `costs.reserve.*`), so system B can be built while A keeps running. "
             "Lines opt in with `reserve_second_system: true` in network/lines.yaml.")
    held = [r for r in R if r["line"].reserve]
    other = [r for r in R if not r["line"].reserve]
    if held:
        L.append(f"Held on {', '.join(r['line'].id for r in held)}: P50 "
                 f"{_bn(_pct(sum(r['capS']['reserve']['total'] for r in held))['p50'])}, "
                 f"lease income {sum(float(r['cap0']['reserve']['lease_income']) for r in held):,.1f} MUSD/yr (nominal).")
    if other:
        L.append(f"Holding it on the other lines too would add P50 "
                 f"{_bn(_pct(sum(r['capS']['reserve']['total'] for r in other))['p50'])}.")
    L.append("")
    L.append("Stations shared between lines are costed once, on the earliest phase. Cumulative network capital:\n")
    for ph, t in net["phase_totals"].items():
        L.append(f"- through phase {ph}: {_bn(t['p10'])} / **{_bn(t['p50'])}** / {_bn(t['p90'])} (P10 / P50 / P90)")
    L.append("")

    L.append("## What drives the uncertainty\n")
    L.append("Rank correlation of each parameter with total network capital. Research the top rows first.\n")
    L.append("| Parameter | Correlation | Confidence |")
    L.append("|---|---|---|")
    for k, rho, conf in net["sensitivity"]:
        L.append(f"| `{k}` | {rho:+.2f} | {conf} |")
    L.append("")
    L.append("## Benchmarks\n")
    L.append("Sourced figures behind the cost parameters (reference/benchmarks.yaml), converted to 2026 USD "
             "with the FHWA construction index and adjusted to each parameter's scope. `allin_per_km` rows "
             "are whole projects (incl. trains, stations, soft costs) to compare with the P50 per km above.\n")
    L.append(net["benchmarks"])
    L.append("")
    L.append(f"Smallest curve radius at cruise speed: **{net['min_radius_m']:,.0f} m** "
             "(12 deg cant + unbalanced lateral limit); the route search must respect it.\n")

    for r in R:
        line, c0 = r["line"], r["cap0"]
        L.append(f"## {line.name} (phase {line.phase})\n")
        if line.note:
            L.append(f"{line.note}\n")
        L.append("| Leg | km | Time | Avg km/h | kWh per trip, winter / summer |")
        L.append("|---|---|---|---|---|")
        for leg in r["kin"]["legs"]:
            L.append(f"| {leg.start} -> {leg.end} | {leg.length_km:,.0f} | {_hm(leg.time_s)} "
                     f"| {leg.length_km / (leg.time_s / 3600):,.0f} | {leg.energy_kwh_winter:,.0f} / {leg.energy_kwh_summer:,.0f} |")
        L.append(f"\nEnergy: {r['kin']['kwh_per_train_km']:,.1f} kWh per train-km (year-weighted). "
                 f"Fleet: {int(c0['trains'])} trains.\n")
        L.append("Capital breakdown with every parameter at its most likely value (MUSD). This sum lands "
                 "near or below the P10: the ranges are skewed high, so stacking most-likely values is "
                 "optimistic (the classic megaproject trap). Plan with the P50 and P90 above.\n")
        L.append("| Item | MUSD |")
        L.append("|---|---|")
        for k in ("guideway", "adders", "systems", "stations", "switches", "depot", "vehicles",
                  "soft", "land", "wetlands", "contingency"):
            L.append(f"| {k} | {float(c0[k]):,.0f} |")
        rv = c0["reserve"]
        L.append(f"| second-system reserve ({'held' if line.reserve else 'not held'}) "
                 f"| {float(rv['total']) if line.reserve else 0:,.0f} |")
        L.append(f"| **total** | **{float(c0['total']):,.0f}** |")
        L.append("")
        L.append(f"Second-system reserve on this line ({'held' if line.reserve else 'priced, not held'}), "
                 f"most likely values: {float(rv['acres']):,.0f} acres, land {float(rv['land']):,.0f}, "
                 f"urban provision {float(rv['urban_provision']):,.0f}, bridge provision {float(rv['bridge_provision']):,.0f}, "
                 f"station provision {float(rv['station_provision']):,.0f}, review {float(rv['review']):,.0f}, "
                 f"contingency {float(rv['contingency']):,.0f} = **{float(rv['total']):,.0f} MUSD**; "
                 f"farm lease income {float(rv['lease_income']):,.2f} MUSD/yr.\n")
        L.append("| Segment | km | Elevated | At grade | Urban viaduct | Tunnel | Bridges m | Acres | Wetland acres filled |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for s, sc in zip(line.segments, c0["segments"]):
            q = sc["quantities"]
            L.append(f"| {s.a.id} -> {s.b.id} | {q['route_km']:,.0f} | {q['elevated_km']:,.0f} | {q['at_grade_km']:,.0f} "
                     f"| {q['urban_viaduct_km']:,.1f} | {q['tunnel_km']:,.1f} | {q['bridge_m']:,.0f} "
                     f"| {sc['acres']:,.0f} | {sc['wetland_acres_filled']:,.1f} |")
        L.append("")

    L.append("## Materials and the ore behind them (nominal)\n")
    L.append("Steel = rebar + prestressing strand + stator electrical steel + guidance rails. "
             "Ore assumes Mesabi taconite pellets and Duluth Complex copper grades (params/materials.yaml).\n")
    keys = [k for k in R[0]["materials"] if k.endswith(("_t", "_m3")) and not k.startswith("mn_")]
    L.append("| Line | " + " | ".join(keys) + " |")
    L.append("|---|" + "---|" * len(keys))
    tot = Counter()
    for r in R:
        tot.update({k: r["materials"][k] for k in keys})
        L.append(f"| {r['line'].id} | " + " | ".join(f"{r['materials'][k]:,.0f}" for k in keys) + " |")
    L.append("| **all** | " + " | ".join(f"**{tot[k]:,.0f}**" for k in keys) + " |")
    L.append("")

    L.append("### Materials bill (nominal, MUSD)\n")
    L.append("What the materials themselves cost at delivered 2026 prices (`materials.prices.*`). They are "
             "already inside the guideway and systems costs; this shows how small a slice they are.\n")
    bkeys = list(R[0]["materials"]["bill_musd"])
    L.append("| Line | " + " | ".join(bkeys) + " | share of construction |")
    L.append("|---|" + "---|" * (len(bkeys) + 1))
    btot = Counter()
    ctot = 0.0
    for r in R:
        b = r["materials"]["bill_musd"]
        btot.update(b)
        ctot += float(r["cap0"]["construction"])
        L.append(f"| {r['line'].id} | " + " | ".join(f"{b[k]:,.0f}" for k in bkeys)
                 + f" | {b['total'] / float(r['cap0']['construction']):.1%} |")
    L.append("| **all** | " + " | ".join(f"**{btot[k]:,.0f}**" for k in bkeys) + f" | **{btot['total'] / ctot:.1%}** |")
    L.append("")

    L.append("## Local supply: Minnesota mines, plants and contracts\n")
    on = net.get("local_supply")
    L.append(f"Policy **{'on' if on else 'off'}**. Minnesota-made guideway beams and stator packs, taconite "
             "aggregate on north-zone segments, and long-term supply contracts (`costs.local_supply.*`). "
             "Savings are P50 differences in total capital, then the nominal breakdown before soft costs "
             "and contingency. The production tax is state revenue on Minnesota pellets in the project's steel.\n")
    L.append("| Line | Saving P50 (MUSD) | Beam plant | Stator plant | Tailings aggregate | Contingency points | "
             "Tailings used (t) | MN pellets (t) | MN production tax (MUSD) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    sav_tot = 0.0
    tax_tot = 0.0
    for r in R:
        ls, mat = r["cap0"]["local_supply"], r["materials"]
        sav = float(np.percentile(r["local_saving"], 50))
        sav_tot += sav
        tax_tot += float(mat["mn_production_tax_musd"])
        L.append(f"| {r['line'].id} | {sav:,.0f} | {float(ls['beam_plant']):,.0f} | {float(ls['stator_plant']):,.0f} "
                 f"| {float(ls['tailings']):,.1f} | {float(ls['contingency_points']):.3f} | {float(ls['tailings_t']):,.0f} "
                 f"| {float(mat['mn_pellets_t']):,.0f} | {float(mat['mn_production_tax_musd']):,.1f} |")
    L.append(f"\nNetwork: local supply saves ~**${sav_tot / 1000:,.1f} bn** P50 (sum of line medians) and pays "
             f"~${tax_tot:,.1f} M in taconite production tax to the Range.\n")
    path.write_text("\n".join(L), encoding="utf-8")


def write_json(net: dict, path: Path) -> None:
    out = {"generated": date.today().isoformat(), "n": net["n"], "seed": net["seed"],
           "min_radius_m": net["min_radius_m"], "phase_totals_musd": net["phase_totals"],
           "sensitivity": net["sensitivity"], "lines": []}
    for r in net["results"]:
        line = r["line"]
        out["lines"].append({
            "id": line.id, "name": line.name, "phase": line.phase, "route_km": line.length_km,
            "points": [p.id for p in line.points],
            "end_to_end_s": r["kin"]["end_to_end_s"],
            "kwh_per_train_km": r["kin"]["kwh_per_train_km"],
            "capital_musd": _pct(r["capS"]["total"]), "opex_musd_per_year": _pct(r["opsS"]["total"]),
            "reserve_held": line.reserve, "reserve_musd": _pct(r["capS"]["reserve"]["total"]),
            "nominal_capital_musd": {k: float(v) for k, v in r["cap0"].items()
                                     if k not in ("segments", "reserve", "reserve_included", "local_supply", "local_supply_included")},
            "materials": r["materials"],
            "local_supply_saving_musd": _pct(r["local_saving"]),
        })
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


PHASE_COLOURS = {1: "#c0392b", 2: "#2471a3", 3: "#7f8c8d"}


def write_map(net: dict, path: Path) -> None:
    feats = []
    stations = {}
    for r in net["results"]:
        line = r["line"]
        cs = _pct(r["capS"]["total"])
        feats.append({
            "name": line.name, "phase": line.phase, "colour": PHASE_COLOURS.get(line.phase, "#333"),
            "coords": [[p.lat, p.lon] for p in line.points],
            "popup": f"<b>{line.name}</b><br>phase {line.phase}, {line.length_km:,.0f} km, "
                     f"{_hm(r['kin']['end_to_end_s'])} end to end<br>capital P50 {_bn(cs['p50'])} "
                     f"(P10 {_bn(cs['p10'])}, P90 {_bn(cs['p90'])})",
        })
        for p in line.stations:
            stations[p.id] = {"name": p.name, "lat": p.lat, "lon": p.lon, "type": p.type}
    html = MAP_TEMPLATE.replace("__LINES__", json.dumps(feats)).replace("__STATIONS__", json.dumps(list(stations.values())))
    path.write_text(html, encoding="utf-8")


MAP_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Minnesota maglev network</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{height:100%;margin:0}
.legend{background:#fff;padding:8px 10px;font:13px sans-serif;border-radius:4px}</style></head>
<body><div id="map"></div><script>
const lines = __LINES__, stations = __STATIONS__;
const map = L.map('map').setView([45.6, -93.5], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 18, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);
for (const l of lines) {
  L.polyline(l.coords, {color: l.colour, weight: l.phase === 1 ? 6 : 4,
    dashArray: l.phase === 3 ? '8 6' : null}).bindPopup(l.popup).addTo(map);
}
for (const s of stations) {
  L.circleMarker([s.lat, s.lon], {radius: s.type === 'terminal_major' ? 8 : 6,
    color: '#111', fillColor: '#fff', fillOpacity: 1, weight: 2}).bindTooltip(s.name).addTo(map);
}
const legend = L.control({position: 'bottomleft'});
legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend');
  d.innerHTML = '<b>Phase</b><br><span style="color:#c0392b">&#9644;</span> 1 spine<br>' +
    '<span style="color:#2471a3">&#9644;</span> 2<br><span style="color:#7f8c8d">&#9644;</span> 3 (future)<br>' +
    '<small>straight lines between points;<br>real alignments come from the GIS phase</small>'; return d; };
legend.addTo(map);
</script></body></html>
"""
