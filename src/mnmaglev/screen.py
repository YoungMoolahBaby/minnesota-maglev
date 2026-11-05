"""The US corridor screen: the whole model (costs with cost growth, kinematics, ridership, USDOT
benefit-cost) on other US corridors, for maglev, high-speed rail and upgraded rail, so Minnesota's
result can be read against denser travel markets (`mnmaglev screen`).

Corridors are planner-level lines (network/screen/corridors.yaml) with the built-up km measured from
Census urban areas (network/screen/measured.yaml) and their NHTS travel market
(network/screen/demand_base.yaml), both from `mnmaglev screen-data`. Construction prices scale by the
region's area cost factor relative to Minneapolis (params/screen.yaml). The demand model keeps its
Minnesota calibration (the Hiawatha rail constant, the gravity fit). Minnesota runs twice: through
the same screen method, and as the measured GIS spine, which shows what the screen method misses.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from . import NETWORK_DIR
from .network import CORRIDOR, Bridge, City, Line, Segment
from .params import TECHNOLOGIES, Param

SCREEN_DIR = NETWORK_DIR / "screen"
# construction prices that follow local construction costs (area cost factor); systems, vehicles
# and land don't (bought nationally / priced per acre)
REGIONAL = ("costs.guideway.elevated", "costs.guideway.at_grade", "costs.guideway.urban_viaduct",
            "costs.guideway.tunnel", "costs.guideway.bridge_per_m", "costs.guideway.tall_pier_per_m",
            "costs.guideway.switch_each", "costs.stations.terminal_major", "costs.stations.airport",
            "costs.stations.city", "costs.depot.per_line")


def load_corridors(path: Path = SCREEN_DIR / "corridors.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_measured(path: Path = SCREEN_DIR / "measured.yaml") -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `mnmaglev screen-data`")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def screen_cities(cfg: dict) -> dict[str, City]:
    return {k: City(id=k, name=v["name"], lat=v["lat"], lon=v["lon"], pop=0, type=v["type"])
            for k, v in cfg["stations"].items()}


def _segment(cfg: dict, corridor: dict, line_id: str, a: City, b: City, over: dict, measured: dict,
             built_up_factor: float) -> Segment:
    d, st = cfg["defaults"], cfg["stations"]
    ka, kb = st[a.id].get("approach_km", 0.0), st[b.id].get("approach_km", 0.0)
    ta, tb = st[a.id].get("tunnel", 0.0), st[b.id].get("tunnel", 0.0)
    seg = Segment(
        line_id=line_id, a=a, b=b, detour=float(over.get("detour", d["detour"])),
        zone=over.get("zone", corridor["zone"]), urban_start_km=ka, urban_end_km=kb,
        urban_tunnel=(ka * ta + kb * tb) / (ka + kb) if ka + kb > 0 else 0.0,
        structure={}, land={}, floodplain=float(over.get("floodplain", d["floodplain"])),
        peat=float(over.get("peat", d["peat"])),
        bridges=[Bridge(**x) for x in over.get("bridges", [])],
    )
    rural = seg.rural_guideway_km
    built = measured[f"{a.id}-{b.id}"]["built_up_share"] * built_up_factor
    tunnel = min(float(over.get("tunnel_km", 0.0)) / rural, 1.0 - built) if rural > 0 else 0.0
    open_ = 1.0 - built - tunnel
    seg.structure = {k: v * open_ for k, v in d["structure"].items()}
    seg.structure.update({"urban_viaduct": built, "tunnel": tunnel})
    seg.structure = {k: v for k, v in seg.structure.items() if v > 0} or {"elevated": 1.0}
    # land: the urban ends are urban core, built-up km suburban, the rest open country (some beside a
    # freeway or railroad), all at Minnesota's prices (land is ~1% of the capital)
    length = seg.length_km
    urban_core = seg.urban_km / length
    suburban = rural * built / length
    rest = max(1.0 - urban_core - suburban, 0.0)
    land = {"urban_core": urban_core, "suburban": suburban,
            CORRIDOR: rest * d["corridor_share"], "cropland_central": rest * (1 - d["corridor_share"])}
    total = sum(land.values())
    seg.land = {k: v / total for k, v in land.items() if v > 0}
    seg.note = f"screen: {built:.0%} of the rural km built-up (Census urban areas)"
    return seg


def corridor_lines(cfg: dict, cid: str, cities: dict[str, City], measured: dict,
                   built_up_factor: float) -> list[Line]:
    """The corridor's lines; built_up_factor = params screen.built_up_factor (the share of the urban-area
    km on the straight line priced as urban viaduct)."""
    c = cfg["corridors"][cid]
    lines = []
    for spec in c["lines"]:
        pts = [cities[p] for p in spec["points"]]
        overrides = spec.get("segments", {}) or {}
        unknown = set(overrides) - {f"{a.id}-{b.id}" for a, b in zip(pts, pts[1:])}
        if unknown:
            raise ValueError(f"screen line {spec['id']}: segments not between neighbouring points: {unknown}")
        segs = [_segment(cfg, c, spec["id"], a, b, overrides.get(f"{a.id}-{b.id}", {}), measured[spec["id"]],
                         built_up_factor)
                for a, b in zip(pts, pts[1:])]
        lines.append(Line(id=spec["id"], name=c["name"], phase=1, points=pts, segments=segs))
    return lines


def regional(params: dict[str, Param], region: str) -> dict[str, Param]:
    """Construction prices times the region's area cost factor relative to Minneapolis."""
    f = params[f"screen.area_cost_factor.{region}"].value / params["screen.area_cost_factor.minnesota"].value
    out = dict(params)
    for name in REGIONAL:
        p = params[name]
        out[name] = replace(p, value=p.value * f, low=p.low * f, high=p.high * f,
                            quantiles=tuple((q, v * f) for q, v in p.quantiles))
    return out


