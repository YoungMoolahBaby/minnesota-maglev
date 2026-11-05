"""Ridership, revenue and benefits (phase 7).

1. Maglev travel times between every pair of stations: a station graph whose nodes are (station,
   line); a leg is an edge of run time plus a dwell at the station it arrives at, and changing lines
   costs the mean planned connection at the hub.
2. The travel market: FHWA NextGen NHTS 2022 trips between markets (network/markets.yaml), by
   distance band and mode (network/demand_base.yaml, `mnmaglev demand-data`), grown to the forecast
   year. Markets inside one NHTS zone (Duluth - Iron Range, Rochester - Winona, the rest-of-state
   zones) get a gravity estimate fitted to the other pairs.
3. Mode choice, per distance band and per current mode: today's drivers choose between car and
   maglev, today's flyers between air and maglev (binary logits on generalized cost in minutes,
   California HSR model weights), so the maglev doesn't take air travellers in proportion to car
   ones (the logit's IIA problem). The car-side constant is the conventional rail constant fitted to
   the Hiawatha's actual FY25 riders (not to a forecast) plus a premium; the air-side constant is
   fitted to observed HSR shares of the rail + air market (reference/demand_calibration.yaml).
4. Benefits (USDOT BCA guidance, Dec 2025, rules): travellers' consumer surplus from the logit,
   fare revenue, unperceived car costs and car externalities avoided, over 30 years at 7%, with the
   residual value.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import yaml

from . import NETWORK_DIR
from .geo import haversine_km
from .kinematics import run_line
from .network import City, Line

KM_PER_MILE = 1.609344


# ---------------------------------------------------------------- 1. maglev travel times
def station_graph(lines: list[Line], P) -> dict:
    """Fastest maglev trip between every pair of stations: minutes on board (incl. dwells at
    intermediate stops) plus transfers, the number of line changes and the stations passed."""
    nodes: list[tuple[str, str]] = []
    index: dict[tuple[str, str], int] = {}

    def node(station: str, line_id: str) -> int:
        k = (station, line_id)
        if k not in index:
            index[k] = len(nodes)
            nodes.append(k)
        return index[k]

    dwell = P["system.vehicle.dwell"] / 60.0
    transfer = (P["system.service.min_transfer"] + P["system.service.max_transfer_wait"]) / 2.0
    edges = []
    for line in lines:
        for leg in run_line(line, P):
            a, b = node(leg.start, line.id), node(leg.end, line.id)
            edges.append((a, b, leg.time_s / 60.0 + dwell))
    by_station: dict[str, list[int]] = {}
    for (s, _), i in index.items():
        by_station.setdefault(s, []).append(i)

    n = len(nodes)
    time = np.full((n, n), np.inf)
    changes = np.zeros((n, n))
    nxt = np.full((n, n), -1, dtype=int)
    np.fill_diagonal(time, 0.0)
    for i in range(n):
        nxt[i, i] = i
    for a, b, t in edges:
        for u, v in ((a, b), (b, a)):
            time[u, v], nxt[u, v] = t, v
    for ids in by_station.values():
        for a, b in itertools.permutations(ids, 2):
            time[a, b], nxt[a, b], changes[a, b] = transfer - dwell, b, 1.0  # the arrival dwell is part of it
    for k in range(n):  # Floyd-Warshall, ~50 nodes
        via = time[:, [k]] + time[[k], :]
        better = via < time - 1e-9
        changes = np.where(better, changes[:, [k]] + changes[[k], :], changes)
        nxt = np.where(better, nxt[:, [k]], nxt)
        time = np.where(better, via, time)

    def path(i: int, j: int) -> list[str]:
        out = [nodes[i][0]]
        while i != j:
            i = int(nxt[i, j])
            if nodes[i][0] != out[-1]:
                out.append(nodes[i][0])
        return out

    od = {}
    for sa, sb in itertools.permutations(by_station, 2):
        i, j = min(((i, j) for i in by_station[sa] for j in by_station[sb]), key=lambda ij: time[ij])
        od[(sa, sb)] = {"minutes": float(time[i, j] - dwell), "changes": int(changes[i, j]), "path": path(i, j)}
    return od


def station_times(lines: list[Line], P) -> dict[tuple[str, str], dict]:
    return station_graph(lines, P)


# ---------------------------------------------------------------- 2. the market
def load_market() -> tuple[dict, dict]:
    markets = yaml.safe_load((NETWORK_DIR / "markets.yaml").read_text(encoding="utf-8"))
    base = yaml.safe_load((NETWORK_DIR / "demand_base.yaml").read_text(encoding="utf-8"))
    return markets, base


def _miles(a: City, b: City) -> float:
    return haversine_km(a.lat, a.lon, b.lat, b.lon) / KM_PER_MILE


def gravity_fit(markets: dict, base: dict, cities: dict[str, City]) -> tuple[float, float, float]:
    """ln T = c + alpha ln(Pa Pb) - beta ln d, on market pairs under 150 miles apart with trips of
    25+ miles (the regime of the pairs it fills in). Returns (c, alpha, beta)."""
    lo = [b[0] for b in base["bands_miles"]]
    first = lo.index(25)
    X, y = [], []
    for key, t in base["trips_2022"].items():
        a, b = key.split("|")
        d = _miles(cities[markets[a]["stations"][0]], cities[markets[b]["stations"][0]])
        trips = sum(t["all"][first:])
        if d < 150 and trips > 0:
            pa, pb = base["markets"][a]["population"], base["markets"][b]["population"]
            X.append([1.0, math.log(pa * pb), math.log(d)])
            y.append(math.log(trips))
    coef, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    return float(coef[0]), float(coef[1]), float(-coef[2])


def pair_bands(a: str, b: str, markets: dict, base: dict, cities: dict[str, City], fit) -> dict:
    """Trips (2022) by band for a market pair: NHTS where the markets lie in different zones, else
    a gravity estimate put in the band of their distance, all by car."""
    t = base["trips_2022"].get(f"{a}|{b}") or base["trips_2022"].get(f"{b}|{a}")
    if t:
        return {"source": "nhts", **t}
    c, alpha, beta = fit
    d = _miles(cities[markets[a]["stations"][0]], cities[markets[b]["stations"][0]])
    pa, pb = base["markets"][a]["population"], base["markets"][b]["population"]
    trips = math.exp(c + alpha * math.log(pa * pb) - beta * math.log(max(d, 10.0)))
    n = len(base["bands_miles"])
    k = max(i for i, (lo, _) in enumerate(base["bands_miles"]) if lo <= d)
    vals = [0.0] * n
    vals[k] = trips
    return {"source": "gravity", "all": vals, "vehicle": list(vals), "air": [0.0] * n, "rail": [0.0] * n,
            "work": [0.0] * n}


def extra_access(trip_miles: float, centre_road: float, P) -> float:
    """Minutes of extra driving to and from the stations for a trip shorter than the distance between
    them: its two ends lie at least (centre - trip) miles from the stations in total (triangle
    inequality), so zone-edge to zone-edge trips get no free ride to a central station."""
    return max(centre_road - trip_miles, 0.0) / P["demand.mode_choice.car_speed"] * 60.0


def band_miles(lo: float, hi: float, centre_road: float) -> float:
    """Representative road miles of trips in a band: the centre-to-centre distance if it falls in
    the band, else the band's middle (open top band: 50 miles past its lower edge)."""
    if lo <= centre_road < hi:
        return centre_road
    return (lo + hi) / 2.0 if hi < 5000 else max(lo + 50.0, centre_road)


