import math

import numpy as np
import pytest

from mnmaglev.costs import line_capital, segment_quantities
from mnmaglev.geo import haversine_km, min_curve_radius_m
from mnmaglev.kinematics import air_density, line_summary, speed_profile
from mnmaglev.network import check_network, load_cities, load_lines
from mnmaglev.params import check_params, load_params, nominal, sample


@pytest.fixture(scope="module")
def world():
    params = load_params()
    cities = load_cities()
    lines = load_lines(cities=cities)
    return params, cities, lines


def test_data_is_valid(world):
    params, cities, lines = world
    assert check_params(params) == []
    assert check_network(lines, cities, set(params)) == []


def test_variants_load_and_validate(world):
    from mnmaglev.network import list_variants

    params, cities, lines = world
    assert "downtown_minneapolis" in list_variants()
    for v in list_variants():
        vl = load_lines(cities=cities, variant=v)
        assert check_network(vl, cities, set(params)) == []
        assert [l.id for l in vl] == [l.id for l in lines]  # same lines, some replaced


def test_spine_runs_through_midway_hub(world):
    _, cities, lines = world
    spine = next(l for l in lines if l.id == "spine")
    assert "midway_hub" in [p.id for p in spine.points]
    downtown = next(l for l in load_lines(cities=cities, variant="downtown_minneapolis") if l.id == "spine")
    assert "minneapolis" in [p.id for p in downtown.points]


def test_reserve_adds_only_where_held(world):
    from dataclasses import replace

    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    assert spine.reserve
    t = line_summary(spine, P0)["end_to_end_s"]
    held = line_capital(spine, P0, spine.stations, t)
    off = line_capital(replace(spine, reserve=False), P0, spine.stations, t)
    assert held["total"] == pytest.approx(off["total"] + held["reserve"]["total"])
    assert off["total"] == pytest.approx(off["total_without_reserve"])
    assert held["reserve"]["total"] > 0 and held["reserve"]["lease_income"] >= 0


def test_reserve_land_scales_with_width(world):
    from mnmaglev.costs import segment_reserve

    params, _, lines = world
    P0 = nominal(params)
    s = next(l for l in lines if l.id == "spine").segments[0]
    a = segment_reserve(s, P0)
    # double every width that makes up the reserve -> double the land
    doubled = {k: 2 * P0[k] for k in ("land.row_width.elevated", "land.row_width.at_grade",
                                      "land.reserve.construction_separation", "land.reserve.width_urban")}
    b = segment_reserve(s, {**P0, **doubled})
    assert b["land"] == pytest.approx(2 * a["land"])
    assert b["acres"] == pytest.approx(2 * a["acres"])
    # the separation alone adds exactly its strip
    wider = segment_reserve(s, {**P0, "land.reserve.construction_separation": P0["land.reserve.construction_separation"] + 10})
    from mnmaglev.costs import ACRE_M2, segment_quantities
    q = segment_quantities(s)
    extra = (q["elevated_km"] + q["at_grade_km"]) * 1000 * 10 / ACRE_M2
    assert wider["acres"] - a["acres"] == pytest.approx(extra)


def test_haversine_one_degree_latitude():
    assert haversine_km(45, -93, 46, -93) == pytest.approx(111.2, abs=0.1)


def test_minneapolis_duluth_straight_line():
    # ~220 km as the crow flies (city centres)
    assert haversine_km(44.9778, -93.2650, 46.7867, -92.1005) == pytest.approx(220, abs=5)


def test_trapezoid_time_matches_closed_form():
    # one long leg at a single limit: t = d/v + v/a
    d, v, a = 100_000.0, 120.0, 0.9
    ds, vel = speed_profile([(d, v)], a, step=10.0)
    t = float((2 * ds / np.maximum(vel[:-1] + vel[1:], 1e-9)).sum())
    assert t == pytest.approx(d / v + v / a, rel=2e-3)


def test_air_density_cold_is_denser():
    assert air_density(15) == pytest.approx(1.225, abs=0.002)
    assert air_density(-20) / air_density(15) == pytest.approx(288.15 / 253.15, rel=1e-9)


def test_curve_radius_textbook():
    # 430 km/h, 12 deg, 1.0 m/s^2: v^2 / (g tan12 + 1)
    v = 430 / 3.6
    expect = v * v / (9.80665 * math.tan(math.radians(12)) + 1.0)
    assert min_curve_radius_m(430, 12, 1.0) == pytest.approx(expect)
    assert 4000 < expect < 5000


def test_structure_km_add_up(world):
    _, _, lines = world
    for line in lines:
        for s in line.segments:
            q = segment_quantities(s)
            parts = q["elevated_km"] + q["at_grade_km"] + q["urban_viaduct_km"] + q["tunnel_km"] + q["bridge_m"] / 1000
            assert parts == pytest.approx(q["route_km"], rel=1e-9)


def test_spine_is_plausible(world):
    params, _, lines = world
    spine = next(l for l in lines if l.id == "spine")
    P0 = nominal(params)
    kin = line_summary(spine, P0)
    assert 350 < spine.length_km < 450
    # Duluth to Rochester with 2 intermediate stops: well under 2 h at maglev speeds
    assert 50 * 60 < kin["end_to_end_s"] < 110 * 60
    # whole-train energy: same order as Transrapid figures (~4-5 MW at 400 km/h ~ 10-15 kWh/km)
    assert 6 < kin["kwh_per_train_km"] < 25


def test_most_likely_values_are_optimistic(world):
    # The ranges are skewed high (overruns are bigger than savings), so the sum of the
    # most-likely values sits below the Monte Carlo median: the megaproject optimism trap.
    params, _, lines = world
    spine = next(l for l in lines if l.id == "spine")
    P0 = nominal(params)
    PS = sample(params, 2000, seed=3)
    t = line_summary(spine, P0)["end_to_end_s"]
    c0 = line_capital(spine, P0, spine.stations, t)["total"]
    cs = line_capital(spine, PS, spine.stations, t)["total"]
    p10, p50, p90 = np.percentile(cs, [10, 50, 90])
    assert p10 < p50 < p90
    assert c0 < p50
