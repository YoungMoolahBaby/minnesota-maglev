"""Track security patrols (network/lines.yaml settings.security, params/security.yaml).

Modes:
  robots  autonomous ground robots with magnetic gradiometers sweep both guideway beams in the
          overnight window (no trains, long stator off) and dock-based drones overfly the route
          day and night; remote operators supervise both; charged from the network's power
  none    no robot patrols (inspection stays in operations.om_per_km_year)

Fleet sizes follow from coverage: a robot surveys speed x usable night hours of beam per night; a
drone flies speed x revisit interval of route per overflight cycle, and is airborne flight_share of
the time. Works with nominal floats and Monte Carlo arrays alike.
"""

from __future__ import annotations

import numpy as np

from .network import Line

MODES = ("robots", "none")
BEAMS = 2  # dual guideway: two beams to sweep


def fleet(line: Line, P) -> dict:
    """Robots, drones and docks a line needs (spares included)."""
    g, a = "security.ground.", "security.aerial."
    night_h = (24.0 - P["system.service.service_hours"]) * P[g + "window_share"]
    beam_km = BEAMS * line.length_km * P[g + "sweeps_per_night"]
    robots = np.ceil(np.ceil(beam_km / (P[g + "speed"] * night_h)) * (1 + P[g + "spare_ratio"]))
    airborne = line.length_km / (P[a + "speed"] * P[a + "revisit_hours"])
    drones = np.ceil(airborne / P[a + "flight_share"] * (1 + P[a + "spare_ratio"]))
    docks = np.maximum(drones, np.ceil(line.length_km / P[a + "dock_spacing_km"]))
    return {"robots": robots, "drones": drones, "docks": docks}


def capital(line: Line, P, mode: str):
    """Robots, docks with their drones, dock sites, and the line's share of the control room. MUSD."""
    if mode == "none":
        return 0.0
    f = fleet(line, P)
    a = "security.aerial."
    return (f["robots"] * P["security.ground.robot_capex"]
            + f["docks"] * (P[a + "dock_capex"] + P[a + "site_capex"])
            + P["security.operations.control_room_capex"])


def charge_mw(line: Line, P, mode: str):
    """Average charging power (MW) drawn from the network's supply (the fusion fleet)."""
    if mode == "none":
        return 0.0
    f = fleet(line, P)
    return (f["robots"] * P["security.ground.charge_kw"] + f["drones"] * P["security.aerial.charge_kw"]) / 1000.0


def operating(line: Line, P, mode: str) -> dict:
    """Annual cost, MUSD/yr: operators around the clock, maintenance, replacement, charging energy."""
    if mode == "none":
        return {"staff": 0.0, "maintenance": 0.0, "renewal": 0.0, "energy": 0.0, "total": 0.0}
    f = fleet(line, P)
    o, g, a = "security.operations.", "security.ground.", "security.aerial."
    # drones are supervised around the clock; robots only in the night window, as a share of a seat
    night = (24.0 - P["system.service.service_hours"]) / 24.0
    seats = (f["drones"] + f["robots"] * night) / P[o + "units_per_operator"]
    staff = seats * P[o + "fte_per_seat"] * P[o + "staff_cost"]
    robots = f["robots"] * P[g + "robot_capex"]
    docks = f["docks"] * P[a + "dock_capex"]
    maintenance = (robots + docks) * P[o + "maintenance_share"]
    renewal = robots / P[g + "life_years"] + docks / P[a + "life_years"]
    energy = charge_mw(line, P, mode) * 8760.0 * 1000.0 * P["costs.operations.energy_price"] / 1e6
    return {"staff": staff, "maintenance": maintenance, "renewal": renewal, "energy": energy,
            "total": staff + maintenance + renewal + energy}