# ---------------------------------------------------------------- 3. mode choice
def _vot(P) -> float:
    return P["demand.mode_choice.value_of_time"] / 60.0  # USD per minute


def car_gc(road_miles, P):
    """(generalized cost in minutes, door-to-door minutes) of driving."""
    t = road_miles / P["demand.mode_choice.car_speed"] * 60.0
    cost = road_miles * P["demand.mode_choice.car_perceived_cost"] / P["demand.benefits.car_occupancy"]
    return t + cost / _vot(P), t


def headway_penalty(trips_per_hour, P):
    return P["demand.mode_choice.headway_scale"] * np.log1p(60.0 / trips_per_hour / 60.0)


def maglev_gc(minutes: float, changes: int, road_miles: float, P):
    """(generalized cost, door-to-door minutes, fare USD) of a maglev trip."""
    mc = "demand.mode_choice."
    transfer = changes * (P["system.service.min_transfer"] + P["system.service.max_transfer_wait"]) / 2.0
    access = 2 * P[mc + "maglev_access"]
    terminal = P[mc + "maglev_wait_terminal"]
    fare = P[mc + "fare_boarding"] + P[mc + "fare_per_mile"] * road_miles
    gc = (minutes - transfer + access + P[mc + "out_of_vehicle_weight"] * (terminal + transfer)
          + headway_penalty(P["system.service.trains_per_hour"], P) + fare / _vot(P))
    return gc, minutes + access + terminal, fare