def corridor_market(cfg: dict, cid: str, base: dict, cities: dict[str, City]):
    """(cities, markets, base) for the demand model, the corridor's markets only."""
    markets = {mid: {"stations": m["stations"], "zones": base["market_zones"][mid], "cbsa": m["cbsa"]}
               for mid, m in cfg["corridors"][cid]["markets"].items()}
    return cities, markets, base


def breakeven_per_km(x: dict, km: float) -> float:
    """Capital per route-km at which the BCR would be 1 at 7% (benefits, O&M and residual held)."""
    bc = x["bcr"]
    k_cap = bc["pv_capital"] / x["capital_mean"]
    k_res = bc["pv_residual"] / x["capital_mean"]
    be = (bc["pv_benefits"] - bc["pv_om"]) / (k_cap - k_res) if k_cap > k_res else float("nan")
    return max(be, 0.0) / km


def run_screen(params, n: int, seed: int, out: Path, techs=TECHNOLOGIES, only: list[str] | None = None,
               security: str = "none", built_up: str = "value") -> Path:
    """built_up: which end of params screen.built_up_factor shapes the corridors (value or high)."""
    from .network import load_lines
    from .report import run_network
    from .technology import prepare

    cfg = load_corridors()
    measured = load_measured()
    base = yaml.safe_load((SCREEN_DIR / "demand_base.yaml").read_text(encoding="utf-8"))
    cities = screen_cities(cfg)
    rows = []
    cases = [(cid, c) for cid, c in cfg["corridors"].items() if not only or cid in only]
    for cid, c in cases:
        lines = corridor_lines(cfg, cid, cities, measured, getattr(params["screen.built_up_factor"], built_up))
        market = corridor_market(cfg, cid, base, cities)
        for tech in techs:
            p, ls = prepare(params, lines, tech)
            p = regional(p, c["region"])
            print(f"screen: {cid} / {tech} ...", flush=True)
            net = run_network(ls, p, n=n, seed=seed, local_supply=False, fusion="none", heating=c["heating"],
                              security=security, market=market, sensitivity_runs=False)
            rows.append(_row(cid, c["name"], tech, net, cfg, market))
    # Minnesota's measured (GIS) spine, same settings (no local supply, no reserve), its own market
    if not only or "minnesota" in only:
        spine = next(l for l in load_lines() if l.id == "spine")
        spine = replace(spine, reserve=False)
        for tech in techs:
            p, ls = prepare(params, [spine], tech)
            print(f"screen: minnesota (measured spine) / {tech} ...", flush=True)
            net = run_network(ls, p, n=n, seed=seed, local_supply=False, fusion="none", heating="targeted",
                              security=security, sensitivity_runs=False)
            rows.append(_row("minnesota_measured", "Minnesota spine, measured GIS alignment (the main model)",
                             tech, net, cfg, None))
    out.mkdir(parents=True, exist_ok=True)
    stem = "screen" if built_up == "value" else f"screen_built_up_{built_up}"
    path = out / f"{stem}.md"
    path.write_text(screen_markdown(rows, n, getattr(params["screen.built_up_factor"], built_up)), encoding="utf-8")
    (out / f"{stem}.yaml").write_text(yaml.safe_dump(
        [{k: v for k, v in r.items() if k != "pairs"} for r in rows], sort_keys=False), encoding="utf-8")
    return path


