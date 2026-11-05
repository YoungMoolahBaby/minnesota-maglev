"""mnmaglev check | report"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ROOT
from .network import check_network, list_variants, load_cities, load_lines, load_settings
from .params import TECHNOLOGIES, check_params, load_params


def _load(phase: int | None, only: list[str] | None, variant: str | None = None, measured: bool = True):
    params = load_params()
    cities = load_cities()
    lines = load_lines(cities=cities, variant=variant, use_measured=measured)
    if phase is not None:
        lines = [l for l in lines if l.phase <= phase]
    if only:
        lines = [l for l in lines if l.id in only]
    return params, cities, lines


def cmd_check(args) -> int:
    problems = []
    for variant in [None, *list_variants()]:
        params, cities, lines = _load(None, None, variant)
        found = check_network(lines, cities, set(params))
        if variant is None:
            found = check_params(params) + found
        problems += [f"[{variant or 'default'}] {p}" for p in found]
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(params)} parameters, {len(cities)} places, {len(lines)} lines, "
          f"variants {list_variants()}, {len(problems)} problems")
    return 1 if problems else 0


def cmd_report(args) -> int:
    from .report import run_network, write_json, write_map, write_markdown

    params, cities, lines = _load(args.phase, args.lines.split(",") if args.lines else None, args.variant,
                                  not args.no_measured)
    problems = check_params(params) + check_network(lines, cities, set(params))
    if problems:
        for p in problems:
            print("PROBLEM", p)
        return 1
    if args.technology != "maglev":
        from .technology import prepare

        params, lines = prepare(params, lines, args.technology)
    out = Path(args.out) if args.out else ROOT / "out" / (args.variant or "") / (
        "" if args.technology == "maglev" else f"tech_{args.technology}")
    out.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    local = settings["local_supply"] if args.local_supply is None else args.local_supply == "on"
    fusion = settings["fusion"] if args.fusion is None else args.fusion
    heating = settings["winter_heating"] if args.winter_heating is None else args.winter_heating
    security = settings["security"] if args.security is None else args.security
    net = run_network(lines, params, n=args.n, seed=args.seed, local_supply=local, fusion=fusion,
                      heating=heating, security=security)
    net["variant"] = args.variant
    write_markdown(net, out / "report.md")
    write_json(net, out / "results.json")
    write_map(net, out / "map.html")
    for ph, t in net["phase_totals"].items():
        print(f"through phase {ph}: P50 ${t['p50'] / 1000:,.1f} bn (P10 {t['p10'] / 1000:,.1f}, P90 {t['p90'] / 1000:,.1f}), "
              f"mean ${t['mean'] / 1000:,.1f} bn, P80 {t['p80'] / 1000:,.1f}")
    print(f"wrote {out / 'report.md'}, results.json, map.html")
    return 0


def cmd_benchmarks(args) -> int:
    from .benchmarks import benchmark_table

    print(benchmark_table(load_params()))
    return 0


def cmd_timetable(args) -> int:
    from .timetable import optimise, write_timetable

    params, _, lines = _load(None, None)
    from .params import nominal

    lines = sorted(lines, key=lambda l: l.phase)
    for l in lines:  # optimise from aligned departures, not from an earlier result
        l.offset_fwd_min = l.offset_rev_min = 0
    result = optimise(lines, nominal(params), restarts=args.restarts, seed=args.seed,
                      transfers=not args.no_transfers)
    if result["unmet_transfers"]:
        print("no offset gives a good hub connection for:", ", ".join(result["unmet_transfers"]))
    for p in result["phases"]:
        print(f"through phase {p['phase']}: 1-second peak {p['peak_aligned_mw']:.0f} MW aligned -> "
              f"{p['peak_staggered_mw']:.0f} MW staggered")
    for lid, (fwd, rev) in result["offsets"].items():
        print(f"  {lid}: forward +{fwd} min, reverse +{rev} min")
    if args.write:
        write_timetable(result)
        print("wrote network/timetable.yaml")
    return 0


def cmd_gis(args) -> int:
    from . import gis
    from .params import nominal

    params = load_params()
    cities = load_cities()
    line = next((l for l in load_lines(cities=cities, use_measured=False) if l.id == args.line), None)
    if line is None:
        print(f"no line {args.line!r}")
        return 1
    P = nominal(params)
    if line.gis_split_at:
        if args.section is not None:  # one section only (run sections in parallel, then merge)
            r = gis.route_section(line, P, args.section)
            print(f"section {args.section} done: {r['curves']}")
            return 0
        res = gis.route_sections(line, P, reuse=args.reuse_sections)
    else:
        res = gis.route(line, P)
    print(f"curves: {res['curves']}")
    for p in res["measured"]:
        a = p["from"] if isinstance(p["from"], str) else p["from"]["id"]
        b = p["to"] if isinstance(p["to"], str) else p["to"]["id"]
        print(f"  {a} -> {b} ({p['zone']}): {p['length_km']} km, detour {p['detour']}, land {p['land_shares']}, "
              f"bridges {p['bridges_m']}, guideway up to {p['guideway_max_height_m']} m")
    gpath, mpath = gis.write_outputs(line, res)
    print(f"wrote {gpath} and {mpath}; set use_measured: true on the line in network/lines.yaml to use it")
    return 0


def cmd_compare(args) -> int:
    from .technology import run_all

    params, cities, lines = _load(None, None, args.variant, True)
    problems = check_params(params) + check_network(lines, cities, set(params))
    if problems:
        for p in problems:
            print("PROBLEM", p)
        return 1
    settings = load_settings()
    path = run_all(params, lines, n=args.n, seed=args.seed, out=ROOT / "out" / (args.variant or ""),
                   local_supply=settings["local_supply"], fusion="none", heating=settings["winter_heating"],
                   security=settings["security"])
    print(f"wrote {path}")
    return 0


def cmd_screen_data(args) -> int:
    from .screen_data import build

    for path in build(min_miles=args.min_miles):
        print(f"wrote {path}")
    return 0


def cmd_screen(args) -> int:
    from .screen import load_corridors, load_measured, screen_cities, corridor_lines, run_screen

    params = load_params()
    cfg = load_corridors()
    cities = screen_cities(cfg)
    lines = [l for cid in cfg["corridors"]
             for l in corridor_lines(cfg, cid, cities, load_measured(), params["screen.built_up_factor"].value)]
    problems = check_params(params) + check_network(lines, cities, set(params))
    if problems:
        for p in problems:
            print("PROBLEM", p)
        return 1
    only = args.corridors.split(",") if args.corridors else None
    techs = args.technologies.split(",") if args.technologies else TECHNOLOGIES
    path = run_screen(params, n=args.n, seed=args.seed, out=ROOT / "out", techs=techs, only=only,
                      security=load_settings()["security"], built_up=args.built_up)
    print(f"wrote {path}")
    return 0


def cmd_demand_data(args) -> int:
    from .demand_data import build

    path = build(min_miles=args.min_miles)
    print(f"wrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mnmaglev")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate params, the network and every variant").set_defaults(fn=cmd_check)
    rp = sub.add_parser("report", help="estimate the network, write out/")
    rp.add_argument("--phase", type=int, default=None, help="include lines up to this phase")
    rp.add_argument("--lines", default=None, help="comma-separated line ids")
    rp.add_argument("--variant", default=None, help=f"network variant from network/variants/ ({', '.join(list_variants())})")
    rp.add_argument("--local-supply", choices=["on", "off"], default=None,
                    help="override settings.local_supply in network/lines.yaml")
    rp.add_argument("--fusion", choices=["own", "none"], default=None,
                    help="override settings.fusion in network/lines.yaml")
    rp.add_argument("--winter-heating", choices=["targeted", "full", "none"], default=None,
                    help="override settings.winter_heating in network/lines.yaml")
    rp.add_argument("--security", choices=["robots", "none"], default=None,
                    help="override settings.security in network/lines.yaml (robot and drone patrols)")
    rp.add_argument("--no-measured", action="store_true",
                    help="use the planner estimates even where a GIS alignment exists")
    rp.add_argument("--n", type=int, default=5000, help="Monte Carlo samples")
    rp.add_argument("--seed", type=int, default=1)
    rp.add_argument("--out", default=None, help="output folder (default out/ or out/<variant>/)")
    rp.add_argument("--technology", choices=["maglev", "hsr", "conventional"], default="maglev",
                    help="run as dedicated high-speed rail or upgraded conventional rail (params/technology.yaml)")
    rp.set_defaults(fn=cmd_report)
    sub.add_parser("benchmarks", help="sourced cost benchmarks in 2026 USD vs parameter ranges").set_defaults(fn=cmd_benchmarks)
    gp = sub.add_parser("gis", help="route a line on elevation + land cover and measure it (needs --extra gis)")
    gp.add_argument("line", help="line id from network/lines.yaml")
    gp.add_argument("--section", type=int, default=None,
                    help="lines with gis_split_at: route only this section (0-based) and save it")
    gp.add_argument("--reuse-sections", action="store_true",
                    help="lines with gis_split_at: merge saved section results instead of re-routing them")
    gp.set_defaults(fn=cmd_gis)
    tp = sub.add_parser("timetable", help="stagger departures to minimise the network power peak")
    tp.add_argument("--write", action="store_true", help="write network/timetable.yaml")
    tp.add_argument("--restarts", type=int, default=6)
    tp.add_argument("--no-transfers", action="store_true", help="ignore connections at the Midway hub")
    tp.add_argument("--seed", type=int, default=1)
    tp.set_defaults(fn=cmd_timetable)
    cp = sub.add_parser("compare", help="maglev vs dedicated HSR vs upgraded rail on the same corridors -> out/compare.md")
    cp.add_argument("--n", type=int, default=2000, help="Monte Carlo samples per technology")
    cp.add_argument("--seed", type=int, default=1)
    cp.add_argument("--variant", default=None)
    cp.set_defaults(fn=cmd_compare)
    dp = sub.add_parser("demand-data", help="build network/demand_base.yaml from NHTS OD 2022 and Census 2025 (~40 MB download)")
    dp.add_argument("--min-miles", type=float, default=10.0, help="lowest distance band kept (NHTS bands start at 0, 10, 25, 50 ...)")
    dp.set_defaults(fn=cmd_demand_data)
    sp = sub.add_parser("screen-data", help="screen corridors: built-up km (Census urban areas, ~75 MB) and NHTS markets")
    sp.add_argument("--min-miles", type=float, default=10.0)
    sp.set_defaults(fn=cmd_screen_data)
    sc = sub.add_parser("screen", help="the model on other US corridors, maglev / HSR / upgraded rail -> out/screen.md")
    sc.add_argument("--n", type=int, default=1000, help="Monte Carlo samples per run")
    sc.add_argument("--seed", type=int, default=1)
    sc.add_argument("--corridors", default=None, help="comma-separated corridor ids (default all)")
    sc.add_argument("--technologies", default=None, help="comma-separated, from maglev,hsr,conventional")
    sc.add_argument("--built-up", choices=["value", "high"], default="value",
                    help="screen.built_up_factor end: value (calibrated on Minnesota) or high (all urban-area km on viaduct)")
    sc.set_defaults(fn=cmd_screen)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