def _binary(utility_gap):
    """Share choosing the maglev when its utility exceeds the current mode's by utility_gap."""
    return 1.0 / (1.0 + math.exp(-utility_gap))


def air_gc(miles: float, P):
    """(generalized cost in minutes, door-to-door minutes) of flying miles (straight line)."""
    mc, bn = "demand.mode_choice.", "demand.benefits."
    flight = P[bn + "air_taxi"] + miles / P[bn + "air_speed"] * 60.0
    access = 2 * P[bn + "air_access"]
    gc = flight + access + P[mc + "out_of_vehicle_weight"] * P[mc + "air_wait_terminal"] + P[mc + "air_fare"] / _vot(P)
    return gc, flight + access + P[mc + "air_wait_terminal"]


def air_constant(P) -> tuple[float, float]:
    """(constant, scale) of the maglev-vs-air choice that best reproduce the observed HSR shares of
    the rail + air market: least squares of logit(share) on theta x (GC_air - GC_rail). The scale
    lets the air side be more sensitive to generalized cost than the car side (the observed share
    falls steeply between 4 and 5 hours)."""
    from . import ROOT

    mc = "demand.mode_choice."
    pts = yaml.safe_load((ROOT / "reference" / "demand_calibration.yaml").read_text(encoding="utf-8"))["air_rail_shares"]
    theta = P[mc + "ivt_coefficient"]
    x, y = [], []
    for q in pts:
        miles = haversine_km(*q["a"], *q["b"]) / KM_PER_MILE
        gc_rail, _, _ = maglev_gc(q["hours"] * 60.0, 0, miles * P[mc + "road_detour"], P)
        gc_air, _ = air_gc(miles, P)
        x.append(theta * (gc_air - gc_rail))
        y.append(math.log(q["share"] / (1 - q["share"])))
    scale, const = np.polyfit(np.array(x), np.array(y), 1)
    return float(const), float(scale)


def rail_constant(markets: dict, base: dict, cities: dict[str, City], P) -> float:
    """Conventional rail constant (utility vs car) that reproduces the Hiawatha's actual riders on
    the Chicago - Milwaukee market, solved by bisection."""
    mc, cal = "demand.mode_choice.", "demand.calibration."
    theta = P[mc + "ivt_coefficient"]
    t = pair_bands("milwaukee", "chicago", markets, base, cities, None)
    centre = _miles(cities["milwaukee"], cities["chicago"]) * P[mc + "road_detour"]
    years = 2025 - 2022
    grow = (1 + P["demand.market.growth"]) ** years
    trips_per_hour = 2 * P[cal + "hiawatha_round_trips"] / (2 * P["system.service.service_hours"])
    gc_rail = (P[cal + "hiawatha_minutes"] + 2 * P[mc + "maglev_access"]
               + P[mc + "out_of_vehicle_weight"] * P[mc + "rail_wait_terminal"]
               + headway_penalty(trips_per_hour, P) + P[cal + "hiawatha_fare"] / _vot(P))
    rows = []
    for (lo, hi), all_, veh in zip(base["bands_miles"], t["all"], t["vehicle"]):
        miles = band_miles(lo, hi, centre)
        if all_ > 0 and miles >= P["demand.market.min_trip_share"] * centre:
            gc_car, _ = car_gc(miles, P)
            rows.append((all_ * grow, gc_car, extra_access(miles, centre, P)))

    def riders(asc: float) -> float:
        return sum(trips * _binary(asc - theta * (gc_rail + extra - gc_car)) for trips, gc_car, extra in rows)

    lo, hi = -20.0, 20.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if riders(mid) < P[cal + "hiawatha_riders"] else (lo, mid)
    return (lo + hi) / 2