def _row(cid: str, name: str, tech: str, net: dict, cfg: dict, market) -> dict:
    from .costs import segment_quantities

    x = net["demand"]["phases"][1]
    b, res = x["benefits"], x["res"]
    lines = [r["line"] for r in net["results"]]
    km = sum(l.length_km for l in lines)
    q = [segment_quantities(s) for l in lines for s in l.segments]
    if market is not None:
        pops = {mid: res_pop for mid, res_pop in
                ((mid, market[2]["markets"][mid]["population"]) for mid in market[1])}
    else:
        from .demand import load_market

        mk, base = load_market()
        served = {s.id for l in lines for s in l.stations}
        pops = {mid: base["markets"][mid]["population"] for mid, m in mk.items() if set(m["stations"]) & served}
    ends = max(res["pairs"], key=lambda p: p["miles"]) if res["pairs"] else None
    return {
        "corridor": cid, "name": name, "tech": tech, "km": km,
        "stations": sum(len(l.stations) for l in lines),
        "population": sum(pops.values()),
        "urban_viaduct_km": sum(v["urban_viaduct_km"] for v in q), "tunnel_km": sum(v["tunnel_km"] for v in q),
        "elevated_km": sum(v["elevated_km"] for v in q), "at_grade_km": sum(v["at_grade_km"] for v in q),
        "capital_mean": x["capital_mean"], "capital_p50": x["capital_p50"], "opex": x["opex"],
        "riders": b["riders"], "revenue": b["revenue_musd"], "benefits": b["total_musd"],
        "pkm": sum(p["riders"] * p["miles"] for p in res["pairs"]) * 1.609344,
        "bcr": x["bcr"]["bcr"], "bcr_alt": x["bcr_alt"]["bcr"], "breakeven_per_km": breakeven_per_km(x, km),
        "trains_needed": x["trains_needed"],
        "end_to_end": (ends["a"], ends["b"], ends["minutes"]) if ends else None,
        "top_pairs": [(p["a"], p["b"], p["riders"], p["share"]) for p in
                      sorted(res["pairs"], key=lambda p: -p["riders"])[:3]],
    }


