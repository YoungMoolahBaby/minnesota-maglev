"""Electric power demand over a service day, second by second.

Each train's electrical power along a leg comes from the same speed profile as kinematics.py:
traction (mass x acceleration + drag) / efficiency while pulling, minus regenerated power while
braking, plus levitation and hotel loads. Trains leave both ends of every line at the timetable
headway through the service day; their profiles are added on a 1-second grid. Braking trains feed
power back to trains that are pulling, as on a shared supply.

The result sizes the power supply (the fusion fleet in fusion.py) from the real peak, not a guess.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .kinematics import leg_power_cells
from .network import Line, Segment

DAY_S = 24 * 3600


def _reverse(segs: list[Segment]) -> list[Segment]:
    return [replace(s, a=s.b, b=s.a, urban_start_km=s.urban_end_km, urban_end_km=s.urban_start_km)
            for s in reversed(segs)]


def trip_profile(line: Line, P, season: str, reverse: bool = False, step_s: float = 1.0) -> np.ndarray:
    """One train's electrical power (W) every step_s over a whole trip, dwells included."""
    segs = _reverse(line.segments) if reverse else line.segments
    dts, ps = [], []
    current = []
    stops = [s for s in segs if s.b.is_station]
    for s in segs:
        current.append(s)
        if s.b.is_station:
            dt, p, _ = leg_power_cells(current, P, season)
            dts.append(dt)
            ps.append(p)
            if s is not stops[-1]:  # dwell at intermediate stations: hotel load only
                sections = P["costs.vehicles.sections_per_train"]
                dts.append(np.array([P["system.vehicle.dwell"]]))
                ps.append(np.array([P[f"system.vehicle.hotel_power_{season}"] * 1000.0 * sections]))
            current = []
    dt = np.concatenate(dts)
    p = np.concatenate(ps)
    # resample by cumulative energy so every step holds the exact average power
    t_edges = np.concatenate([[0.0], np.cumsum(dt)])
    e_edges = np.concatenate([[0.0], np.cumsum(p * dt)])
    grid = np.arange(0.0, t_edges[-1] + step_s, step_s)
    e = np.interp(grid, t_edges, e_edges)
    return np.diff(e) / step_s


def line_day_profile(line: Line, P, season: str = "winter", step_s: float = 1.0) -> np.ndarray:
    """All trains of a line over one day (W per step), both directions, departures from 06:00."""
    headway = 3600.0 / P["system.service.trains_per_hour"]
    start = 6 * 3600.0
    n_dep = int(P["system.service.service_hours"] * P["system.service.trains_per_hour"])
    n = int(DAY_S / step_s)
    day = np.zeros(n)
    for reverse in (False, True):
        trip = trip_profile(line, P, season, reverse, step_s)
        for k in range(n_dep):
            idx = (int((start + k * headway) / step_s) + np.arange(len(trip))) % n  # the day repeats
            np.add.at(day, idx, trip)
    return day


def demand_summary(profile_w: np.ndarray, step_s: float = 1.0) -> dict:
    """Peak (1 s and 1 min), service-hours and daily averages, energy per day."""
    mw = profile_w / 1e6
    win = max(int(60 / step_s), 1)
    minute = np.convolve(mw, np.ones(win) / win, mode="valid")
    active = mw[np.abs(mw) > 1e-9]
    return {
        "peak_mw": float(mw.max()),
        "peak_1min_mw": float(minute.max()),
        "min_mw": float(mw.min()),
        "avg_service_mw": float(active.mean()) if len(active) else 0.0,
        "avg_day_mw": float(mw.mean()),
        "mwh_per_day": float(mw.sum() * step_s / 3600.0),
    }
