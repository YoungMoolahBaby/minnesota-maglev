import math

import numpy as np
import pytest
import yaml

from mnmaglev import ROOT
from mnmaglev import demand as D
from mnmaglev.kinematics import line_summary
from mnmaglev.network import load_cities, load_lines
from mnmaglev.params import load_params, nominal


@pytest.fixture(scope="module")
def world():
    P = nominal(load_params())
    cities = load_cities()
    lines = load_lines(cities=cities)
    markets, base = D.load_market()
    return P, cities, lines, markets, base


def test_station_graph_matches_line_run_times(world):
    # one line, end to end: the graph time equals the kinematics' run time with dwells
    P, cities, lines, *_ = world
    spine = next(l for l in lines if l.id == "spine")
    od = D.station_graph([spine], P)
    assert od[("duluth", "rochester")]["minutes"] == pytest.approx(line_summary(spine, P)["end_to_end_s"] / 60.0)
    assert od[("duluth", "rochester")]["changes"] == 0
    assert od[("rochester", "duluth")]["path"] == ["rochester", "msp", "midway_hub", "duluth"]


def test_transfers_add_the_planned_connection(world):
    P, cities, lines, *_ = world
    spine = next(l for l in lines if l.id == "spine")
    southwest = next(l for l in lines if l.id == "southwest")
    od = D.station_graph([spine, southwest], P)
    hub_msp = od[("midway_hub", "msp")]["minutes"]
    msp_mankato = od[("msp", "mankato")]["minutes"]
    transfer = (P["system.service.min_transfer"] + P["system.service.max_transfer_wait"]) / 2
    # the dwell at MSP on arrival is part of the connection
    assert od[("midway_hub", "mankato")]["minutes"] == pytest.approx(hub_msp + transfer + msp_mankato)
    assert od[("midway_hub", "mankato")]["changes"] == 1


def test_every_station_belongs_to_one_market(world):
    _, _, lines, markets, base = world
    stations = {c.id for l in lines for c in l.stations}
    owners = [s for m in markets.values() for s in m["stations"]]
    assert stations == set(owners) and len(owners) == len(set(owners))
    for mid in markets:
        assert 0 < base["markets"][mid]["zone_share"] <= 1


def test_rail_constant_reproduces_hiawatha(world):
    P, cities, _, markets, base = world
    asc = D.rail_constant(markets, base, cities, P)
    # rebuild the calibration sum independently
    mc, cal = "demand.mode_choice.", "demand.calibration."
    t = D.pair_bands("milwaukee", "chicago", markets, base, cities, None)
    centre = D._miles(cities["milwaukee"], cities["chicago"]) * P[mc + "road_detour"]
    grow = (1 + P["demand.market.growth"]) ** 3
    tph = P[cal + "hiawatha_round_trips"] / P["system.service.service_hours"]
    gc_rail = (P[cal + "hiawatha_minutes"] + 2 * P[mc + "maglev_access"] + P[mc + "out_of_vehicle_weight"]
               * P[mc + "rail_wait_terminal"] + D.headway_penalty(tph, P) + P[cal + "hiawatha_fare"] / D._vot(P))
    riders = 0.0
    for (lo, hi), all_ in zip(base["bands_miles"], t["all"]):
        miles = D.band_miles(lo, hi, centre)
        if all_ > 0 and miles >= P["demand.market.min_trip_share"] * centre:
            gc_car, _ = D.car_gc(miles, P)
            gap = asc - P[mc + "ivt_coefficient"] * (gc_rail + D.extra_access(miles, centre, P) - gc_car)
            riders += all_ * grow / (1 + math.exp(-gap))
    assert riders == pytest.approx(P[cal + "hiawatha_riders"], rel=1e-6)


def test_air_side_fits_observed_rail_air_shares(world):
    P = world[0]
    const, scale = D.air_constant(P)
    pts = yaml.safe_load((ROOT / "reference" / "demand_calibration.yaml").read_text(encoding="utf-8"))["air_rail_shares"]
    theta = P["demand.mode_choice.ivt_coefficient"]
    model = []
    for q in pts:
        miles = D.haversine_km(*q["a"], *q["b"]) / D.KM_PER_MILE
        g_rail, _, _ = D.maglev_gc(q["hours"] * 60, 0, miles * P["demand.mode_choice.road_detour"], P)
        g_air, _ = D.air_gc(miles, P)
        model.append(D._binary(const - scale * theta * (g_rail - g_air)))
    obs = [q["share"] for q in pts]
    assert np.mean(np.abs(np.array(model) - np.array(obs))) < 0.08
    assert model[-1] < 0.3 < 0.7 < model[0]  # 2 h: rail wins; 5 h: air wins


def test_riders_bounded_and_surplus_positive(world):
    P, cities, lines, markets, base = world
    res = D.ridership(lines, cities, P, markets, base)
    induced = P["demand.mode_choice.induced_share"]
    for p in res["pairs"]:
        assert 0 < p["riders"] <= p["market"] / (1 - induced) + 1e-6
        assert p["cs_minutes"] > 0
        assert p["induced"] == pytest.approx(p["riders"] * induced)
    ab = D.annual_benefits(res, P)
    assert ab["total_musd"] > ab["revenue_musd"] > 0


def test_benefit_cost_matches_annuity_closed_form(world):
    P = dict(world[0])
    P["demand.market.growth"] = 0.0
    P["demand.benefits.construction_years"] = 1
    r = P["demand.benefits.discount_rate"]
    n = int(P["demand.benefits.analysis_years"])
    out = D.benefit_cost(100.0, 1000.0, 10.0, P)
    annuity = (1 - (1 + r) ** -n) / r  # end-of-year payments
    # benefits are mid-year, starting after one year of building: shift by (1 + r)^-0.5
    assert out["pv_benefits"] == pytest.approx(100.0 * annuity * (1 + r) ** 0.5 * (1 + r) ** -1)
    assert out["pv_capital"] == pytest.approx(1000.0 * (1 + r) ** -0.5)
    life = P["demand.benefits.service_life"]
    assert out["pv_residual"] == pytest.approx(1000.0 * (1 - n / life) * (1 + r) ** -(1 + n))
