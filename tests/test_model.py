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
    crow = seg.length_km / seg.detour
    long = replace(seg, urban_start_km=0, urban_end_km=0, detour=230 / crow)  # 230 km, stops at both ends
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
    # peaks above the average: trains accelerating (staggering keeps them apart, so not 2x any more)
    assert d["peak_1min_mw"] > 1.5 * d["avg_service_mw"]


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


def test_staggering_cuts_the_peak_and_keeps_hub_connections(world):
    from mnmaglev.timetable import _connects, hub_events, optimise

    params, _, lines = world
    P0 = nominal(params)
    two = sorted([l for l in lines if l.id in ("spine", "west")], key=lambda l: l.phase)
    for l in two:
        l.offset_fwd_min = l.offset_rev_min = 0
    r = optimise(two, P0, restarts=2)
    for p in r["phases"]:
        assert p["peak_staggered_mw"] <= p["peak_aligned_mw"] + 1e-6
    assert r["phases"][0]["peak_staggered_mw"] < 0.9 * r["phases"][0]["peak_aligned_mw"]
    assert r["unmet_transfers"] == []
    # the west line leaves the hub 5-12 min after a spine arrival
    h = r["headway_min"]
    spine_arr = [(r["offsets"]["spine"][i] + hub_events(two[0], P0, bool(i))[0]) % h for i in (0, 1)]
    west_dep = (r["offsets"]["west"][0] + hub_events(two[1], P0, False)[1]) % h
    assert _connects(west_dep, spine_arr, True, 5, 12, h)


def test_guideway_profile_respects_grade():
    np_ = __import__("numpy")
    from mnmaglev.gis import guideway_profile

    z = np_.concatenate([np_.full(50, 300.0), np_.full(50, 150.0)])  # a 150 m cliff
    p = guideway_profile(z, 100.0, 0.10)
    assert (p >= z - 1e-9).all()
    assert np_.abs(np_.diff(p)).max() <= 0.10 * 100.0 + 1e-9
    assert (p - z).max() == pytest.approx(150 - 10, abs=1e-6)  # one step down allowed at the cliff edge


def test_measured_spine_loads_and_validates(world):
    params, cities, _ = world
    from pathlib import Path

    from mnmaglev import ROOT
    if not (Path(ROOT) / "network" / "measured" / "spine.yaml").exists():
        pytest.skip("no GIS alignment yet")
    measured = next(l for l in load_lines(cities=cities, use_measured=True) if l.id == "spine")
    planner = next(l for l in load_lines(cities=cities, use_measured=False) if l.id == "spine")
    assert check_network([measured], cities, set(params)) == []
    assert [p.id for p in measured.stations] == [p.id for p in planner.stations]
    assert 0.8 * planner.length_km < measured.length_km < 1.2 * planner.length_km


def test_corridor_land_costs_a_share_of_the_land_around_it(world):
    """Highway right-of-way is priced as price_factor x the other land on the segment."""
    from dataclasses import replace

    from mnmaglev.costs import land_price_per_acre

    params, _, lines = world
    P0 = nominal(params)
    seg = next(l for l in lines if l.id == "spine").segments[0]
    farm = replace(seg, land={"cropland_central": 1.0}, parcel_coverage=0.0)
    half = replace(seg, land={"cropland_central": 0.5, "existing_corridor": 0.5}, parcel_coverage=0.0)
    crop = P0["land.price_per_acre.cropland_central"]
    f = P0["land.corridor.price_factor"]
    assert land_price_per_acre(farm, P0) == pytest.approx(crop)
    assert land_price_per_acre(half, P0) == pytest.approx(0.5 * crop + 0.5 * f * crop)
    assert land_price_per_acre(half, {**P0, "land.corridor.price_factor": 0.0}) == pytest.approx(0.5 * crop)


def test_built_up_km_are_priced_as_urban_viaduct(world):
    """A built-up share in the structure mix moves rural km from elevated to urban viaduct."""
    from dataclasses import replace

    params, _, lines = world
    seg = next(l for l in lines if l.id == "spine").segments[0]
    plain = replace(seg, structure={"elevated": 1.0})
    built = replace(seg, structure={"elevated": 0.7, "urban_viaduct": 0.3})
    q0, q1 = segment_quantities(plain), segment_quantities(built)
    assert q1["urban_viaduct_km"] - q0["urban_viaduct_km"] == pytest.approx(0.3 * seg.rural_guideway_km)
    assert q0["elevated_km"] - q1["elevated_km"] == pytest.approx(0.3 * seg.rural_guideway_km)