def ridership(lines: list[Line], cities: dict[str, City], P, markets=None, base=None, calib=None) -> dict:
    """Riders, diversion, revenue and benefits per market pair for the lines given, in the forecast year.
    calib: (markets, base, cities) to calibrate the rail constant and gravity model on (default: the
    market itself; the corridor screen calibrates on Minnesota's, which has the Hiawatha)."""
    if markets is None:
        markets, base = load_market()
    cal_m, cal_b, cal_c = calib or (markets, base, cities)
    mc, bn = "demand.mode_choice.", "demand.benefits."
    theta = P[mc + "ivt_coefficient"]
    asc = rail_constant(cal_m, cal_b, cal_c, P) + theta * P[mc + "maglev_premium"]
    asc_air, air_scale = air_constant(P)
    fit = gravity_fit(cal_m, cal_b, cal_c)
    od = station_graph(lines, P)
    served = {s for (s, _) in od}
    grow = (1 + P["demand.market.growth"]) ** (P["demand.market.forecast_year"] - 2022)
    induced = P[mc + "induced_share"]
    pairs = []
    for a, b in itertools.combinations(markets, 2):
        sa = [s for s in markets[a]["stations"] if s in served]
        sb = [s for s in markets[b]["stations"] if s in served]
        if not sa or not sb:
            continue
        s1, s2 = min(itertools.product(sa, sb), key=lambda st: od[st]["minutes"])
        trip = od[(s1, s2)]
        straight = _miles(cities[s1], cities[s2])
        if straight < P["demand.market.min_pair_miles"]:
            continue  # a commuter market, outside the intercity model's scope
        centre = straight * P[mc + "road_detour"]
        gc_mag, door_mag, fare = maglev_gc(trip["minutes"], trip["changes"], centre, P)
        t = pair_bands(a, b, markets, base, cities, fit)
        div = {"car": 0.0, "air": 0.0, "rail": 0.0, "other": 0.0}
        hours_saved = 0.0
        car_vmt = 0.0
        cs_minutes = 0.0
        market = 0.0
        for (lo, hi), all_, veh, air, rail in zip(base["bands_miles"], t["all"], t["vehicle"], t["air"], t["rail"]):
            miles = band_miles(lo, hi, centre)
            if all_ <= 0 or miles < P["demand.market.min_trip_share"] * centre:
                continue
            market += all_ * grow
            gc_car, door_car = car_gc(miles, P)
            gc_air, door_air = air_gc(miles / P[mc + "road_detour"], P)
            extra = extra_access(miles, centre, P)
            gap_ground = asc - theta * (gc_mag + extra - gc_car)  # today's drivers (and rail, bus, other)
            gap_air = asc_air - air_scale * theta * (gc_mag + extra - gc_air)  # today's flyers
            p_ground, p_air = _binary(gap_ground), _binary(gap_air)
            trips = all_ * grow
            ground = trips * max(all_ - air, 0.0) / all_
            flyers = trips * air / all_
            d_car = trips * veh / all_ * p_ground
            d_air = flyers * p_air
            d_rail = trips * rail / all_ * p_ground
            d_other = trips * max(all_ - veh - air - rail, 0.0) / all_ * p_ground
            # consumer surplus: the logsum gain of a binary choice, ln(1 + e^gap) / scale, in minutes
            cs_minutes += ground * math.log1p(math.exp(gap_ground)) / theta
            cs_minutes += flyers * math.log1p(math.exp(gap_air)) / (air_scale * theta)
            hours_saved += ((d_car + d_rail + d_other) * (door_car - door_mag - extra)
                            + d_air * (door_air - door_mag - extra)) / 60.0
            car_vmt += d_car * miles / P[bn + "car_occupancy"]
            div["car"] += d_car
            div["air"] += d_air
            div["rail"] += d_rail
            div["other"] += d_other
        diverted = sum(div.values())
        if diverted <= 0:
            continue
        riders = diverted / (1 - induced)
        new = riders - diverted
        cs_minutes += new * 0.5 * cs_minutes / diverted  # rule of half for induced trips
        pairs.append({
            "a": a, "b": b, "stations": (s1, s2), "path": trip["path"], "minutes": trip["minutes"],
            "changes": trip["changes"], "door_minutes": door_mag, "fare": fare, "miles": straight,
            "market": market, "riders": riders, "share": riders / market if market else 0.0,
            "diverted": div, "induced": new, "hours_saved": hours_saved, "car_vmt": car_vmt,
            "cs_minutes": cs_minutes,
            "source": t["source"],
        })
    return {"pairs": pairs, "asc": asc, "asc_air": asc_air, "air_scale": air_scale, "gravity": fit,
            "lines": [l.id for l in lines]}


