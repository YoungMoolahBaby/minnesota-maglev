"""Capital cost, land, wetlands, operating cost and materials.

Functions take P, a mapping of parameter name -> float (nominal run) or numpy array (Monte Carlo),
so one code path serves both. Money is in USD millions (2026).
"""

from __future__ import annotations

import numpy as np

from .network import Line, Segment

ACRE_M2 = 4046.8564224


def segment_quantities(s: Segment) -> dict[str, float]:
    """Kilometres by structure type for one segment (no prices)."""
    rural = s.rural_guideway_km
    return {
        "elevated_km": rural * s.structure.get("elevated", 0.0),
        "at_grade_km": rural * s.structure.get("at_grade", 0.0),
        "urban_viaduct_km": s.urban_km * (1 - s.urban_tunnel),
        "tunnel_km": s.urban_km * s.urban_tunnel,
        "bridge_m": s.bridge_km * 1000.0,
        "route_km": s.length_km,
    }


def segment_capital(s: Segment, P) -> dict:
    q = segment_quantities(s)
    g = "costs.guideway."
    civil = (
        q["elevated_km"] * P[g + "elevated"]
        + q["at_grade_km"] * P[g + "at_grade"]
        + q["urban_viaduct_km"] * P[g + "urban_viaduct"]
        + q["tunnel_km"] * P[g + "tunnel"]
        + q["bridge_m"] * P[g + "bridge_per_m"]
    )
    # the frost zone is a fixed flag (low == high), so its mean is the flag in both modes
    frost_key = "frost_north" if float(np.mean(P[f"climate.{s.zone}.frost"])) >= 0.5 else "frost_south"
    adders = civil * (
        P["costs.adders.floodplain"] * s.floodplain
        + P["costs.adders.peat_soft_ground"] * s.peat
        + P[f"costs.adders.{frost_key}"]
    )
    systems = q["route_km"] * P["costs.systems.propulsion_power_control"]

    # land: surface width per structure type (tunnels and bridges take little surface land)
    width_km_m = (
        q["elevated_km"] * P["land.row_width.elevated"]
        + q["at_grade_km"] * P["land.row_width.at_grade"]
        + q["urban_viaduct_km"] * P["land.row_width.urban"]
        + q["bridge_m"] / 1000.0 * P["land.row_width.elevated"]
    )
    acres = width_km_m * 1000.0 / ACRE_M2
    price = sum(share * P[f"land.price_per_acre.{cls}"] for cls, share in s.land.items())
    land = acres * price * P["land.acquisition_multiplier"]

    wet_share = s.land.get("wetland", 0.0)
    filled_acres = wet_share * 1000.0 / ACRE_M2 * (
        q["elevated_km"] * P["land.row_width.elevated"] * P["land.wetlands.impact_fraction_elevated"]
        + q["at_grade_km"] * P["land.row_width.at_grade"] * P["land.wetlands.impact_fraction_at_grade"]
    )
    wetlands = filled_acres * P["land.wetlands.replacement_ratio"] * P["land.wetlands.credit_price"]

    return {
        "quantities": q,
        "guideway": civil,
        "adders": adders,
        "systems": systems,
        "land": land,
        "wetlands": wetlands,
        "acres": acres,
        "wetland_acres_filled": filled_acres,
    }


def fleet_size(round_trip_s: float, P) -> np.ndarray | float:
    headway_s = 3600.0 / P["system.service.trains_per_hour"]
    in_service = np.ceil(round_trip_s / headway_s)
    return np.ceil(in_service * (1 + P["costs.vehicles.spare_ratio"]))