def test_smoothing_fits_curves_locally_and_keeps_the_detour(world):
    from mnmaglev.gis import CELL, Grid, smooth

    params, _, _ = world
    P = nominal(params)
    g = Grid(x0=-5000.0, y0=-20000.0, nx=400, ny=200)  # 84 x 42 km
    xs = g.x0 + (np.arange(g.nx) + 0.5) * CELL
    ys = g.y1 - (np.arange(g.ny) + 0.5) * CELL
    lake = np.hypot(xs[None, :] - 30000.0, ys[:, None]) < 4000.0
    cost = np.where(lake, 400.0, 70.0)
    # least-cost path: around the lake, plus a kink no curve fits (forces vertices out)
    leg = np.array([[0, 0], [5000, 0], [5300, 600], [5600, 0], [20000, 0], [30000, 8000],
                    [40000, 0], [60000, 0], [75000, 0]], dtype=float)
    stations = leg[[0, -1]]
    out, info = smooth([leg[:7], leg[6:]], np.vstack([stations[0], leg[6], stations[1]]), P, cost, g)
    assert info["all_curves_fit"]
    assert info["vertices_removed_for_curves"] >= 1
    assert np.allclose(out[0], leg[0]) and np.allclose(out[-1], leg[-1])
    # the mid station stays on the line (its vertex is filleted like any other: within a platform)
    assert np.min(np.linalg.norm(out - leg[6], axis=1)) < 150.0
    assert info["cost_smoothed_musd"] <= 1.02 * info["cost_least_cost_path_musd"]


def test_tall_piers_pay_for_every_metre_above_the_reference(world):
    import dataclasses

    from mnmaglev.costs import segment_capital, tall_pier_excess

    params, _, lines = world
    P = nominal(params)
    s = lines[0].segments[0]
    flat = dataclasses.replace(s, pier_excess={})
    tall = dataclasses.replace(s, pier_excess={10.0: 80.0, 20.0: 40.0, 30.0: 10.0})
    P2 = {**P, "costs.guideway.pier_height_ref": 15.0}
    assert tall_pier_excess(tall, P2) == pytest.approx(60.0)  # interpolated between 10 and 20 m
    extra = segment_capital(tall, P2)["guideway"] - segment_capital(flat, P2)["guideway"]
    assert extra == pytest.approx(60.0 * P["costs.guideway.tall_pier_per_m"])
    assert segment_capital(flat, P2)["tall_piers"] == 0.0


def test_adding_a_parameter_leaves_the_other_draws_alone(world):
    from mnmaglev.params import Param

    params, _, _ = world
    extra = {**params, "costs.zz_new": Param("costs.zz_new", 1.0, 0.5, 2.0, "x", "low", "", "")}
    a, b = sample(params, 500, seed=1), sample(extra, 500, seed=1)
    assert all(np.array_equal(a[k], b[k]) for k in params)


def test_peat_comes_from_histosols_where_the_soil_survey_is_complete():
    from mnmaglev.gis import soft_ground, soil_cells

    # mukey 1: half Histosols; 2: mineral; 3: NOTCOM (not surveyed); 9: unknown to SDA; 0: no data
    info = {1: (0.5, True), 2: (0.0, True), 3: (0.0, False)}
    b = np.zeros((1, 7, 3, 7), dtype=np.int64)
    b[0, :, 0, :] = 1                      # cell 0: all mukey 1
    b[0, :, 1, :] = 2
    b[0, :4, 1, :] = 3                     # cell 1: 28 px NOTCOM, 21 px mineral
    b[0, :, 2, :] = 9                      # cell 2: unknown key
    peat, cov = soil_cells(b, info)
    assert peat[0].tolist() == pytest.approx([0.5, 0.0, 0.0])
    assert cov[0].tolist() == pytest.approx([1.0, 21 / 49, 0.0])
    wet = np.array([[0.2, 0.7, 0.4]])
    soft = soft_ground({"wetland": wet}, {"peat": peat, "coverage": cov})
    # surveyed: the soil decides, unsurveyed: the wetland share stands in
    assert soft[0].tolist() == pytest.approx([0.5, 0.7 * 28 / 49, 0.4])


