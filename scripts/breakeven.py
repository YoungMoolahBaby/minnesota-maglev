"""What the maglev would have to cost to break even (BCR = 1), per build-out, at 7% and 3.1%, at
the most likely demand and with high-end demand (maglev premium, value of time and market growth
all at their high values), plus the spine's capital by item. Same run as `mnmaglev compare`
(2000 samples, seed 1, no fusion). Numbers in docs/PLAN.md ("What it would take").

Break-even capital C solves PV benefits + residual(C) = PV capital(C) + PV O&M; both capital terms
are linear in C.

Usage: uv run python scripts/breakeven.py
"""

from __future__ import annotations

import numpy as np

from mnmaglev.cli import _load
from mnmaglev.demand import benefit_cost, network_demand
from mnmaglev.network import load_settings
from mnmaglev.params import nominal
from mnmaglev.report import run_network

HIGH_DEMAND = ("demand.mode_choice.maglev_premium", "demand.mode_choice.value_of_time", "demand.market.growth")
ITEMS = ("guideway", "adders", "systems", "stations", "switches", "depot", "vehicles", "heaters", "land",
         "buildings", "soft", "contingency", "first_of_kind")


def breakeven(x: dict, P, rate: float) -> tuple[float, float]:
    """(BCR, break-even capital MUSD) of one build-out at a discount rate."""
    bc = benefit_cost(x["benefits"]["total_musd"], x["capital_mean"], x["opex"], P, rate=rate)
    k_cap = bc["pv_capital"] / x["capital_mean"]
    k_res = bc["pv_residual"] / x["capital_mean"]
    return bc["bcr"], (bc["pv_benefits"] - bc["pv_om"]) / (k_cap - k_res)


def main() -> None:
    params, _, lines = _load(None, None, None, True)
    s = load_settings()
    net = run_network(lines, params, n=2000, seed=1, local_supply=s["local_supply"], fusion="none",
                      heating=s["winter_heating"], security=s["security"], sensitivity_runs=False)
    results = net["results"]
    P0 = nominal(params)
    high = {**P0, **{k: params[k].high for k in HIGH_DEMAND}}
    for label, P in (("most likely demand", P0), ("high demand (" + ", ".join(HIGH_DEMAND) + " high)", high)):
        d = network_demand(results, params, P, sweep=False)
        print(f"\n{label}")
        for ph in sorted(d["phases"]):
            x = d["phases"][ph]
            km = sum(r["line"].length_km for r in results if r["line"].phase <= ph)
            for rate in (P0["demand.benefits.discount_rate"], P0["demand.benefits.discount_rate_alt"]):
                bcr, be = breakeven(x, P, rate)
                print(f"  through phase {ph} ({km:,.0f} km) at {rate:.1%}: BCR {bcr:.3f}; capital mean "
                      f"${x['capital_mean'] / 1e3:,.1f} bn (${x['capital_mean'] / km:,.0f} M/km), P50 "
                      f"${x['capital_p50'] / 1e3:,.1f} bn; break-even ${be / 1e3:,.1f} bn (${be / km:,.0f} M/km): "
                      f"cut {1 - be / x['capital_mean']:.0%} of the mean, {1 - be / x['capital_p50']:.0%} of the P50; "
                      f"benefits ${x['benefits']['total_musd']:,.0f} M/yr, O&M ${x['opex']:,.0f} M/yr")
    spine = next(r for r in results if r["line"].phase == 1)
    km = spine["line"].length_km
    print(f"\n{spine['line'].id} capital by item ({km:,.0f} km; mean, P50):")
    c = spine["capS"]
    for k in ITEMS + ("total",):
        v = np.asarray(c[k], dtype=float)
        print(f"  {k:14s} ${v.mean() / 1e3:6.1f} bn  ${np.percentile(v, 50) / 1e3:6.1f} bn  ${v.mean() / km:6.1f} M/km")
    if c["reserve_included"]:
        print(f"  {'reserve':14s} ${np.mean(c['reserve']['total']) / 1e3:6.1f} bn")


if __name__ == "__main__":
    main()
