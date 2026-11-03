"""Guideway heating against ice: critical spots during icing, overnight warming of the whole line.

Modes (network/lines.yaml settings.winter_heating):
  targeted  heat the critical spots continuously during icing (stations and their switches, river
            bridges, a share of the route for grades / shaded cuts / drifts) and warm the whole line
            overnight on icing nights, in rotation, with power the trains aren't using (default)
  full      heat the whole guideway continuously during icing (shows what that does to the power peak)
  none      no heaters: storm trains, sweepers and clearing vehicles only
Storm trains and clearing vehicles are in operations.winter_per_km_year for every mode.
"""

from __future__ import annotations

import numpy as np

from .network import Line

MODES = ("targeted", "full", "none")


def mw_per_km(P) -> float:
    """Heating power per km of dual guideway while on (MW/km)."""
    return P["winter.heating.w_per_m2"] * P["winter.heating.area_per_m"] * 1000.0 / 1e6


def critical_km(line: Line, P) -> float:
    bridges = sum(s.bridge_km for s in line.segments)
    stations = len(line.stations) * P["winter.heating.station_heated_km"]
    return np.minimum(bridges + stations + line.length_km * P["winter.heating.extra_critical_share"], line.length_km)


def storm_mw(line: Line, P, mode: str) -> float:
    """Heating power running during icing, on top of the trains (MW)."""
    if mode == "targeted":
        return critical_km(line, P) * mw_per_km(P)
    if mode == "full":
        return line.length_km * mw_per_km(P)
    return 0.0


def night_mw(line: Line, P, mode: str, night_hours: float) -> float:
    """Average overnight warming power on an icing night (whole line in rotation), MW."""
    if mode != "targeted":
        return 0.0
    return line.length_km * mw_per_km(P) * P["winter.heating.warm_hours_per_km"] / night_hours


def heating_mwh(line: Line, P, mode: str) -> float:
    """Heating energy per year (MWh)."""
    storm = storm_mw(line, P, mode) * P["winter.heating.icing_hours"]
    night = 0.0
    if mode == "targeted":
        night = line.length_km * mw_per_km(P) * P["winter.heating.warm_hours_per_km"] * P["winter.heating.icing_nights"]
    return storm + night


def heater_capital(line: Line, P, mode: str):
    """Heaters along the whole line (targeted needs them everywhere for the overnight warming). MUSD."""
    return 0.0 if mode == "none" else line.length_km * P["winter.heating.heater_capex_per_km"]