def test_refinement_bends_a_straight_chord_around_a_lake(world):
    from mnmaglev.gis import CELL, Grid, _sample, smooth

    params, _, _ = world
    P = nominal(params)
    g = Grid(x0=-5000.0, y0=-20000.0, nx=400, ny=200)
    xs = g.x0 + (np.arange(g.nx) + 0.5) * CELL
    ys = g.y1 - (np.arange(g.ny) + 0.5) * CELL
    lake = np.hypot(xs[None, :] - 30000.0, ys[:, None]) < 1500.0
    cost = np.where(lake, 400.0, 70.0)
    leg = np.array([[0, 0], [60000, 0]], dtype=float)  # the least-cost path, say, ran straight across
    out, info = smooth([leg], leg, P, cost, g)
    assert info["all_curves_fit"] and info["refinement_moves"] >= 1
    _, x, y = _sample(out)
    assert np.hypot(x - 30000.0, y).min() >= 1500.0 - CELL  # no longer over the lake
    assert info["cost_smoothed_musd"] < info["cost_least_cost_path_musd"]


def test_a_strip_takes_the_buildings_it_touches():
    """building_takes against real geometry: random square buildings in a cell, a strip of width W
    across it; the count and footprint the strip touches match (W + s) x 1000 / CELL^2 per km."""
    from shapely.geometry import box

    from mnmaglev.gis import BUILDING_GROUPS, CELL, building_takes

    rng = np.random.default_rng(7)
    n, width = 20000, 20.0
    side = rng.uniform(8.0, 40.0, n)
    cx, cy = rng.uniform(0, CELL, n), rng.uniform(0, CELL, n)
    strip = box(-100.0, CELL / 2 - width / 2, CELL + 100.0, CELL / 2 + width / 2)
    hit = np.array([strip.intersects(box(x - s / 2, y - s / 2, x + s / 2, y + s / 2))
                    for x, y, s in zip(cx, cy, side)])
    a = side ** 2
    sums = {"n": n, "side": side.sum(), "area": a.sum(), "aside": (a * side).sum()}
    b = {f"{g}_{k}": (v if g == "residential" else 0.0) for g in BUILDING_GROUPS for k, v in sums.items()}
    t = building_takes(b, width)["residential"]
    per_km = 1000.0 / CELL  # the strip crosses the cell once: CELL metres of route
    assert t["n"] == pytest.approx(hit.sum() * per_km, rel=0.03)
    assert t["m2"] == pytest.approx(a[hit].sum() * per_km, rel=0.03)


def test_parcel_values_replace_class_prices_where_they_cover(world):
    from dataclasses import replace

    from mnmaglev.costs import land_price_per_acre

    params, _, lines = world
    P0 = nominal(params)
    seg = next(l for l in lines if l.id == "spine").segments[0]
    crop = P0["land.price_per_acre.cropland_central"]
    k = P0["land.parcels.emv_to_market"]
    f = P0["land.corridor.price_factor"]
    farm = replace(seg, land={"cropland_central": 1.0}, parcel_price=20000.0)
    assert land_price_per_acre(replace(farm, parcel_coverage=0.0), P0) == pytest.approx(crop)
    assert land_price_per_acre(replace(farm, parcel_coverage=1.0), P0) == pytest.approx(0.02 * k)
    assert land_price_per_acre(replace(farm, parcel_coverage=0.25), P0) == pytest.approx(0.25 * 0.02 * k + 0.75 * crop)
    # beside a freeway the right-of-way still costs price_factor x the (parcel) land around it
    half = replace(farm, land={"cropland_central": 0.5, "existing_corridor": 0.5}, parcel_coverage=1.0)
    assert land_price_per_acre(half, P0) == pytest.approx(0.5 * 0.02 * k * (1 + f))


