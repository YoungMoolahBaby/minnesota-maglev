"""Running time and traction energy between stops.

A speed-limit profile along the leg, a forward pass (accelerate) and a backward pass (brake),
then time and energy integrated over the distance grid. Drag uses the air density of the
segment's climate zone, so Minnesota winters cost energy through physics, not a guessed factor.
This is the stand-in until OSRD runs the same legs (integrations/osrd).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .network import Line, Segment

STEP_M = 25.0
R_AIR = 287.05  # J/(kg K)
P_SEA = 101325.0  # Pa


def air_density(temp_c: float) -> float:
    return P_SEA / (R_AIR * (temp_c + 273.15))


@dataclass
class LegResult:
    start: str
    end: str
    length_km: float
    time_s: float
    energy_kwh_winter: float
    energy_kwh_summer: float
    top_speed_kmh: float


def speed_profile(pieces: list[tuple[float, float]], accel: float, step: float = STEP_M):
    """pieces: (length_m, limit_m_s). Returns (ds array, node speeds v[0..n])."""
    limits = []
    for length, vmax in pieces:
        n = max(int(round(length / step)), 1)
        limits += [vmax] * n
    lengths = []
    for length, _ in pieces:
        n = max(int(round(length / step)), 1)
        lengths += [length / n] * n
    ds = np.array(lengths)
    lim = np.array(limits)
    # node limits: the stricter of the two neighbouring cells
    node_lim = np.empty(len(ds) + 1)
    node_lim[0] = node_lim[-1] = 0.0
    node_lim[1:-1] = np.minimum(lim[:-1], lim[1:])
    v = node_lim.copy()
    for i in range(len(ds)):
        v[i + 1] = min(v[i + 1], np.sqrt(v[i] ** 2 + 2 * accel * ds[i]))
    for i in range(len(ds) - 1, -1, -1):
        v[i] = min(v[i], np.sqrt(v[i + 1] ** 2 + 2 * accel * ds[i]))
    return ds, v


def _leg_pieces(segs: list[Segment], cruise: float, urban: float) -> tuple[list, list]:
    pieces, zones = [], []
    for s in segs:
        rural = max(s.length_km - s.urban_km, 0.0)
        us = min(s.urban_start_km, s.length_km)
        ue = min(s.urban_end_km, s.length_km - us)
        for km, v in ((us, urban), (rural, cruise), (ue, urban)):
            if km > 0:
                pieces.append((km * 1000.0, v))
                zones.append(s.zone)
    return pieces, zones


def leg_power_cells(segs: list[Segment], P, season: str):
    """Per distance cell of one leg: duration (s), electrical power (W, negative = returned), speeds.

    Traction = (mass x acceleration + drag) x speed. While pulling it costs traction / efficiency;
    while braking the net (drag already helps slow the train) is regenerated at regen x efficiency.
    Levitation and hotel loads run throughout. kinematics energy and power.py both use this.
    """
    cruise = P["system.vehicle.cruise_speed"] / 3.6
    urban = P["system.vehicle.urban_speed"] / 3.6
    sections = P["costs.vehicles.sections_per_train"]
    mass = P["system.vehicle.section_mass"] * sections * 1000.0  # kg
    cda = P["system.vehicle.drag_coefficient"] * P["system.vehicle.frontal_area"]
    eff = P["system.vehicle.propulsion_efficiency"]
    regen = P["system.vehicle.regen_fraction"]
    base_w = (P["system.vehicle.levitation_power"] * mass  # kW/t x kg = W
              + P[f"system.vehicle.hotel_power_{season}"] * 1000.0 * sections)

    pieces, zones = _leg_pieces(segs, cruise, urban)
    ds, v = speed_profile(pieces, P["system.vehicle.accel"])
    cell_zone = []
    for (length, _), z in zip(pieces, zones):
        cell_zone += [z] * max(int(round(length / STEP_M)), 1)
    rho = np.array([air_density(P[f"climate.{z}.{season}_mean_temp"]) for z in cell_zone])
    dt = 2 * ds / np.maximum(v[:-1] + v[1:], 1e-9)
    vmid = 0.5 * (v[:-1] + v[1:])
    accel = (v[1:] ** 2 - v[:-1] ** 2) / (2 * ds)
    mech = (mass * accel + 0.5 * rho * cda * vmid**2) * vmid
    elec = np.where(mech > 0, mech / eff, mech * eff * regen) + base_w
    return dt, elec, v


def run_leg(segs: list[Segment], P: dict[str, float]) -> LegResult:
    out = {}
    for season in ("winter", "summer"):
        dt, elec, v = leg_power_cells(segs, P, season)
        out[season] = float((elec * dt).sum()) / 3.6e6
    length_km = sum(s.length_km for s in segs)
    schedule = float(np.mean(P["system.vehicle.schedule_speed"]))  # a fixed switch, not sampled
    time_s = length_km / schedule * 3600.0 if schedule > 0 else float(dt.sum())
    return LegResult(
        start=segs[0].a.id, end=segs[-1].b.id,
        length_km=length_km, time_s=time_s,
        energy_kwh_winter=out["winter"], energy_kwh_summer=out["summer"],
        top_speed_kmh=float(v.max() * 3.6),
    )


def run_line(line: Line, P: dict[str, float]) -> list[LegResult]:
    """One direction, stopping at every station (waypoints are passed through)."""
    legs, current = [], []
    for s in line.segments:
        current.append(s)
        if s.b.is_station:
            legs.append(run_leg(current, P))
            current = []
    return legs


def line_summary(line: Line, P: dict[str, float]) -> dict:
    legs = run_line(line, P)
    dwell = P["system.vehicle.dwell"] * max(len(legs) - 1, 0)
    run_s = sum(l.time_s for l in legs) + dwell
    w = P["system.service.winter_share"]
    kwh_trip = sum(w * l.energy_kwh_winter + (1 - w) * l.energy_kwh_summer for l in legs)
    return {
        "legs": legs,
        "end_to_end_s": run_s,
        "kwh_per_trip": kwh_trip,
        "kwh_per_train_km": kwh_trip / line.length_km,
    }
