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


def test_local_supply_lowers_cost_by_its_savings(world):
    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    t = line_summary(spine, P0)["end_to_end_s"]
    off = line_capital(spine, P0, spine.stations, t, local_supply=False)
    on = line_capital(spine, P0, spine.stations, t, local_supply=True)
    ls = on["local_supply"]
    assert on["construction"] == pytest.approx(off["construction"] - ls["construction"])
    assert on["total"] < off["total"]
    # tailings only on north-zone segments
    assert ls["tailings_t"] > 0
    southern = next(l for l in lines if l.id == "southern_link")
    t2 = line_summary(southern, P0)["end_to_end_s"]
    assert line_capital(southern, P0, southern.stations, t2, True)["local_supply"]["tailings_t"] == 0


def test_materials_bill_is_a_small_share(world):
    from mnmaglev.costs import line_materials

    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    t = line_summary(spine, P0)["end_to_end_s"]
    bill = line_materials(spine, P0)["bill_musd"]
    assert bill["total"] == pytest.approx(sum(v for k, v in bill.items() if k != "total"))
    construction = line_capital(spine, P0, spine.stations, t)["construction"]
    assert 0 < bill["total"] / construction < 0.15


def test_energy_matches_tr08_at_300_kmh(world):
    """TR08, 5 sections: 28.1 Wh per seat-km at 300 km/h (Schach et al., via de.wikipedia Transrapid)."""
    from dataclasses import replace

    from mnmaglev.kinematics import run_leg

    params, _, lines = world
    P0 = nominal(params)
    seg = next(l for l in lines if l.id == "spine").segments[3]
    long = replace(seg, urban_start_km=0, urban_end_km=0, detour=2.0)  # ~230 km, stops at both ends
    r = run_leg([long], {**P0, "system.vehicle.cruise_speed": 300})
    w = P0["system.service.winter_share"]
    kwh = w * r.energy_kwh_winter + (1 - w) * r.energy_kwh_summer
    seats = P0["system.vehicle.seats_per_section"] * P0["costs.vehicles.sections_per_train"]
    wh_per_seat_km = kwh / r.length_km / seats * 1000
    assert wh_per_seat_km == pytest.approx(28.1, rel=0.1)


def test_day_power_profile_matches_trip_energy(world):
    """Second-by-second power over a day integrates to the energy model's trips (dwells aside)."""
    from mnmaglev.power import demand_summary, line_day_profile

    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    d = demand_summary(line_day_profile(spine, P0, "winter"))
    s = line_summary(spine, P0)
    trips = 2 * P0["system.service.trains_per_hour"] * P0["system.service.service_hours"]
    kin_mwh = trips * sum(l.energy_kwh_winter for l in s["legs"]) / 1000
    assert d["mwh_per_day"] == pytest.approx(kin_mwh, rel=0.01)
    # peaks well above the average: trains accelerating together
    assert d["peak_1min_mw"] > 2 * d["avg_service_mw"]


def test_fusion_fleet_covers_peak_with_spare(world):
    from mnmaglev.fusion import fleet_money, size_by_phase

    params, _, lines = world
    P0 = nominal(params)
    sizing = size_by_phase(lines, P0)
    unit = P0["power.fusion.unit_mwe"]
    for s in sizing:
        # without the spare unit, capacity still covers the 1-second peak plus headroom
        assert (s["units"] - P0["power.fusion.spare_units"]) * unit >= s["peak_mw"] * (1 + P0["power.fusion.sizing_margin"])
        assert s["new_units"] >= 0
    assert [s["units"] for s in sizing] == sorted(s["units"] for s in sizing)  # fleet only grows
    money = fleet_money(sizing, P0)
    assert all(m["surplus_mwh"] >= 0 for m in money)
    total_new = sum(s["new_units"] for s in sizing)
    assert total_new == sizing[-1]["units"]


def test_fusion_learning_curve_makes_later_units_cheaper(world):
    from mnmaglev.fusion import fleet_money, size_by_phase

    params, _, lines = world
    P0 = nominal(params)
    sizing = size_by_phase(lines, P0)
    flat = fleet_money(sizing, {**P0, "power.fusion.learning_rate": 0.0})
    learn = fleet_money(sizing, P0)
    per_unit_flat = P0["power.fusion.unit_mwe"] * P0["power.fusion.capex_per_kw"] / 1000.0
    soft = (1 + P0["costs.soft.engineering_admin"]) * (1 + P0["costs.soft.contingency"])
    assert flat[0]["capital"] == pytest.approx(sizing[0]["new_units"] * per_unit_flat * soft)
    assert all(l["capital"] < f["capital"] for l, f in zip(learn[1:], flat[1:]) if f["capital"] > 0)


def test_winter_heating_modes(world):
    from mnmaglev.fusion import size_by_phase
    from mnmaglev.winter import critical_km, heater_capital, heating_mwh, mw_per_km, storm_mw

    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    # 450 W/m2 x 1.4 m2/m = 0.63 MW per km
    assert mw_per_km(P0) == pytest.approx(P0["winter.heating.w_per_m2"] * P0["winter.heating.area_per_m"] / 1000)
    assert 0 < critical_km(spine, P0) < spine.length_km
    assert storm_mw(spine, P0, "none") == 0 < storm_mw(spine, P0, "targeted") < storm_mw(spine, P0, "full")
    assert heating_mwh(spine, P0, "none") == 0 and heater_capital(spine, P0, "none") == 0
    # more heating never shrinks the fleet; targeted overnight warming fits in the idle units
    units = {m: size_by_phase([spine], P0, m)[0] for m in ("none", "targeted", "full")}
    assert units["none"]["units"] <= units["targeted"]["units"] <= units["full"]["units"]
    t = units["targeted"]
    assert t["night_warming_mw"] <= t["night_idle_mw"]