def test_buildings_are_taken_only_where_the_right_of_way_can_take_them(world):
    """Takes scale with the takeable km (not urban ends, bridges, freeway right-of-way) and width."""
    from dataclasses import replace

    from mnmaglev.costs import building_cost, building_takes, segment_capital

    params, _, lines = world
    P0 = nominal(params)
    seg = next(l for l in lines if l.id == "spine").segments[0]
    dens = {"residential": {"n": 100.0, "side": 1200.0, "area": 15000.0, "aside": 2e5},
            "nonresidential": {"n": 0.0, "side": 0.0, "area": 0.0, "aside": 0.0},
            "agriculture": {"n": 0.0, "side": 0.0, "area": 0.0, "aside": 0.0}}
    s = replace(seg, buildings=dens, structure={"elevated": 1.0}, land={"cropland_central": 1.0})
    n, m2 = building_takes(s, {"elevated": 20.0})
    assert n["residential"] == pytest.approx(s.rural_guideway_km * (20 * 100 + 1200) / 1000)
    assert m2["residential"] == pytest.approx(s.rural_guideway_km * (20 * 15000 + 2e5) / 1000)
    half = replace(s, land={"cropland_central": 0.5, "existing_corridor": 0.5})
    assert building_takes(half, {"elevated": 20.0})[0]["residential"] == pytest.approx(0.5 * n["residential"])
    home = P0["land.buildings.home_value"] * P0["land.parcels.emv_to_market"] + P0["land.buildings.home_relocation"]
    assert building_cost(n, m2, P0) == pytest.approx(
        n["residential"] * home + m2["residential"] * P0["land.buildings.demolition_per_m2"] / 1e6)
    assert segment_capital(s, P0)["buildings"] > segment_capital(replace(s, buildings={}), P0)["buildings"] == 0


def test_public_land_kinds_follow_section_4f():
    """Public parks, refuges and conservation areas are 4(f); forests are multiple-use; private land isn't public."""
    from mnmaglev.gis import public_kind

    assert public_kind({"Own_Type": "LOC", "Des_Tp": "LP"}) == "section_4f"
    assert public_kind({"Own_Type": "FED", "Des_Tp": "NWR"}) == "section_4f"
    assert public_kind({"Own_Type": "STAT", "Des_Tp": "SCA"}) == "section_4f"  # WMAs, SNAs
    assert public_kind({"Own_Type": "FED", "Des_Tp": "RMA", "Mang_Name": "FWS"}) == "section_4f"  # WPAs
    assert public_kind({"Own_Type": "FED", "Des_Tp": "NF", "Mang_Name": "USFS"}) == "public_other"
    assert public_kind({"Own_Type": "STAT", "Des_Tp": "SRMA"}) == "public_other"  # state forests
    # Wisconsin county forests are 'LCA' in PAD-US but multiple-use; Illinois forest preserves are parks
    assert public_kind({"Own_Type": "LOC", "Des_Tp": "LCA", "Unit_Nm": "Polk County Forest"}) == "public_other"
    assert public_kind({"Own_Type": "DIST", "Des_Tp": "LCA", "Unit_Nm": "Old School Forest Preserve"}) == "section_4f"
    assert public_kind({"Own_Type": "NGO", "Des_Tp": "PCON"}) is None
    assert public_kind({"Own_Type": "PVT", "Des_Tp": "LP"}) is None


def test_public_land_shares_and_crossings_match_the_geometry():
    """Rasterised shares add up to the polygon's area; km crossed = the chord through it, once even
    when the unit is listed twice."""
    from shapely.geometry import Point

    from mnmaglev.gis import CELL, Grid, _rasterize_share, public_land_crossed

    g = Grid(x0=0.0, y0=0.0, nx=100, ny=60)
    park = Point(10000.0, 6000.0).buffer(3000.0, 256)
    share = _rasterize_share(g, [park])
    assert share.sum() * CELL ** 2 == pytest.approx(park.area, rel=0.01)
    assert share.max() == 1.0 and share.min() == 0.0
    # a straight line 1 km off the centre: chord 2 sqrt(3^2 - 1^2) km
    align = np.array([[0.0, 7000.0], [20000.0, 7000.0]])
    feats = [("section_4f", "Park", park), ("section_4f", "Park", park.buffer(-1.0)),
             ("public_other", "Forest", Point(18000.0, 7000.0).buffer(500.0, 256))]
    rows = public_land_crossed(align, feats)
    assert [r["name"] for r in rows] == ["Park", "Forest"]
    assert rows[0]["km"] == pytest.approx(2 * math.sqrt(8), abs=0.01)
    assert rows[1]["km"] == pytest.approx(1.0, abs=0.01)