# ---------------------------------------------------------------- loads and service
def segment_loads(res: dict) -> dict[tuple[str, str], float]:
    """Annual riders (both directions) on each station-to-station hop."""
    loads: dict[tuple[str, str], float] = {}
    for p in res["pairs"]:
        for u, v in zip(p["path"], p["path"][1:]):
            k = tuple(sorted((u, v)))
            loads[k] = loads.get(k, 0.0) + p["riders"]
    return loads


def trains_needed(loads: dict, P) -> float:
    """Trains per hour per direction the busiest hop needs in the peak hour."""
    if not loads:
        return 0.0
    peak = max(loads.values()) / 365.0 / 2.0 * P["demand.market.peak_hour_share"]
    seats = P["costs.vehicles.sections_per_train"] * P["system.vehicle.seats_per_section"]
    return peak / (seats * P["demand.market.design_load_factor"])


# ---------------------------------------------------------------- 4. benefits
def annual_benefits(res: dict, P) -> dict:
    """Benefits in the forecast year (MUSD): travellers' consumer surplus (the logit's logsum gain,
    valued at the choice model's value of time, so time, cost, comfort and fares all count), fare
    revenue (the operator's side of the fares the surplus nets out), car costs drivers don't weigh
    (USDOT resource cost less the perceived cost) and car externalities avoided."""
    bn, mc = "demand.benefits.", "demand.mode_choice."
    vmt = sum(p["car_vmt"] for p in res["pairs"])
    out = {
        "riders": sum(p["riders"] for p in res["pairs"]),
        "revenue_musd": sum(p["riders"] * p["fare"] for p in res["pairs"]) / 1e6,
        "hours_saved": sum(p["hours_saved"] for p in res["pairs"]),
        "car_vmt_avoided": vmt,
        "surplus_musd": sum(p["cs_minutes"] for p in res["pairs"]) * _vot(P) / 1e6,
        "car_cost_musd": vmt * max(P[bn + "car_operating_cost"] - P[mc + "car_perceived_cost"], 0.0) / 1e6,
        "external_musd": vmt * P[bn + "car_external_cost"] / 1e6,
    }
    out["total_musd"] = out["surplus_musd"] + out["revenue_musd"] + out["car_cost_musd"] + out["external_musd"]
    return out


