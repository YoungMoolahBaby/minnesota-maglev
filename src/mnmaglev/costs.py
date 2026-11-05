"""Capital cost, land, wetlands, operating cost and materials.

Functions take P, a mapping of parameter name -> float (nominal run) or numpy array (Monte Carlo),
so one code path serves both. Money is in USD millions (2026).
"""

from __future__ import annotations

import numpy as np

from .security import capital as security_capital
from .security import operating as security_operating
from .winter import heater_capital

from .network import CORRIDOR, Line, Segment

ACRE_M2 = 4046.8564224


def land_price_per_acre(s: Segment, P):
    """Mean price per acre over the segment's land classes; on measured lines, county parcel values
    (assessed land EMV x land.parcels.emv_to_market) where the counties publish them. Highway
    right-of-way (existing_corridor) costs land.corridor.price_factor x the price of the land around it."""
    others = {c: v for c, v in s.land.items() if c != CORRIDOR}
    base = sum(v * P[f"land.price_per_acre.{c}"] for c, v in others.items())
    corr = s.land.get(CORRIDOR, 0.0)
    total = sum(others.values())
    around = base / total if total > 0 else P["land.price_per_acre.cropland_central"]
    if s.parcel_coverage > 0:
        around = (s.parcel_coverage * s.parcel_price / 1e6 * P["land.parcels.emv_to_market"]
                  + (1 - s.parcel_coverage) * around)
        base = around * total
    if not corr:
        return base
    return base + corr * P["land.corridor.price_factor"] * around


def public_land_factor(s: Segment, P):
    """Extra land cost on public and tribal land, as a share of the segment's land cost: replacement
    land for Section 4(f) land used (public parks, refuges, ...), the negotiated premium on tribal land."""
    return (s.section_4f * P["land.public.section_4f_replacement"]
            + s.tribal * (P["land.tribal.consent_multiplier"] - 1))


TAKE_WIDTHS = (("elevated", "elevated"), ("at_grade", "at_grade"), ("urban_viaduct", "urban"))


def building_takes(s: Segment, widths: dict) -> tuple[dict, dict]:
    """Buildings a strip takes along the segment's takeable km (outside the urban ends, bridges and
    freeway right-of-way): structure type -> strip width (m). Returns (count, footprint m2) by group;
    a building is taken when the strip touches it (gis.building_takes)."""
    if not s.buildings:
        return {}, {}
    km_free = s.rural_guideway_km * (1 - s.land.get(CORRIDOR, 0.0))
    n, m2 = {}, {}
    for grp, d in s.buildings.items():
        n[grp] = m2[grp] = 0.0
        for typ, w in widths.items():
            km = km_free * s.structure.get(typ, 0.0)
            n[grp] = n[grp] + km * (w * d["n"] + d["side"]) / 1000.0
            m2[grp] = m2[grp] + km * (w * d["area"] + d["aside"]) / 1000.0
    return n, m2


def building_cost(n: dict, m2: dict, P):
    """MUSD to buy, clear and relocate the buildings taken: homes by count (assessed building value
    + Uniform Act relocation), businesses and farm buildings by footprint, demolition by footprint."""
    if not n:
        return 0.0
    b = "land.buildings."
    return (n.get("residential", 0.0) * (P[b + "home_value"] * P["land.parcels.emv_to_market"] + P[b + "home_relocation"])
            + n.get("nonresidential", 0.0) * P[b + "business_relocation"]
            + (m2.get("nonresidential", 0.0) * P[b + "nonresidential_value_per_m2"]
               + m2.get("agriculture", 0.0) * P[b + "farm_value_per_m2"]
               + sum(m2.values()) * P[b + "demolition_per_m2"]) / 1e6)