def test_public_and_tribal_land_cost_replacement_and_premium(world):
    """Capital: 4(f) land buys replacement land, tribal land a premium; route search: avoidance too."""
    from dataclasses import replace

    from mnmaglev.costs import segment_capital
    from mnmaglev.gis import Grid, cost_surface

    params, _, lines = world
    P0 = nominal(params)
    seg = replace(next(l for l in lines if l.id == "spine").segments[0], section_4f=0.0, tribal=0.0)
    base = segment_capital(seg, P0)
    r, m =P0["land.public.section_4f_replacement"], P0["land.tribal.consent_multiplier"]
    assert base["public_land"] == 0
    assert segment_capital(replace(seg, section_4f=0.4), P0)["public_land"] == pytest.approx(0.4 * r * base["land"])
    assert segment_capital(replace(seg, tribal=0.5), P0)["public_land"] == pytest.approx(0.5 * (m - 1) * base["land"])

    g = Grid(x0=0.0, y0=0.0, nx=4, ny=3)
    z = np.zeros((g.ny, g.nx))
    frac = {k: z.copy() for k in ("water", "urban", "suburban", "forest", "wetland")}
    frac["open"] = z + 1.0
    dem = z.copy()
    one = z + 1.0
    plain = cost_surface(g, frac, dem, P0)
    park = cost_surface(g, frac, dem, P0, public={"section_4f": one, "tribal": z, "public_other": z})
    land = (P0["land.row_width.elevated"] * 1000 / 4046.86 * P0["land.acquisition_multiplier"]
            * P0["land.price_per_acre.cropland_south"])
    avoid = P0["land.public.section_4f_avoidance_km"] * P0["costs.guideway.elevated"]
    # this toy grid sits near lat 23 (south zone prices); every cell is fully in the park
    assert park - plain == pytest.approx(np.full_like(plain, land * r + avoid))


def test_security_fleet_covers_the_line(world):
    """Robots sweep both beams in the usable night hours; drones overfly every km once per revisit
    interval while airborne flight_share of the time; at least one dock per dock_spacing_km."""
    from mnmaglev.costs import line_capital, line_operating
    from mnmaglev.fusion import size_by_phase
    from mnmaglev.security import capital, charge_mw, fleet, operating

    params, _, lines = world
    P0 = nominal(params)
    spine = next(l for l in lines if l.id == "spine")
    L = spine.length_km
    night = (24 - P0["system.service.service_hours"]) * P0["security.ground.window_share"]
    per_robot = P0["security.ground.speed"] * night
    f = fleet(spine, P0)
    working = math.ceil(2 * L * P0["security.ground.sweeps_per_night"] / per_robot)
    assert f["robots"] == math.ceil(working * (1 + P0["security.ground.spare_ratio"]))
    airborne = L / (P0["security.aerial.speed"] * P0["security.aerial.revisit_hours"])
    assert f["drones"] == math.ceil(airborne / P0["security.aerial.flight_share"] * (1 + P0["security.aerial.spare_ratio"]))
    assert f["docks"] >= max(f["drones"], L / P0["security.aerial.dock_spacing_km"])
    # off means nothing anywhere: capital, opex, charging power, the fusion fleet's load
    assert capital(spine, P0, "none") == 0 and operating(spine, P0, "none")["total"] == 0
    assert charge_mw(spine, P0, "none") == 0
    t = 3600.0
    on, off = (line_capital(spine, P0, spine.stations, t, security=m) for m in ("robots", "none"))
    assert on["construction"] - off["construction"] == pytest.approx(capital(spine, P0, "robots"))
    ops = {m: line_operating(spine, P0, 8, 22.0, security=m)["total"] for m in ("robots", "none")}
    assert ops["robots"] - ops["none"] == pytest.approx(operating(spine, P0, "robots")["total"])
    s_on, s_off = (size_by_phase([spine], P0, "none", m)[0] for m in ("robots", "none"))
    assert s_on["security_mw"] == pytest.approx(charge_mw(spine, P0, "robots"))
    assert s_on["demand_mwh"] - s_off["demand_mwh"] == pytest.approx(charge_mw(spine, P0, "robots") * 8760)
    assert s_on["units"] >= s_off["units"]


def test_long_lines_route_in_sections_that_share_stations(world):
    from mnmaglev.gis import line_sections

    _, _, lines = world
    line = next(l for l in lines if l.id == "heartland")
    secs = line_sections(line)
    assert len(secs) == len(line.gis_split_at) + 1
    assert [s.points[-1].id for s in secs[:-1]] == list(line.gis_split_at)
    assert all(a.points[-1] is b.points[0] for a, b in zip(secs, secs[1:]))
    assert sum(len(s.segments) for s in secs) == len(line.segments)
    assert sum(s.length_km for s in secs) == pytest.approx(line.length_km)
