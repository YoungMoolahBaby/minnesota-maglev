"""Run the network, Monte Carlo the costs, and write report.md, results.json and map.html."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

from . import ROOT
from .benchmarks import benchmark_table
from .costs import curve_radius_note, line_capital, line_materials, line_operating
from .fusion import fleet_money, size_by_phase
from .timetable import hub_times
from .security import capital as security_capital
from .security import charge_mw as security_charge_mw
from .security import fleet as security_fleet
from .security import operating as security_operating
from .winter import heating_mwh
from .kinematics import line_summary
from .network import Line
from .demand import network_demand
from .params import Param, nominal, sample


def _pct(x) -> dict[str, float]:
    a = np.asarray(x, dtype=float)
    return {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)),
            "p80": float(np.percentile(a, 80)), "p90": float(np.percentile(a, 90)), "mean": float(a.mean())}


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
                local_supply: bool = False, fusion: str = "none", heating: str = "none",
                security: str = "none") -> dict:
    P0 = nominal(params)
    PS = sample(params, n, seed)
    seen: set[str] = set()
    results = []
    net_total = np.zeros(n)
    for line in sorted(lines, key=lambda l: l.phase):
        new = [c for c in line.stations if c.id not in seen]
        seen |= {c.id for c in new}
        kin = line_summary(line, P0)
        cap0 = line_capital(line, P0, new, kin["end_to_end_s"], local_supply, heating, security)
        capS = line_capital(line, PS, new, kin["end_to_end_s"], local_supply, heating, security)
        alt = line_capital(line, PS, new, kin["end_to_end_s"], not local_supply, heating, security)["total"]
        local_saving = (alt - capS["total"]) if local_supply else (capS["total"] - alt)
        lease0 = cap0["reserve"]["lease_income"] if line.reserve else 0.0
        leaseS = capS["reserve"]["lease_income"] if line.reserve else 0.0
        ops0 = line_operating(line, P0, cap0["trains"], kin["kwh_per_train_km"], lease0,
                              heating_mwh(line, P0, heating), security)
        opsS = line_operating(line, PS, capS["trains"], kin["kwh_per_train_km"], leaseS,
                              heating_mwh(line, PS, heating), security)
        net_total = net_total + capS["total"]
        results.append({
            "line": line, "new_stations": new, "kin": kin,
            "cap0": cap0, "capS": capS, "ops0": ops0, "opsS": opsS,
            "materials": line_materials(line, P0, local_supply),
            "local_saving": local_saving,
        })
    # power supply: the fusion fleet, sized from the network's second-by-second peak
    sizing = size_by_phase([r["line"] for r in results], P0, heating, security)
    sizing_full = (size_by_phase([r["line"] for r in results], P0, "full", security) if heating != "full"
                   else sizing)
    fus0, fusS = fleet_money(sizing, P0), fleet_money(sizing, PS)
    own = fusion == "own"
    fusion_cum = {s["phase"]: sum(f["capital"] for f in fusS if f["phase"] <= s["phase"]) for s in sizing}
    if own:
        net_total = net_total + fusion_cum[max(fusion_cum)]
    return {
        "P0": P0, "results": results, "n": n, "seed": seed,
        "demand": network_demand(results, params, P0),
        "sensitivity": sensitivity(params, PS, net_total),
        # the cost-growth draw swamps everything else, so also rank against the total with it divided out
        "sensitivity_base": sensitivity({k: p for k, p in params.items() if k != "costs.soft.contingency"}, PS,
                                        net_total / (1 + PS["costs.soft.contingency"])),
        "phase_totals": {
            ph: _pct(sum(r["capS"]["total"] for r in results if r["line"].phase <= ph)
                     + (fusion_cum[ph] if own else 0.0))
            for ph in sorted({r["line"].phase for r in results})
        },
        "fusion": fusion, "fusion0": fus0, "fusionS": fusS, "heating": heating, "sizing_full": sizing_full,
        "security": security,
        "min_radius_m": curve_radius_note(P0),
        "benchmarks": benchmark_table(params),
        "conf_counts": Counter(p.conf for p in params.values()),
        "local_supply": local_supply,
    }


def _taken(sc: dict, groups) -> str:
    """Buildings a segment's right-of-way takes (measured lines only)."""
    t = sc.get("buildings_taken") or {}
    return f"{sum(float(t.get(g, 0.0)) for g in groups):,.0f}" if t else "-"


KIND_LABEL = {"section_4f": "4(f)", "public_other": "public", "tribal": "tribal"}