def segment_quantities(s: Segment) -> dict[str, float]:
    """Kilometres by structure type for one segment (no prices)."""
    rural = s.rural_guideway_km
    return {
        "elevated_km": rural * s.structure.get("elevated", 0.0),
        "at_grade_km": rural * s.structure.get("at_grade", 0.0),
        # urban ends, plus built-up km between them (suburbs) where the GIS measured them
        "urban_viaduct_km": s.urban_km * (1 - s.urban_tunnel) + rural * s.structure.get("urban_viaduct", 0.0),
        "tunnel_km": s.urban_km * s.urban_tunnel,
        "bridge_m": s.bridge_km * 1000.0,
        "route_km": s.length_km,
    }


def tall_pier_excess(s: Segment, P):
    """m x km of guideway above costs.guideway.pier_height_ref (measured lines; 0 elsewhere)."""
    if not s.pier_excess:
        return 0.0
    refs = sorted(s.pier_excess)
    return np.interp(P["costs.guideway.pier_height_ref"], refs, [s.pier_excess[r] for r in refs])


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
    # piers taller than the elevated price covers (ravine and valley crossings for the grade limit)
    new_row = P["system.corridor.new_right_of_way"]  # 0: an existing railroad, nothing new to buy or dig
    tall_piers = tall_pier_excess(s, P) * P[g + "tall_pier_per_m"] * new_row
    civil = civil + tall_piers
    # the frost zone is a fixed flag (low == high), so its mean is the flag in both modes
    frost_key = "frost_north" if float(np.mean(P[f"climate.{s.zone}.frost"])) >= 0.5 else "frost_south"
    adders = civil * (
        P["costs.adders.floodplain"] * s.floodplain
        + P["costs.adders.peat_soft_ground"] * s.peat
        + P["costs.adders.highway_corridor"] * s.land.get(CORRIDOR, 0.0)
        + P[f"costs.adders.{frost_key}"]
    ) * new_row
    systems = q["route_km"] * P["costs.systems.propulsion_power_control"]

    # land: surface width per structure type (tunnels and bridges take little surface land)
    width_km_m = (
        q["elevated_km"] * P["land.row_width.elevated"]
        + q["at_grade_km"] * P["land.row_width.at_grade"]
        + q["urban_viaduct_km"] * P["land.row_width.urban"]
        + q["bridge_m"] / 1000.0 * P["land.row_width.elevated"]
    )
    acres = width_km_m * 1000.0 / ACRE_M2
    price = land_price_per_acre(s, P)
    land = acres * price * P["land.acquisition_multiplier"] * new_row
    public_land = land * public_land_factor(s, P)

    wet_share = s.land.get("wetland", 0.0)
    filled_acres = wet_share * 1000.0 / ACRE_M2 * (
        q["elevated_km"] * P["land.row_width.elevated"] * P["land.wetlands.impact_fraction_elevated"]
        + q["at_grade_km"] * P["land.row_width.at_grade"] * P["land.wetlands.impact_fraction_at_grade"]
    )
    wetlands = filled_acres * P["land.wetlands.replacement_ratio"] * P["land.wetlands.credit_price"] * new_row

    taken, taken_m2 = building_takes(s, {typ: P[f"land.row_width.{w}"] for typ, w in TAKE_WIDTHS})
    buildings = building_cost(taken, taken_m2, P) * new_row

    return {
        "quantities": q,
        "guideway": civil,
        "tall_piers": tall_piers,
        "adders": adders,
        "systems": systems,
        "land": land,
        "wetlands": wetlands,
        "buildings": buildings,
        "public_land": public_land,
        "buildings_taken": taken,
        "acres": acres,
        "wetland_acres_filled": filled_acres,
    }


LEASABLE_CLASSES = ("cropland_south", "cropland_central")