def benefit_cost(benefits_musd: float, capital_musd: float, opex_musd: float, P, rate: float | None = None) -> dict:
    """Present values at the start of construction: capital spread evenly over the construction years,
    then 30 years of service whose benefits grow with the market, plus the residual value (linear
    depreciation over the service life). BCR = (benefits + residual) / (capital + O&M)."""
    bn = "demand.benefits."
    r = P[bn + "discount_rate"] if rate is None else rate
    build = int(round(P[bn + "construction_years"]))
    years = int(P[bn + "analysis_years"])
    g = P["demand.market.growth"]
    disc = lambda t: (1 + r) ** -t  # noqa: E731  (t in years from the start of construction, mid-year)
    pv_cap = sum(capital_musd / build * disc(t + 0.5) for t in range(build))
    pv_ben = sum(benefits_musd * (1 + g) ** k * disc(build + k + 0.5) for k in range(years))
    pv_om = sum(opex_musd * disc(build + k + 0.5) for k in range(years))
    residual = capital_musd * max(0.0, 1 - years / P[bn + "service_life"]) * disc(build + years)
    return {"rate": r, "pv_benefits": pv_ben, "pv_residual": residual, "pv_capital": pv_cap, "pv_om": pv_om,
            "bcr": (pv_ben + residual) / (pv_cap + pv_om)}


# ---------------------------------------------------------------- network summary for the report
SENSITIVITY = ("demand.mode_choice.maglev_premium", "demand.mode_choice.fare_per_mile",
               "demand.mode_choice.maglev_access", "demand.mode_choice.value_of_time",
               "demand.mode_choice.induced_share", "demand.market.growth", "demand.market.min_trip_share",
               "demand.market.min_pair_miles")


def network_demand(results: list[dict], params: dict, P0, market=None, sweep: bool = True) -> dict:
    """Ridership, revenue and benefit-cost for each build-out (lines through phase p), the transport
    line items only (capital mean and P50 of the lines; the fusion fleet is a separate investment,
    O&M at P50 with grid power), plus a low / high sweep of the main demand assumptions.
    market: (cities, markets, base) for another market than Minnesota's (the corridor screen); the
    rail constant and gravity model stay calibrated on Minnesota's."""
    from .network import load_cities

    mn_cities = load_cities()
    mn_markets, mn_base = load_market()
    cities, markets, base = market or (mn_cities, mn_markets, mn_base)
    calib = (mn_markets, mn_base, mn_cities)
    bn = "demand.benefits."
    out: dict = {"phases": {}, "sensitivity": []}

    def evaluate(P, ph):
        sub = [r for r in results if r["line"].phase <= ph]
        res = ridership([r["line"] for r in sub], cities, P, markets, base, calib)
        ab = annual_benefits(res, P)
        cap = sum(r["capS"]["total"] for r in sub)
        cap_mean, cap_p50 = float(np.mean(cap)), float(np.percentile(cap, 50))
        opex = sum(float(np.percentile(r["opsS"]["total"], 50)) for r in sub)
        return res, ab, cap_mean, cap_p50, opex

    phases = sorted({r["line"].phase for r in results})
    for ph in phases:
        res, ab, cap_mean, cap_p50, opex = evaluate(P0, ph)
        out["phases"][ph] = {
            "res": res, "benefits": ab, "capital_mean": cap_mean, "capital_p50": cap_p50, "opex": opex,
            "trains_needed": trains_needed(segment_loads(res), P0),
            "bcr": benefit_cost(ab["total_musd"], cap_mean, opex, P0),
            "bcr_p50": benefit_cost(ab["total_musd"], cap_p50, opex, P0),
            "bcr_alt": benefit_cost(ab["total_musd"], cap_mean, opex, P0, rate=P0[bn + "discount_rate_alt"]),
        }
    for name in SENSITIVITY if sweep else ():
        p = params[name]
        row = {"param": name, "low": p.low, "high": p.high, "value": p.value}
        for ph in (phases[0], phases[-1]):
            for side in ("low", "high"):
                P = dict(P0)
                P[name] = getattr(p, side)
                _, ab, cap_mean, _, opex = evaluate(P, ph)
                row[(ph, side)] = (ab["riders"], benefit_cost(ab["total_musd"], cap_mean, opex, P)["bcr"])
        out["sensitivity"].append(row)
    return out
