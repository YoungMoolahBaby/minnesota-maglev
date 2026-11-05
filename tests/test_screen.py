import struct

import numpy as np
import pytest

from mnmaglev.costs import segment_quantities
from mnmaglev.network import check_network, load_lines
from mnmaglev.params import load_params
from mnmaglev.screen import REGIONAL, corridor_lines, load_corridors, load_measured, regional, screen_cities
from mnmaglev.screen_data import UrbanAreas, built_up_share, shp_rings


@pytest.fixture(scope="module")
def world():
    params = load_params()
    cfg = load_corridors()
    return params, cfg, screen_cities(cfg), load_measured()


def _shp(polygons: list[list[np.ndarray]]) -> bytes:
    """A minimal ESRI polygon shapefile (.shp bytes): one record per polygon, each a list of rings."""
    recs = b""
    for i, rings in enumerate(polygons):
        pts = np.vstack(rings)
        parts, k = [], 0
        for r in rings:
            parts.append(k)
            k += len(r)
        body = struct.pack("<i4d2i", 5, pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max(),
                           len(rings), len(pts))
        body += struct.pack(f"<{len(parts)}i", *parts) + pts.astype("<f8").tobytes()
        recs += struct.pack(">ii", i + 1, len(body) // 2) + body
    return b"\0" * 100 + recs


def _ring(x0, y0, x1, y1):
    return np.array([[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]], dtype=float)


def test_shapefile_rings_and_even_odd_holes():
    # a 2 x 2 degree urban area with a 1 x 1 hole (a park), and a far-away one the bbox drops
    data = _shp([[_ring(0, 0, 2, 2), _ring(0.5, 0.5, 1.5, 1.5)], [_ring(50, 50, 51, 51)]])
    rings = shp_rings(data, bbox=(-1, -1, 3, 3))
    assert len(rings) == 2
    ua = UrbanAreas(rings)
    inside = ua.inside(np.array([0.25, 1.0, 1.75, 3.0]), np.array([0.25, 1.0, 1.75, 3.0]))
    assert inside.tolist() == [True, False, True, False]


def test_built_up_share_skips_the_station_approaches():
    ua = UrbanAreas([_ring(-0.01, -1, 0.5, 1)])  # urban over the first half of a 0..1 degree line
    a, b = {"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}
    share, km = built_up_share(a, b, ua, 0.0, 0.0)
    assert km == pytest.approx(111.2, rel=0.01)
    assert share == pytest.approx(0.5, abs=0.01)
    # leave out 20 km at the urban end: 35.6 of the remaining 91.2 km are urban
    share, _ = built_up_share(a, b, ua, 20.0, 0.0)
    assert share == pytest.approx((km / 2 - 20) / (km - 20), abs=0.01)


def test_screen_method_reproduces_the_measured_spine(world):
    """The calibration behind screen.built_up_factor: the screen's Minnesota spine has about the
    measured GIS alignment's urban viaduct km, and a similar length."""
    params, cfg, cities, measured = world
    screen = corridor_lines(cfg, "minnesota", cities, measured, params["screen.built_up_factor"].value)
    spine = [l for l in load_lines() if l.id == "spine"]
    tot = lambda ls, k: sum(segment_quantities(s)[k] for l in ls for s in l.segments)  # noqa: E731
    assert tot(screen, "urban_viaduct_km") == pytest.approx(tot(spine, "urban_viaduct_km"), rel=0.15)
    assert tot(screen, "route_km") == pytest.approx(tot(spine, "route_km"), rel=0.05)


def test_every_corridor_builds_and_checks(world):
    params, cfg, cities, measured = world
    f = params["screen.built_up_factor"].value
    for cid, c in cfg["corridors"].items():
        lines = corridor_lines(cfg, cid, cities, measured, f)
        assert check_network(lines, cities, set(params)) == [], cid
        served = {s.id for l in lines for s in l.stations}
        for mid, m in c["markets"].items():
            assert set(m["stations"]) <= served, (cid, mid)
        for l in lines:
            for s in l.segments:
                assert sum(s.structure.values()) == pytest.approx(1.0)
                assert sum(s.land.values()) == pytest.approx(1.0)
        assert f"screen.area_cost_factor.{c['region']}" in params


def test_mountain_tunnels_land_in_the_rural_km(world):
    params, cfg, cities, measured = world
    lines = corridor_lines(cfg, "california", cities, measured, params["screen.built_up_factor"].value)
    seg = next(s for l in lines for s in l.segments if (s.a.id, s.b.id) == ("palmdale", "los_angeles"))
    q = segment_quantities(seg)
    want = cfg["corridors"]["california"]["lines"][0]["segments"]["palmdale-los_angeles"]["tunnel_km"]
    assert q["tunnel_km"] == pytest.approx(want + seg.urban_km * seg.urban_tunnel)
    assert q["route_km"] == pytest.approx(seg.length_km)


def test_regional_prices_scale_construction_only(world):
    params = world[0]
    f = params["screen.area_cost_factor.northeast"].value / params["screen.area_cost_factor.minnesota"].value
    p = regional(params, "northeast")
    for name in REGIONAL:
        assert p[name].value == pytest.approx(params[name].value * f)
        assert p[name].high == pytest.approx(params[name].high * f)
    assert p["costs.systems.propulsion_power_control"] is params["costs.systems.propulsion_power_control"]
    assert p["costs.vehicles.per_section"] is params["costs.vehicles.per_section"]
    assert regional(params, "minnesota")["costs.guideway.elevated"].value == params["costs.guideway.elevated"].value