def _public_land_crossed(line_id: str) -> list[dict]:
    """Named public and tribal land units on the line's measured route (network/measured), if any."""
    import yaml

    path = ROOT / "network" / "measured" / f"{line_id}.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("public_land_crossed") or []


def _hm(seconds: float) -> str:
    m = int(round(seconds / 60))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


def _bn(musd: float) -> str:
    return f"${musd / 1000:,.1f} bn"


def _demand_section(net: dict) -> list[str]:
    d, P0 = net["demand"], net["P0"]
    L = ["## Ridership and benefits\n"]
    first = next(iter(d["phases"].values()))["res"]
    L.append(
        f"Forecast year {P0['demand.market.forecast_year']:.0f}, every parameter at its most likely value. The market is "
        "observed travel: FHWA NextGen NHTS 2022 trips between the station markets (network/markets.yaml) by "
        "distance band and mode, grown "
        f"{P0['demand.market.growth']:.1%} a year. Today's drivers and today's flyers each choose between their mode "
        "and the maglev (binary logits on generalized cost, California HSR model weights). The car-side constant "
        f"is the conventional-rail constant fitted to the Hiawatha's actual FY25 riders ({first['asc'] - P0['demand.mode_choice.ivt_coefficient'] * P0['demand.mode_choice.maglev_premium']:+.2f}) "
        f"plus a maglev premium of {P0['demand.mode_choice.maglev_premium']:.0f} minutes; the air side is fitted to "
        f"observed HSR shares of the rail + air market (constant {first['asc_air']:+.2f}, scale {first['air_scale']:.2f}; "
        "reference/demand_calibration.yaml). Benefits follow USDOT's BCA guidance (Dec 2025): consumer surplus, "
        "fare revenue, car costs drivers don't weigh and car externalities avoided; 30 years of service at "
        f"{P0['demand.benefits.discount_rate']:.0%} after {P0['demand.benefits.construction_years']:.0f} years of building, "
        "with residual value. Capital is the lines' (fusion excluded: it is a separate investment, the "
        "operating cost uses grid power); 2026 vs 2024 dollars are not converted (~2%).\n")
    L.append("| Through phase | Riders / yr | Fare revenue / yr | O&M P50 / yr | Farebox | Benefits / yr | "
             "Trains/h needed (assumed) | BCR at 7%, mean capital | BCR, P50 capital | BCR at "
             f"{P0['demand.benefits.discount_rate_alt']:.1%} |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for ph, x in d["phases"].items():
        b = x["benefits"]
        L.append(f"| {ph} | {b['riders'] / 1e6:,.1f} M | ${b['revenue_musd']:,.0f} M | ${x['opex']:,.0f} M "
                 f"| {b['revenue_musd'] / x['opex']:.0%} | ${b['total_musd']:,.0f} M "
                 f"| {x['trains_needed']:.1f} ({P0['system.service.trains_per_hour']:.0f}) "
                 f"| **{x['bcr']['bcr']:.3f}** | {x['bcr_p50']['bcr']:.3f} | {x['bcr_alt']['bcr']:.3f} |")
    last = d["phases"][max(d["phases"])]
    b = last["benefits"]
    L.append(f"\nFull network benefits per year: consumer surplus ${b['surplus_musd']:,.0f} M, fares "
             f"${b['revenue_musd']:,.0f} M, unperceived car costs ${b['car_cost_musd']:,.0f} M, car externalities "
             f"${b['external_musd']:,.0f} M; {b['car_vmt_avoided'] / 1e9:,.2f} bn car-miles avoided. Present values at "
             f"7%: benefits {_bn(last['bcr']['pv_benefits'])} + residual {_bn(last['bcr']['pv_residual'])} vs capital "
             f"{_bn(last['bcr']['pv_capital'])} + O&M {_bn(last['bcr']['pv_om'])}.\n")
    L.append("Busiest market pairs (full network):\n")
    L.append("| Pair | Stations | Maglev time | Fare | Market / yr | Riders / yr | Share | From air | Source |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for p in sorted(last["res"]["pairs"], key=lambda p: -p["riders"])[:15]:
        L.append(f"| {p['a']} - {p['b']} | {p['stations'][0]} - {p['stations'][1]} | {_hm(p['minutes'] * 60)}"
                 f"{' (' + str(p['changes']) + ' change' + ('s' if p['changes'] > 1 else '') + ')' if p['changes'] else ''} "
                 f"| ${p['fare']:,.0f} | {p['market'] / 1e6:,.2f} M | {p['riders'] / 1e3:,.0f} k | {p['share']:.1%} "
                 f"| {p['diverted']['air'] / 1e3:,.0f} k | {p['source']} |")
    ph0, ph1 = min(d["phases"]), max(d["phases"])
    L.append(f"\nSensitivity (one at a time, low / high end of the range): riders and BCR at 7%.\n")
    L.append(f"| Parameter | Range | Through phase {ph0}: riders | BCR | Through phase {ph1}: riders | BCR |")
    L.append("|---|---|---|---|---|---|")
    for row in d["sensitivity"]:
        lo0, hi0, lo1, hi1 = row[(ph0, "low")], row[(ph0, "high")], row[(ph1, "low")], row[(ph1, "high")]
        L.append(f"| `{row['param']}` | {row['low']:g} - {row['high']:g} | {lo0[0] / 1e6:.1f} - {hi0[0] / 1e6:.1f} M "
                 f"| {lo0[1]:.3f} - {hi0[1]:.3f} | {lo1[0] / 1e6:.1f} - {hi1[0] / 1e6:.1f} M | {lo1[1]:.3f} - {hi1[1]:.3f} |")
    L.append("\nCaveats: the maglev premium (a constant above conventional rail, half of California HSR's "
             "asserted gap) is the biggest single assumption. Only trips at least "
             f"{P0['demand.market.min_trip_share']:.0%} as long as the road distance between the stations count "
             "(a placeholder rule; the logit's weak time sensitivity would otherwise send ~8% of short car trips to a "
             "much slower maglev trip). Station access time has no effect because the Hiawatha calibration uses the "
             "same access time, so its constant absorbs it. Trips inside one NHTS zone (Duluth - Iron Range, "
             "Rochester - Winona, Owatonna - Albert Lea, Brainerd - Bemidji) are a gravity estimate. Rail ridership "
             "forecasts have historically come in at about half of forecast (Flyvbjerg 2005), which calibrating to "
             "actual riders is meant to avoid. Trains per hour stays an input: the needed figure is reported, not "
             "fed back into the fleet, energy or fusion sizing.\n")
    return L


def write_markdown(net: dict, path: Path) -> None:
    R = net["results"]
    L = []
    variant = net.get("variant")
    L.append("# Minnesota maglev: network estimate" + (f" (variant: {variant})" if variant else "") + "\n")
    L.append(f"Generated {date.today().isoformat()} by `mnmaglev report` "
             f"({net['n']:,} Monte Carlo samples, seed {net['seed']}). USD 2026.\n")
    L.append(f"Local supply policy: **{'on' if net.get('local_supply') else 'off'}** "
             "(network/lines.yaml settings.local_supply; `--local-supply on|off` overrides).\n")
    L.append(f"Winter heating: **{net.get('heating', 'none')}** (see Power and fusion below).\n")
    L.append(f"Fusion: **{net.get('fusion', 'none')}** (see Power and fusion below).\n")
    cc = net["conf_counts"]
    L.append("> Concept-stage numbers. Parameters by confidence: "
             + ", ".join(f"{k} {cc.get(k, 0)}" for k in ("high", "medium", "low", "placeholder"))
             + ". Segment shares (built-up, land, floodplain, peat, bridges) are measured by GIS on lines with a "
               "measured route (`use_measured`) and planner estimates elsewhere; the structure mix "
               "(elevated / at grade) and the cost adders themselves are still estimates. "
               "See docs/RESEARCH.md for what to firm up first.\n")

    L.append("## Lines\n")
    L.append("| Line | Phase | Route km | Stations (new) | End to end | Capital P10 / P50 / P90 | Capital mean | P50 per km | Opex P50 / yr | Second-system reserve P50 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in R:
        line, cs, os_ = r["line"], _pct(r["capS"]["total"]), _pct(r["opsS"]["total"])
        rs = _pct(r["capS"]["reserve"]["total"])["p50"]
        held = "held, in total" if line.reserve else "not held"
        L.append(
            f"| {line.name} | {line.phase} | {line.length_km:,.0f} | {len(line.stations)} ({len(r['new_stations'])}) "
            f"| {_hm(r['kin']['end_to_end_s'])} | {_bn(cs['p10'])} / {_bn(cs['p50'])} / {_bn(cs['p90'])} "
            f"| {_bn(cs['mean'])} | ${cs['p50'] / line.length_km:,.0f} M | ${os_['p50']:,.0f} M "
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
    L.append("Stations shared between lines are costed once, on the earliest phase. Cumulative network capital "
             "(cost growth follows a rail reference-class curve, `costs.soft.contingency`, so the mean, i.e. the "
             "expected cost, sits well above the median; UK appraisal budgets on the mean, FTA funds at P65):\n")
    for ph, t in net["phase_totals"].items():
        L.append(f"- through phase {ph}: {_bn(t['p10'])} / **{_bn(t['p50'])}** / {_bn(t['p90'])} (P10 / P50 / P90); "
                 f"mean **{_bn(t['mean'])}**, P80 {_bn(t['p80'])}")
    L.append("")

    L.append("## What drives the uncertainty\n")
    L.append("Rank correlation of each parameter with total network capital. Research the top rows first.\n")
    L.append("| Parameter | Correlation | Confidence |")
    L.append("|---|---|---|")
    for k, rho, conf in net["sensitivity"]:
        L.append(f"| `{k}` | {rho:+.2f} | {conf} |")
    L.append("")
    L.append("Cost growth (`costs.soft.contingency`, the reference-class curve) dominates. With its draw divided "
             "out, this is what drives the base estimate, and the order to research it in:\n")
    L.append("| Parameter | Correlation with the base estimate | Confidence |")
    L.append("|---|---|---|")
    for k, rho, conf in net["sensitivity_base"]:
        L.append(f"| `{k}` | {rho:+.2f} | {conf} |")
    L.append("")
    L += _demand_section(net)
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
        L.append("Capital breakdown with every parameter at its most likely value (cost growth at the "
                 "reference-class median, MUSD). This sum lands near or below the P10: the ranges are skewed "
                 "high, so stacking most-likely values is optimistic (the classic megaproject trap). Plan with "
                 "the mean and P80 above.\n")
        L.append("| Item | MUSD |")
        L.append("|---|---|")
        for k in ("guideway", "adders", "systems", "stations", "switches", "depot", "vehicles", "heaters", "security",
                  "soft", "land", "wetlands", "buildings", "public_land", "contingency", "first_of_kind"):
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
        L.append("| Segment | km | Elevated | At grade | Urban viaduct | Tunnel | Bridges m | Acres | Wetland acres filled "
                 "| Homes taken | Other buildings taken | 4(f) km | Tribal km |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s, sc in zip(line.segments, c0["segments"]):
            q = sc["quantities"]
            L.append(f"| {s.a.id} -> {s.b.id} | {q['route_km']:,.0f} | {q['elevated_km']:,.0f} | {q['at_grade_km']:,.0f} "
                     f"| {q['urban_viaduct_km']:,.1f} | {q['tunnel_km']:,.1f} | {q['bridge_m']:,.0f} "
                     f"| {sc['acres']:,.0f} | {sc['wetland_acres_filled']:,.1f} "
                     f"| {_taken(sc, ('residential',))} | {_taken(sc, ('nonresidential', 'agriculture'))} "
                     f"| {s.section_4f * s.length_km:,.1f} | {s.tribal * s.length_km:,.1f} |")
        L.append("")
        crossed = _public_land_crossed(line.id)
        if crossed:
            L.append("Public and tribal land the measured route runs through (km; Section 4(f) = public parks, "
                     "recreation areas, refuges, conservation and historic areas): "
                     + "; ".join(f"{c['name'] or 'unnamed'} ({KIND_LABEL[c['kind']]}) {c['km']:.1f}" for c in crossed)
                     + ".\n")

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
    pellets_all = sum(float(r["materials"]["iron_pellets_t"]) for r in R)
    annual = net["P0"]["materials.mn_ore.annual_pellets"] * 1e6
    L.append(f"All the steel in these lines needs ~{pellets_all / 1e6:,.1f} Mt of iron pellets, "
             f"{pellets_all / annual:.1%} of one year of Minnesota pellet output "
             f"({annual / 1e6:,.1f} Mt, 2023-24): {pellets_all / annual / 15:.1%}-{pellets_all / annual / 10:.1%} "
             f"of output a year over a 10-15 year build.\n")

    L.append("## Power and fusion\n")
    fz = net.get("fusion", "none")
    L.append(f"Fusion setting: **{fz}** (network/lines.yaml settings.fusion; `--fusion own|none` overrides). "
             "Demand comes from every train on the timetable, second by second, both directions, "
             "with the departures in the Timetable section below, in winter air. Braking trains feed power to pulling ones. The fleet covers "
             "the 1-second peak plus headroom and one spare unit, no batteries; everything the trains "
             "don't use is surplus for neighbouring users or the grid.\n")
    L.append("| Through phase | Avg demand MW (24 h / service) | Peak MW (1 min / 1 s) | Units (new) | Capacity MW "
             "| Capital P50 new units | Surplus GWh/yr (share) | Surplus value P50 /yr | Fusion O&M P50 /yr "
             "| Grid energy avoided P50 /yr |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for f0, fS in zip(net["fusion0"], net["fusionS"]):
        share = float(f0["surplus_mwh"]) / float(f0["production_mwh"]) if float(f0["production_mwh"]) else 0.0
        L.append(
            f"| {f0['phase']} | {f0['avg_mw']:,.0f} / {f0['avg_service_mw']:,.0f} "
            f"| {f0['peak_1min_mw']:,.0f} / {f0['peak_mw']:,.0f} | {f0['units']} ({f0['new_units']}) "
            f"| {f0['capacity_mw']:,.0f} | {_bn(_pct(fS['capital'])['p50'])} "
            f"| {float(f0['surplus_mwh']) / 1000:,.0f} ({share:.0%}) "
            f"| ${_pct(fS['surplus_value_per_year'])['p50']:,.0f} M "
            f"| ${_pct(fS['om_per_year'])['p50']:,.0f} M "
            f"| ${_pct(fS['grid_energy_avoided_per_year'])['p50']:,.0f} M |"
        )
    first = net["P0"]["power.fusion.first_power_year"]
    L.append(f"\nCapital includes soft costs and contingency{' and counts in the phase totals above' if fz == 'own' else ' but is NOT in the totals (fusion off)'}. "
             f"Until the first unit delivers power (most likely ~{first:.0f}, `power.fusion.first_power_year`), "
             "the trains buy grid power: that is the energy line in each line's opex, so the opex columns "
             "already show the 'fusion late' case.\n")

    L.append("### Winter: heating, storm trains and clearing\n")
    hm = net.get("heating", "none")
    L.append(f"Winter heating: **{hm}** (network/lines.yaml settings.winter_heating; `--winter-heating "
             "targeted|full|none` overrides; params/winter.yaml). The levitation magnets and long stator sit "
             "under the deck where ice normally can't form; the heated surfaces are the side guidance rails "
             "(~10 mm magnet gap) and gliding strips. Targeted = critical spots (stations and their switches, "
             "river bridges, a share for grades, shaded cuts and drifts) heated during icing, on top of the "
             "trains' peak, plus the whole line warmed overnight on icing nights in rotation with units the "
             "trains aren't using. Storm trains, sweepers and clearing vehicles are in each line's winter O&M. "
             "Heater capital is in each line's construction; heating energy is in its opex (at grid price).\n")
    L.append("| Through phase | Heated continuously (km) | Heating during icing MW | Units with heating "
             "| Units if the whole line were heated (full) | Overnight warming MW vs idle fleet MW | Heating GWh/yr "
             "| Fleet size set by |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f0, ff in zip(net["fusion0"], net["sizing_full"]):
        fits = "fits" if f0["night_warming_mw"] <= f0["night_idle_mw"] else "DOES NOT FIT"
        L.append(f"| {f0['phase']} | {float(f0['critical_km']):,.0f} | {float(f0['storm_heating_mw']):,.0f} "
                 f"| {f0['units']} | {ff['units']} | {float(f0['night_warming_mw']):,.0f} vs {f0['night_idle_mw']:,.0f} ({fits}) "
                 f"| {float(f0['heating_mwh']) / 1000:,.1f} | {f0['binding']} "
                 f"({f0['units_by_peak']} by day peak, {f0['units_by_night']} by overnight warming) |")
    L.append("")

    L.append("### Track security: ground robots and drones\n")
    sm = net.get("security", "none")
    L.append(f"Security patrols: **{sm}** (network/lines.yaml settings.security; `--security robots|none` "
             "overrides; params/security.yaml). Ground robots with magnetic gradiometers sweep both guideway "
             "beams every night, while no trains run and the long stator is off, against a baseline magnetic "
             "map of the guideway (foreign ferrous objects, tampering, shifted stator packs); dock-based drones "
             "overfly the route day and night. Remote operators supervise both. Robots, docks and the control "
             "room are in each line's construction; operators, maintenance, replacement and charging energy in "
             "its opex; charging adds to the fusion fleet's load.\n")
    if sm != "none":
        P0 = net["P0"]
        L.append("| Line | Robots | Drones | Docks | Capital MUSD (before soft costs and contingency) "
                 "| Opex MUSD/yr | Charging kW |")
        L.append("|---|---|---|---|---|---|---|")
        for r in R:
            ln = r["line"]
            fl = security_fleet(ln, P0)
            L.append(f"| {ln.id} | {fl['robots']:,.0f} | {fl['drones']:,.0f} | {fl['docks']:,.0f} "
                     f"| {float(security_capital(ln, P0, sm)):,.1f} | {float(security_operating(ln, P0, sm)['total']):,.1f} "
                     f"| {float(security_charge_mw(ln, P0, sm)) * 1000:,.0f} |")
        L.append("")

    L.append("### Timetable: staggered departures\n")
    stag = any(r["line"].offset_fwd_min or r["line"].offset_rev_min for r in R)
    if stag:
        L.append("Departures are staggered per network/timetable.yaml (`mnmaglev timetable --write` picks the "
                 "offsets that minimise the network's 1-second power peak, phase by phase). Each line still "
                 "runs every 30 minutes each way. Minutes past the hour trains reach the Midway hub (every "
                 "30 minutes after that), for planning transfers:\n")
    else:
        L.append("Departures are aligned (no network/timetable.yaml): every line leaves its ends on the hour "
                 "and half hour, the peakiest case. Run `mnmaglev timetable --write` to stagger them.\n")
    L.append("| Line | Forward first departure | Reverse first departure | At Midway hub, forward | At Midway hub, reverse |")
    L.append("|---|---|---|---|---|")
    for r in R:
        line = r["line"]
        ht = hub_times(line, net["P0"])
        fmt = lambda v: "-" if v is None else ", ".join(f":{m % 60:02d}" for m in v)  # noqa: E731
        L.append(f"| {line.id} | 06:{line.offset_fwd_min:02d} from {line.points[0].id} "
                 f"| 06:{line.offset_rev_min:02d} from {line.points[-1].id} "
                 f"| {fmt(ht['forward'])} | {fmt(ht['reverse'])} |")
    L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


def write_json(net: dict, path: Path) -> None:
    out = {"generated": date.today().isoformat(), "n": net["n"], "seed": net["seed"],
           "min_radius_m": net["min_radius_m"], "phase_totals_musd": net["phase_totals"],
           "sensitivity": net["sensitivity"], "lines": [],
           "fusion": {"setting": net.get("fusion", "none"),
                      "phases": [{k: (v if isinstance(v, (int, str)) else float(v)) for k, v in f.items()}
                                 for f in net["fusion0"]],
                      "capital_musd_p": [_pct(f["capital"]) for f in net["fusionS"]]}}
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


PHASE_COLOURS = {1: "#c0392b", 2: "#2471a3", 3: "#7f8c8d", 4: "#b9770e"}


def write_map(net: dict, path: Path) -> None:
    feats = []
    stations = {}
    for r in net["results"]:
        line = r["line"]
        cs = _pct(r["capS"]["total"])
        apath = ROOT / "network" / "alignments" / f"{line.id}.geojson"
        if apath.exists():
            geom = json.loads(apath.read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"]
            coords = [[lat, lon] for lon, lat in geom]
        else:
            coords = [[p.lat, p.lon] for p in line.points]
        feats.append({
            "name": line.name, "phase": line.phase, "colour": PHASE_COLOURS.get(line.phase, "#333"),
            "coords": coords,
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
const map = L.map('map').setView([44.0, -96.0], 6);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 18, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);
for (const l of lines) {
  L.polyline(l.coords, {color: l.colour, weight: l.phase === 1 ? 6 : 4,
    dashArray: l.phase >= 3 ? '8 6' : null}).bindPopup(l.popup).addTo(map);
}
for (const s of stations) {
  L.circleMarker([s.lat, s.lon], {radius: s.type === 'terminal_major' ? 8 : 6,
    color: '#111', fillColor: '#fff', fillOpacity: 1, weight: 2}).bindTooltip(s.name).addTo(map);
}
const legend = L.control({position: 'bottomleft'});
legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend');
  d.innerHTML = '<b>Phase</b><br><span style="color:#c0392b">&#9644;</span> 1 spine<br>' +
    '<span style="color:#2471a3">&#9644;</span> 2<br><span style="color:#7f8c8d">&#9644;</span> 3 (future)<br>' +
    '<span style="color:#b9770e">&#9644;</span> 4 (Denver)<br>' +
    '<small>routed lines: GIS alignment;<br>others: straight lines until routed</small>'; return d; };
legend.addTo(map);
</script></body></html>
"""