def segment_reserve(s: Segment, P) -> dict:
    """Land and build-for-two provisions to hold room for a second system beside this segment."""
    q = segment_quantities(s)
    g = "costs.guideway."
    rural_km = q["elevated_km"] + q["at_grade_km"]
    # B's own right-of-way (same structure mix as A) + the construction separation between them
    rural_width_km_m = (
        q["elevated_km"] * P["land.row_width.elevated"]
        + q["at_grade_km"] * P["land.row_width.at_grade"]
        + rural_km * P["land.reserve.construction_separation"]
    )
    rural_acres = rural_width_km_m * 1000.0 / ACRE_M2
    urban_acres = q["urban_viaduct_km"] * 1000.0 * P["land.reserve.width_urban"] / ACRE_M2
    price = land_price_per_acre(s, P)
    land = (rural_acres + urban_acres) * price * P["land.reserve.acquisition_multiplier"]
    land = land * (1 + public_land_factor(s, P))
    # buildings in the strip beside A: B's right-of-way + the separation (country), width_urban (suburbs)
    sep = P["land.reserve.construction_separation"]
    taken, taken_m2 = building_takes(s, {"elevated": P["land.row_width.elevated"] + sep,
                                         "at_grade": P["land.row_width.at_grade"] + sep,
                                         "urban_viaduct": P["land.reserve.width_urban"]})
    urban_civil = q["urban_viaduct_km"] * P[g + "urban_viaduct"] + q["tunnel_km"] * P[g + "tunnel"]
    bridge_civil = q["bridge_m"] * P[g + "bridge_per_m"]
    leasable = sum(s.land.get(c, 0.0) for c in LEASABLE_CLASSES)
    return {
        "acres": rural_acres + urban_acres,
        "land": land,
        "buildings": building_cost(taken, taken_m2, P),
        "urban_provision": urban_civil * P["costs.reserve.urban_provision"],
        "bridge_provision": bridge_civil * P["costs.reserve.bridge_provision"],
        "lease_income": rural_acres * leasable * P["land.reserve.lease_income"],
    }


def line_reserve(line: Line, P, new_stations: list, construction, soft_rate, contingency_rate) -> dict:
    """What holding room for a second system costs on this line, contingency included."""
    segs = [segment_reserve(s, P) for s in line.segments]
    total = lambda k: sum(sr[k] for sr in segs)  # noqa: E731
    stations = sum(P[f"costs.stations.{c.type}"] for c in new_stations) * P["costs.reserve.station_provision"]
    provisions = total("urban_provision") + total("bridge_provision") + stations
    review = construction * P["costs.reserve.review_extra"]
    base = total("land") + total("buildings") + provisions * (1 + soft_rate) + review
    return {
        "segments": segs,
        "acres": total("acres"),
        "land": total("land"),
        "buildings": total("buildings"),
        "urban_provision": total("urban_provision"),
        "bridge_provision": total("bridge_provision"),
        "station_provision": stations,
        "review": review,
        "contingency": base * contingency_rate * P["system.corridor.new_right_of_way"],
        "total": base * (1 + contingency_rate) * P["system.corridor.new_right_of_way"],
        "lease_income": total("lease_income"),
    }


def fleet_size(round_trip_s: float, P) -> np.ndarray | float:
    headway_s = 3600.0 / P["system.service.trains_per_hour"]
    in_service = np.ceil(round_trip_s / headway_s)
    return np.ceil(in_service * (1 + P["costs.vehicles.spare_ratio"]))


