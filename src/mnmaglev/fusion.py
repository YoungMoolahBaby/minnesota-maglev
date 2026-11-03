"""The megaproject's own fusion fleet, sized from the network's real peak (power.py).

Units are added phase by phase so the fleet always covers the 1-second peak of everything built so
far, plus headroom and a spare unit (no batteries). Everything the trains don't use is surplus for
neighbouring users or the grid. Works with scalar or Monte Carlo parameters for the money; the
sizing itself is done once, from the nominal day profile.
"""

from __future__ import annotations

import math

import numpy as np

from .kinematics import line_summary
from .network import Line
from .power import demand_summary, line_day_profile
from .winter import critical_km, heating_mwh, night_mw, storm_mw

HOURS_PER_YEAR = 8760.0


def annual_demand_mwh(line: Line, P) -> float:
    """Year-weighted traction energy from the energy model (MWh/yr)."""
    s = line_summary(line, P)
    train_km = 2 * P["system.service.trains_per_hour"] * P["system.service.service_hours"] * 365 * line.length_km
    return train_km * s["kwh_per_train_km"] / 1000.0


def size_by_phase(lines: list[Line], P0: dict[str, float], heating: str = "none") -> list[dict]:
    """Cumulative demand, peaks and units per phase (nominal; sizing is a design decision)."""
    f = "power.fusion."
    unit = P0[f + "unit_mwe"]
    phases = sorted({l.phase for l in lines})
    profiles = {l.id: line_day_profile(l, P0, "winter") for l in lines}  # winter = the heavier season
    mwh = {l.id: annual_demand_mwh(l, P0) for l in lines}
    out, prev_units = [], 0
    for ph in phases:
        built = [l for l in lines if l.phase <= ph]
        d = demand_summary(sum(profiles[l.id] for l in built))
        storm = sum(storm_mw(l, P0, heating) for l in built)  # icing doesn't wait for quiet hours
        night_hours = 24.0 - P0["system.service.service_hours"]
        night = sum(night_mw(l, P0, heating, night_hours) for l in built)
        units = math.ceil((d["peak_mw"] + storm) * (1 + P0[f + "sizing_margin"]) / unit) + int(P0[f + "spare_units"])
        units = max(units, prev_units)
        heat_mwh = sum(heating_mwh(l, P0, heating) for l in built)
        demand = sum(mwh[l.id] for l in built) + heat_mwh
        out.append({
            "phase": ph,
            "demand_mwh": demand,
            "avg_mw": demand / HOURS_PER_YEAR,
            "avg_service_mw": d["avg_service_mw"],
            "peak_mw": d["peak_mw"],
            "peak_1min_mw": d["peak_1min_mw"],
            "units": units,
            "new_units": units - prev_units,
            "capacity_mw": units * unit,
            "heating": heating,
            "storm_heating_mw": storm,
            "night_warming_mw": night,
            "night_idle_mw": (units - int(P0[f + "spare_units"])) * unit,
            "heating_mwh": heat_mwh,
            "critical_km": sum(critical_km(l, P0) for l in built) if heating == "targeted" else
                           (sum(l.length_km for l in built) if heating == "full" else 0.0),
        })
        prev_units = units
    return out


def fleet_money(sizing: list[dict], P) -> list[dict]:
    """Capital (new units), annual O&M, surplus and its value, grid energy avoided. MUSD."""
    f = "power.fusion."
    soft, cont = P["costs.soft.engineering_admin"], P["costs.soft.contingency"]
    out = []
    b = np.log2(1 - P[f + "learning_rate"])  # n-th unit costs first x n^b
    for s in sizing:
        first = s["units"] - s["new_units"] + 1
        factor = sum(np.power(float(n), b) for n in range(first, s["units"] + 1)) if s["new_units"] else 0.0
        capital = factor * P[f + "unit_mwe"] * P[f + "capex_per_kw"] / 1000.0  # MW x $/kW / 1000 = MUSD
        production = s["capacity_mw"] * P[f + "capacity_factor"] * HOURS_PER_YEAR
        surplus = np.maximum(production - s["demand_mwh"], 0.0)
        out.append({
            **s,
            "capital": capital * (1 + soft) * (1 + cont),
            "om_per_year": s["capacity_mw"] * 1000.0 * P[f + "fixed_om_per_kw_year"] / 1e6,
            "production_mwh": production,
            "surplus_mwh": surplus,
            "surplus_value_per_year": surplus * P[f + "surplus_value"] / 1e6,
            "grid_energy_avoided_per_year": s["demand_mwh"] * P["costs.operations.energy_price"] * 1000.0 / 1e6,
        })
    return out
