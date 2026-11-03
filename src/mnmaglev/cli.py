"""mnmaglev check | report"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ROOT
from .network import check_network, load_cities, load_lines
from .params import check_params, load_params


def _load(phase: int | None, only: list[str] | None):
    params = load_params()
    cities = load_cities()
    lines = load_lines(cities=cities)
    if phase is not None:
        lines = [l for l in lines if l.phase <= phase]
    if only:
        lines = [l for l in lines if l.id in only]
    return params, cities, lines


def cmd_check(args) -> int:
    params, cities, lines = _load(None, None)
    problems = check_params(params) + check_network(lines, cities, set(params))
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(params)} parameters, {len(cities)} places, {len(lines)} lines, {len(problems)} problems")
    return 1 if problems else 0


def cmd_report(args) -> int:
    from .report import run_network, write_json, write_map, write_markdown

    params, cities, lines = _load(args.phase, args.lines.split(",") if args.lines else None)
    problems = check_params(params) + check_network(lines, cities, set(params))
    if problems:
        for p in problems:
            print("PROBLEM", p)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    net = run_network(lines, params, n=args.n, seed=args.seed)
    write_markdown(net, out / "report.md")
    write_json(net, out / "results.json")
    write_map(net, out / "map.html")
    for ph, t in net["phase_totals"].items():
        print(f"through phase {ph}: P50 ${t['p50'] / 1000:,.1f} bn (P10 {t['p10'] / 1000:,.1f}, P90 {t['p90'] / 1000:,.1f})")
    print(f"wrote {out / 'report.md'}, results.json, map.html")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mnmaglev")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate params and network").set_defaults(fn=cmd_check)
    rp = sub.add_parser("report", help="estimate the network, write out/")
    rp.add_argument("--phase", type=int, default=None, help="include lines up to this phase")
    rp.add_argument("--lines", default=None, help="comma-separated line ids")
    rp.add_argument("--n", type=int, default=5000, help="Monte Carlo samples")
    rp.add_argument("--seed", type=int, default=1)
    rp.add_argument("--out", default=str(ROOT / "out"))
    rp.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