def line_capital(line: Line, P, new_stations: list, end_to_end_s: float, local_supply: bool = False,
                 heating: str = "none", security: str = "none") -> dict:
    segs = [segment_capital(s, P) for s in line.segments]
    total = lambda k: sum(sc[k] for sc in segs)  # noqa: E731

    stations = sum(P[f"costs.stations.{c.type}"] for c in new_stations)
    switches = len(new_stations) * P["costs.stations.switches_per_station"] * P["costs.guideway.switch_each"]
    depot = P["costs.depot.per_line"]
    turnaround_s = 15 * 60
    trains = fleet_size(2 * (end_to_end_s + turnaround_s), P)
    vehicles = trains * P["costs.vehicles.sections_per_train"] * P["costs.vehicles.per_section"]

    heaters = heater_capital(line, P, heating)
    patrols = security_capital(line, P, security)  # ground robots, drone docks, control room
    construction = (total("guideway") + total("adders") + total("systems") + stations + switches + depot
                    + vehicles + heaters + patrols)
    # local supply (Minnesota beam and stator plants, tailings aggregate, supply contracts)
    local = local_supply_savings(line, P, total("systems"))
    contingency_rate = P["costs.soft.contingency"]
    if local_supply:
        construction = construction - local["construction"]
        contingency_rate = contingency_rate - local["contingency_points"]
    soft = construction * P["costs.soft.engineering_admin"]
    land = total("land") + total("wetlands") + total("buildings") + total("public_land")
    base = construction + soft + land
    contingency = base * contingency_rate
    # first-of-kind premium: extra growth on the maglev-specific items, full on phase 1 and partly
    # on later lines once the technology runs (params costs.soft.first_of_kind*)
    fok_rate = P["costs.soft.first_of_kind"] * (1.0 if line.phase == 1 else P["costs.soft.first_of_kind_later"])
    first_of_kind = (total("systems") + vehicles + switches) * (1 + P["costs.soft.engineering_admin"]) * fok_rate
    # the reserve is priced for every line; it counts in the total only where the line opts in
    reserve = line_reserve(line, P, new_stations, construction,
                           P["costs.soft.engineering_admin"], contingency_rate)
    without = base + contingency + first_of_kind
    return {
        "segments": segs,
        "guideway": total("guideway"),
        "adders": total("adders"),
        "systems": total("systems"),
        "stations": stations,
        "switches": switches,
        "depot": depot,
        "vehicles": vehicles,
        "heaters": heaters,
        "security": patrols,
        "trains": trains,
        "construction": construction,
        "soft": soft,
        "land": total("land"),
        "wetlands": total("wetlands"),
        "buildings": total("buildings"),
        "public_land": total("public_land"),
        "contingency": contingency,
        "first_of_kind": first_of_kind,
        "reserve": reserve,
        "reserve_included": line.reserve,
        "local_supply": local,
        "local_supply_included": local_supply,
        "total_without_reserve": without,
        "total": without + reserve["total"] if line.reserve else without,
    }


def line_operating(line: Line, P, trains, kwh_per_train_km: float, reserve_lease=0.0, heating_mwh=0.0,
                   security: str = "none") -> dict:
    """Annual operating cost, MUSD/year. reserve_lease: farm lease income from a held reserve."""
    train_km = 2 * P["system.service.trains_per_hour"] * P["system.service.service_hours"] * 365 * line.length_km
    energy = (train_km * kwh_per_train_km + heating_mwh * 1000.0) * P["costs.operations.energy_price"] / 1e6
    om = line.length_km * P["costs.operations.om_per_km_year"] + train_km * P["costs.operations.per_train_km"] / 1e6
    winter = sum(
        s.length_km * P["costs.operations.winter_per_km_year"] * P[f"climate.{s.zone}.snowfall"] / 130.0
        for s in line.segments
    )
    staff = trains * P["costs.operations.staff_per_train_year"]
    patrols = security_operating(line, P, security)["total"]
    return {
        "train_km": train_km,
        "energy": energy,
        "om": om,
        "winter": winter,
        "staff": staff,
        "security": patrols,
        "reserve_lease_income": reserve_lease,
        "total": energy + om + winter + staff + patrols - reserve_lease,
    }


def segment_concrete(s: Segment, P) -> float:
    """Concrete in one segment, m^3 (works with scalar or array parameters)."""
    m = "materials.guideway."
    q = segment_quantities(s)
    return (
        q["elevated_km"] * P[m + "concrete_elevated"]
        + q["at_grade_km"] * P[m + "concrete_at_grade"]
        + (q["urban_viaduct_km"] + q["bridge_m"] / 1000.0) * P[m + "concrete_urban"]
        + q["tunnel_km"] * P["materials.tunnel.concrete"]
    )