def line_capital(line: Line, P, new_stations: list, end_to_end_s: float) -> dict:
    segs = [segment_capital(s, P) for s in line.segments]
    total = lambda k: sum(sc[k] for sc in segs)  # noqa: E731

    stations = sum(P[f"costs.stations.{c.type}"] for c in new_stations)
    switches = len(new_stations) * P["costs.stations.switches_per_station"] * P["costs.guideway.switch_each"]
    depot = P["costs.depot.per_line"]
    turnaround_s = 15 * 60
    trains = fleet_size(2 * (end_to_end_s + turnaround_s), P)
    vehicles = trains * P["costs.vehicles.sections_per_train"] * P["costs.vehicles.per_section"]

    construction = total("guideway") + total("adders") + total("systems") + stations + switches + depot + vehicles
    soft = construction * P["costs.soft.engineering_admin"]
    land = total("land") + total("wetlands")
    base = construction + soft + land
    contingency = base * P["costs.soft.contingency"]
    return {
        "segments": segs,
        "guideway": total("guideway"),
        "adders": total("adders"),
        "systems": total("systems"),
        "stations": stations,
        "switches": switches,
        "depot": depot,
        "vehicles": vehicles,
        "trains": trains,
        "construction": construction,
        "soft": soft,
        "land": total("land"),
        "wetlands": total("wetlands"),
        "contingency": contingency,
        "total": base + contingency,
    }


def line_operating(line: Line, P, trains, kwh_per_train_km: float) -> dict:
    """Annual operating cost, MUSD/year."""
    train_km = 2 * P["system.service.trains_per_hour"] * P["system.service.service_hours"] * 365 * line.length_km
    energy = train_km * kwh_per_train_km * P["costs.operations.energy_price"] / 1e6
    om = line.length_km * P["costs.operations.om_per_km_year"]
    winter = sum(
        s.length_km * P["costs.operations.winter_per_km_year"] * P[f"climate.{s.zone}.snowfall"] / 130.0
        for s in line.segments
    )
    staff = trains * P["costs.operations.staff_per_train_year"]
    return {
        "train_km": train_km,
        "energy": energy,
        "om": om,
        "winter": winter,
        "staff": staff,
        "total": energy + om + winter + staff,
    }


def line_materials(line: Line, P: dict[str, float]) -> dict[str, float]:
    """Material takeoff (nominal) and the ore behind it. Tonnes and m^3."""
    m = "materials.guideway."
    concrete = steel_struct = 0.0
    stator = alu = guide = cu = 0.0
    for s in line.segments:
        q = segment_quantities(s)
        c = (
            q["elevated_km"] * P[m + "concrete_elevated"]
            + q["at_grade_km"] * P[m + "concrete_at_grade"]
            + (q["urban_viaduct_km"] + q["bridge_m"] / 1000.0) * P[m + "concrete_urban"]
            + q["tunnel_km"] * P["materials.tunnel.concrete"]
        )
        concrete += c
        steel_struct += c * (P[m + "rebar_per_m3"] + P[m + "strand_per_m3"])
        stator += q["route_km"] * P[m + "stator_steel"]
        alu += q["route_km"] * P[m + "stator_aluminium"]
        guide += q["route_km"] * P[m + "guidance_steel"]
        cu += q["route_km"] * P[m + "copper"]
    o = "materials.ore."
    steel = steel_struct + stator + guide
    pellets = steel * P[o + "pellets_per_t_steel"]
    return {
        "concrete_m3": concrete,
        "cement_t": concrete * P[o + "cement_per_m3"],
        "aggregate_t": concrete * P[o + "aggregate_per_m3"],
        "rebar_strand_t": steel_struct,
        "electrical_steel_t": stator,
        "guidance_steel_t": guide,
        "steel_total_t": steel,
        "iron_pellets_t": pellets,
        "crude_taconite_t": pellets * P[o + "taconite_per_t_pellets"],
        "aluminium_t": alu,
        "copper_t": cu,
        "cu_ore_t": cu / (P[o + "cu_ore_grade"] * P[o + "cu_recovery"]),
    }


def curve_radius_note(P: dict[str, float]) -> float:
    from .geo import min_curve_radius_m

    return min_curve_radius_m(
        P["system.vehicle.cruise_speed"],
        P["system.geometry.superelevation_max"],
        P["system.geometry.unbalanced_lateral"],
    )

