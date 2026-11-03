"""mnmaglev check | report"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ROOT
from .network import check_network, list_variants, load_cities, load_lines, load_settings
from .params import check_params, load_params


def _load(phase: int | None, only: list[str] | None, variant: str | None = None):
    params = load_params()
    cities = load_cities()
    lines = load_lines(cities=cities, variant=variant)
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

    params, cities, lines = _load(args.phase, args.lines.split(",") if args.lines else None, args.variant)
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
    rp.add_argument("--n", type=int, default=5000, help="Monte Carlo samples")
    rp.add_argument("--seed", type=int, default=1)
    rp.add_argument("--out", default=None, help="output folder (default out/ or out/<variant>/)")
    rp.set_defaults(fn=cmd_report)
    sub.add_parser("benchmarks", help="sourced cost benchmarks in 2026 USD vs parameter ranges").set_defaults(fn=cmd_benchmarks)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