def line_materials(line: Line, P: dict[str, float], local_supply: bool = False) -> dict:
    """Material takeoff (nominal), the ore behind it, the materials bill and Minnesota's ore tax."""
    m = "materials.guideway."
    concrete = sum(segment_concrete(s, P) for s in line.segments)
    route_km = line.length_km
    rebar = concrete * P[m + "rebar_per_m3"]
    strand = concrete * P[m + "strand_per_m3"]
    stator = route_km * P[m + "stator_steel"]
    alu = route_km * P[m + "stator_aluminium"]
    guide = route_km * P[m + "guidance_steel"]
    cu = route_km * P[m + "copper"]
    o = "materials.ore."
    steel = rebar + strand + stator + guide
    pellets = steel * P[o + "pellets_per_t_steel"]
    aggregate = concrete * P[o + "aggregate_per_m3"]
    pr = "materials.prices."
    bill = {  # MUSD
        "concrete": concrete * P[pr + "concrete"] / 1e6,
        "rebar": rebar * P[pr + "rebar"] / 1e6,
        "strand": strand * P[pr + "strand"] / 1e6,
        "electrical_steel": stator * P[pr + "electrical_steel"] / 1e6,
        "guidance_steel": guide * P[pr + "structural_steel"] / 1e6,
        "copper": cu * P[pr + "copper"] / 1e6,
        "aluminium": alu * P[pr + "aluminium"] / 1e6,
    }
    bill["total"] = sum(bill.values())
    share = P["materials.mn_ore.pellet_share_local" if local_supply else "materials.mn_ore.pellet_share_market"]
    mn_pellets = pellets * share
    return {
        "concrete_m3": concrete,
        "cement_t": concrete * P[o + "cement_per_m3"],
        "aggregate_t": aggregate,
        "rebar_strand_t": rebar + strand,
        "electrical_steel_t": stator,
        "guidance_steel_t": guide,
        "steel_total_t": steel,
        "iron_pellets_t": pellets,
        "crude_taconite_t": pellets * P[o + "taconite_per_t_pellets"],
        "aluminium_t": alu,
        "copper_t": cu,
        "cu_ore_t": cu / (P[o + "cu_ore_grade"] * P[o + "cu_recovery"]),
        "bill_musd": bill,
        "mn_pellets_t": mn_pellets,
        "mn_production_tax_musd": mn_pellets * P["materials.mn_ore.production_tax"] / 1e6,
    }


def local_supply_savings(line: Line, P, systems) -> dict:
    """What the local-supply policy saves on this line (MUSD, before soft costs and contingency)."""
    g, ls = "costs.guideway.", "costs.local_supply."
    beam_civil = sum(
        segment_quantities(s)["elevated_km"] * P[g + "elevated"]
        + segment_quantities(s)["at_grade_km"] * P[g + "at_grade"]
        for s in line.segments
    )
    north_aggregate_t = sum(
        segment_concrete(s, P) * P["materials.ore.aggregate_per_m3"] for s in line.segments if s.zone == "north"
    )
    beams = beam_civil * P[ls + "beam_plant_saving"]
    stators = systems * P[ls + "stator_plant_saving"]
    tailings = north_aggregate_t * P[ls + "tailings_share"] * P[ls + "tailings_saving_per_t"] / 1e6
    return {
        "beam_plant": beams,
        "stator_plant": stators,
        "tailings": tailings,
        "construction": beams + stators + tailings,
        "contingency_points": P[ls + "contingency_points"],
        "tailings_t": north_aggregate_t * P[ls + "tailings_share"],
    }


def curve_radius_note(P: dict[str, float]) -> float:
    from .geo import min_curve_radius_m

    return min_curve_radius_m(
        P["system.vehicle.cruise_speed"],
        P["system.geometry.superelevation_max"],
        P["system.geometry.unbalanced_lateral"],
    )

