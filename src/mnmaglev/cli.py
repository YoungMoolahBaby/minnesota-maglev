"""mnmaglev check | report"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ROOT
from .network import check_network, list_variants, load_cities, load_lines, load_settings
from .params import check_params, load_params


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
    out = Path(args.out) if args.out else ROOT / "out" / (args.variant or "")
    out.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    local = settings["local_supply"] if args.local_supply is None else args.local_supply == "on"
    fusion = settings["fusion"] if args.fusion is None else args.fusion
    heating = settings["winter_heating"] if args.winter_heating is None else args.winter_heating
    net = run_network(lines, params, n=args.n, seed=args.seed, local_supply=local, fusion=fusion,
                      heating=heating)
    net["variant"] = args.variant
    write_markdown(net, out / "report.md")
    write_json(net, out / "results.json")
    write_map(net, out / "map.html")
    for ph, t in net["phase_totals"].items():
        print(f"through phase {ph}: P50 ${t['p50'] / 1000:,.1f} bn (P10 {t['p10'] / 1000:,.1f}, P90 {t['p90'] / 1000:,.1f})")
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
    res = gis.route(line, nominal(params))
    print(f"curves: {res['curves']}")
    for p in res["measured"]:
        a = p["from"] if isinstance(p["from"], str) else p["from"]["id"]
        b = p["to"] if isinstance(p["to"], str) else p["to"]["id"]
        print(f"  {a} -> {b} ({p['zone']}): {p['length_km']} km, detour {p['detour']}, land {p['land_shares']}, "
              f"bridges {p['bridges_m']}, guideway up to {p['guideway_max_height_m']} m")
    gpath, mpath = gis.write_outputs(line, res)
    print(f"wrote {gpath} and {mpath}; set use_measured: true on the line in network/lines.yaml to use it")
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
    rp.add_argument("--no-measured", action="store_true",
                    help="use the planner estimates even where a GIS alignment exists")
    rp.add_argument("--n", type=int, default=5000, help="Monte Carlo samples")
    rp.add_argument("--seed", type=int, default=1)
    rp.add_argument("--out", default=None, help="output folder (default out/ or out/<variant>/)")
    rp.set_defaults(fn=cmd_report)
    sub.add_parser("benchmarks", help="sourced cost benchmarks in 2026 USD vs parameter ranges").set_defaults(fn=cmd_benchmarks)
    gp = sub.add_parser("gis", help="route a line on elevation + land cover and measure it (needs --extra gis)")
    gp.add_argument("line", help="line id from network/lines.yaml")
    gp.set_defaults(fn=cmd_gis)
    tp = sub.add_parser("timetable", help="stagger departures to minimise the network power peak")
    tp.add_argument("--write", action="store_true", help="write network/timetable.yaml")
    tp.add_argument("--restarts", type=int, default=6)
    tp.add_argument("--no-transfers", action="store_true", help="ignore connections at the Midway hub")
    tp.add_argument("--seed", type=int, default=1)
    tp.set_defaults(fn=cmd_timetable)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