def screen_markdown(rows: list[dict], n: int, built_up_factor: float) -> str:
    from .report import _bn, _hm

    techs = list(dict.fromkeys(r["tech"] for r in rows))
    order = list(dict.fromkeys(r["corridor"] for r in rows))
    by = {(r["corridor"], r["tech"]): r for r in rows}
    L = ["# US corridor screen: the same model on other corridors\n",
         f"Generated by `mnmaglev screen` ({n:,} Monte Carlo samples per run). Each corridor runs the whole "
         "model: costs with cost growth (reference-class curve, first-of-kind premium for maglev), kinematics, "
         "the NHTS 2022 travel market of its CBSAs, the Minnesota-calibrated mode choice, and the USDOT "
         "benefit-cost analysis (7%, 30 years, residual value). Capital is the expected value (mean), 2026 USD, "
         "construction prices scaled by the region's area cost factor; no local-supply savings, no "
         "second-system reserve, no fusion fleet. Corridors are planner-level lines (network/screen/"
         f"corridors.yaml) with built-up km measured from Census urban areas, {built_up_factor:.2f} of them priced as "
         "urban viaduct (screen.built_up_factor).\n",
         "## Benefit-cost ratio at 7% (3.1% in brackets)\n",
         "| Corridor | Route km | Market pop. | " + " | ".join(techs) + " |",
         "|---|---|---|" + "---|" * len(techs)]
    for cid in order:
        r0 = by[(cid, techs[0])]
        cells = [f"**{by[(cid, t)]['bcr']:.2f}** ({by[(cid, t)]['bcr_alt']:.2f})" if (cid, t) in by else "-"
                 for t in techs]
        L.append(f"| {r0['name']} | {r0['km']:,.0f} | {r0['population'] / 1e6:,.1f} M | " + " | ".join(cells) + " |")
    for tech in techs:
        L.append(f"\n## {tech}\n")
        L.append("| Corridor | Capital mean (P50) | per km | End to end | Riders / yr | Passenger-km / yr "
                 "| Fares / yr | O&M / yr | Farebox | Benefits / yr | BCR 7% | Break-even per km | Trains/h needed |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cid in order:
            r = by.get((cid, tech))
            if not r:
                continue
            e2e = f"{r['end_to_end'][0]}-{r['end_to_end'][1]} {_hm(r['end_to_end'][2] * 60)}" if r["end_to_end"] else "-"
            L.append(f"| {cid} | {_bn(r['capital_mean'])} ({_bn(r['capital_p50'])}) | ${r['capital_mean'] / r['km']:,.0f} M "
                     f"| {e2e} | {r['riders'] / 1e6:,.1f} M | {r['pkm'] / 1e9:,.1f} bn | ${r['revenue']:,.0f} M "
                     f"| ${r['opex']:,.0f} M | {r['revenue'] / r['opex']:.0%} | ${r['benefits']:,.0f} M "
                     f"| **{r['bcr']:.2f}** | ${r['breakeven_per_km']:,.0f} M | {r['trains_needed']:.1f} |")
    L.append("\n## Corridors (maglev geometry; HSR moves part of the rural elevated km to grade)\n")
    L.append("| Corridor | Route km | Stations | Elevated | At grade | Built-up (urban viaduct) | Tunnel | Busiest pairs (maglev riders / yr, share of the market) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for cid in order:
        r = by.get((cid, techs[0]))
        pairs = "; ".join(f"{a}-{b} {n_ / 1e6:,.1f} M ({s:.0%})" for a, b, n_, s in r["top_pairs"])
        L.append(f"| {cid} | {r['km']:,.0f} | {r['stations']} | {r['elevated_km']:,.0f} | {r['at_grade_km']:,.0f} "
                 f"| {r['urban_viaduct_km']:,.0f} | {r['tunnel_km']:,.0f} | {pairs} |")
    comp_path = SCREEN_DIR.parent.parent / "reference" / "screen_comparators.yaml"
    if comp_path.exists() and "hsr" in techs:
        comp = yaml.safe_load(comp_path.read_text(encoding="utf-8"))
        L.append("\n## Real projects on these corridors (reference/screen_comparators.yaml; costs as published, "
                 "not 2026 USD) beside the screen's HSR\n")
        L.append("| Corridor | Project | Published cost | Published riders | Screen HSR: capital mean (P50), riders, end to end |")
        L.append("|---|---|---|---|---|")
        for cid in order:
            c, r = comp.get(cid), by.get((cid, "hsr"))
            if not c or not r:
                continue
            e2e = _hm(r["end_to_end"][2] * 60) if r["end_to_end"] else "-"
            L.append(f"| {cid} | {c['project']} | {c.get('cost', '-')} | {c.get('riders', '-')} "
                     f"| {_bn(r['capital_mean'])} ({_bn(r['capital_p50'])}), {r['riders'] / 1e6:,.1f} M, {e2e} |")
    return "\n".join(L) + "\n"
