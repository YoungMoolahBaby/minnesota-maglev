import pytest

from mnmaglev.costs import line_capital, segment_quantities
from mnmaglev.demand import station_graph
from mnmaglev.kinematics import line_summary
from mnmaglev.network import load_cities, load_lines
from mnmaglev.params import TECHNOLOGIES, apply_technology, check_params, load_params, nominal
from mnmaglev.technology import prepare


@pytest.fixture(scope="module")
def world():
    params = load_params()
    lines = load_lines(cities=load_cities())
    return params, lines


def test_every_technology_validates_and_maglev_is_the_model(world):
    params, _ = world
    assert apply_technology(params, "maglev") == params
    for tech in TECHNOLOGIES:
        p = apply_technology(params, tech)
        assert check_params(p) == []
    hsr = apply_technology(params, "hsr")
    assert hsr["system.vehicle.cruise_speed"].value == params["technology.hsr.cruise_speed"].value
    assert hsr["system.vehicle.cruise_speed"].name == "system.vehicle.cruise_speed"
    assert hsr["costs.guideway.tunnel"] is params["costs.guideway.tunnel"]  # not overridden


def test_hsr_moves_elevated_km_to_grade_and_keeps_the_route(world):
    params, lines = world
    _, hsr_lines = prepare(params, lines, "hsr")
    share = params["technology.hsr.elevated_to_at_grade"].value
    for a, b in zip(lines, hsr_lines):
        for s, t in zip(a.segments, b.segments):
            qa, qb = segment_quantities(s), segment_quantities(t)
            assert qb["route_km"] == pytest.approx(qa["route_km"])
            assert qb["elevated_km"] + qb["at_grade_km"] == pytest.approx(qa["elevated_km"] + qa["at_grade_km"])
            assert qb["elevated_km"] == pytest.approx(qa["elevated_km"] * (1 - share))


def test_conventional_runs_on_its_schedule_speed(world):
    params, lines = world
    p, ls = prepare(params, lines, "conventional")
    P = nominal(p)
    spine = next(l for l in ls if l.id == "spine")
    km = sum(s.length_km for s in spine.segments)
    assert line_summary(spine, P)["end_to_end_s"] == pytest.approx(km / P["system.vehicle.schedule_speed"] * 3600)
    od = station_graph([spine], P)
    assert od[("duluth", "rochester")]["minutes"] == pytest.approx(km / P["system.vehicle.schedule_speed"] * 60)


def test_conventional_buys_no_land_and_holds_no_reserve(world):
    params, lines = world
    p, ls = prepare(params, lines, "conventional")
    P = nominal(p)
    spine = next(l for l in ls if l.id == "spine")
    t = line_summary(spine, P)["end_to_end_s"]
    cap = line_capital(spine, P, spine.stations, t)
    assert cap["land"] == cap["buildings"] == cap["wetlands"] == 0
    assert cap["reserve"]["total"] == 0
    km = sum(s.length_km for s in spine.segments)
    assert cap["guideway"] == pytest.approx(km * P["costs.guideway.at_grade"])
