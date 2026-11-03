"""Stagger departures to cut the network's power peak (and the fusion fleet).

Every line runs every headway in both directions. Each direction gets an offset in whole minutes
within one headway. Phase by phase (earlier lines keep their timetable when new ones open), a
coordinate search with random restarts picks the offsets that minimise the network's 1-second
power peak, the number the fusion fleet is sized to. The day repeats, so shifting a direction's
departures by k minutes is a roll of its day profile.
"""

from __future__ import annotations

import numpy as np
import yaml

from .kinematics import leg_power_cells
from .network import TIMETABLE_PATH, Line
from .power import _reverse, direction_day_profile

HUB = "midway_hub"


def _peak(x: np.ndarray) -> float:
    return float(x.max()) / 1e6


def hub_events(line: Line, P, reverse: bool, hub: str = HUB):
    """Minutes after departure that a direction arrives at / leaves the hub (None if it doesn't)."""
    segs = _reverse(line.segments) if reverse else line.segments
    if segs[0].a.id == hub:
        return None, 0.0
    t, current = 0.0, []
    for s in segs:
        current.append(s)
        if s.b.is_station:
            dt, _, _ = leg_power_cells(current, P, "winter")
            t += float(dt.sum())
            current = []
            if s.b.id == hub:
                last = s is segs[-1]
                return t / 60.0, None if last else (t + P["system.vehicle.dwell"]) / 60.0
            t += P["system.vehicle.dwell"]
    return None, None


def _connects(event: float, others: list[float], after: bool, lo: float, hi: float, h: float) -> bool:
    """after=True: event (a departure) is lo..hi min after one of others (arrivals); else before."""
    gaps = [((event - o) if after else (o - event)) % h for o in others]
    return any(lo <= g <= hi for g in gaps)


def optimise(lines: list[Line], P, season: str = "winter", restarts: int = 6, seed: int = 1,
             transfers: bool = True) -> dict:
    """Offsets {line_id: (fwd_min, rev_min)} and peaks before/after, per phase.

    transfers=True: a direction that starts at or passes through the Midway hub must leave it
    min_transfer..max_transfer_wait minutes after an arrival of a line already running, and must
    arrive that long before one of their departures (connections both ways)."""
    headway_min = int(round(60 / P["system.service.trains_per_hour"]))
    prof = {(l.id, rev): direction_day_profile(l, P, season, rev, 0.0) for l in lines for rev in (False, True)}
    roll = lambda key, k: np.roll(prof[key], 60 * k)  # noqa: E731
    rng = np.random.default_rng(seed)
    offsets: dict[str, list[int]] = {}
    report = []
    base = np.zeros_like(next(iter(prof.values())))
    base_aligned = base.copy()
    lo, hi = P["system.service.min_transfer"], P["system.service.max_transfer_wait"]
    events = {(l.id, rev): hub_events(l, P, rev) for l in lines for rev in (False, True)}
    fixed_arr, fixed_dep = [], []  # hub events of lines already running (minutes mod headway)
    unmet = []
    for ph in sorted({l.phase for l in lines}):
        new = [l for l in lines if l.phase == ph]
        keys = [(l.id, rev) for l in new for rev in (False, True)]
        options = {}
        for k in keys:
            arr, dep = events[k]
            ok = []
            for m in range(headway_min):
                good = True
                if transfers and dep is not None and fixed_arr:
                    good &= _connects((m + dep) % headway_min, fixed_arr, True, lo, hi, headway_min)
                if transfers and arr is not None and fixed_dep:
                    good &= _connects((m + arr) % headway_min, fixed_dep, False, lo, hi, headway_min)
                if good:
                    ok.append(m)
            if not ok:
                unmet.append(k)
                ok = list(range(headway_min))
            options[k] = ok
        aligned = base_aligned + sum(prof[k] for k in keys)
        best_vals, best_peak = None, np.inf
        for r in range(restarts):
            vals = {k: options[k][0] if r == 0 else int(rng.choice(options[k])) for k in keys}
            total = base + sum(roll(k, vals[k]) for k in keys)
            improved = True
            while improved:
                improved = False
                for k in keys:
                    partial = total - roll(k, vals[k])
                    peaks = [_peak(partial + roll(k, m)) for m in options[k]]
                    m = options[k][int(np.argmin(peaks))]
                    if min(peaks) < _peak(partial + roll(k, vals[k])) - 1e-9:
                        vals[k] = m
                        improved = True
                    total = partial + roll(k, vals[k])
            if _peak(total) < best_peak:
                best_peak, best_vals = _peak(total), dict(vals)
        for l in new:
            offsets[l.id] = [best_vals[(l.id, False)], best_vals[(l.id, True)]]
        for k in keys:
            arr, dep = events[k]
            if arr is not None:
                fixed_arr.append((best_vals[k] + arr) % headway_min)
            if dep is not None:
                fixed_dep.append((best_vals[k] + dep) % headway_min)
        base = base + sum(roll(k, best_vals[k]) for k in keys)
        base_aligned = aligned
        report.append({"phase": ph, "peak_aligned_mw": _peak(aligned), "peak_staggered_mw": best_peak})
    return {"offsets": offsets, "phases": report, "headway_min": headway_min, "transfers": transfers,
            "unmet_transfers": [f"{lid} {'reverse' if rev else 'forward'}" for lid, rev in unmet]}


def hub_times(line: Line, P, hub: str = HUB) -> dict:
    """Minutes past the hour the line's trains reach the hub, per direction (None if it doesn't)."""
    out = {}
    headway = 60.0 / P["system.service.trains_per_hour"]
    for rev, offset in ((False, line.offset_fwd_min), (True, line.offset_rev_min)):
        segs = _reverse(line.segments) if rev else line.segments
        t, current, found = 0.0, [], None
        for s in segs:
            current.append(s)
            if s.b.is_station:
                dt, _, _ = leg_power_cells(current, P, "winter")
                t += float(dt.sum())
                current = []
                if s.b.id == hub:
                    found = t
                    break
                t += P["system.vehicle.dwell"]
        if found is None and segs[0].a.id == hub:
            found = 0.0
        out["reverse" if rev else "forward"] = (
            None if found is None else sorted({round((offset + found / 60.0 + k * headway) % 60) for k in range(2)}))
    return out


def write_timetable(result: dict, path=TIMETABLE_PATH) -> None:
    doc = {
        "offsets": {k: {"forward": v[0], "reverse": v[1]} for k, v in result["offsets"].items()},
        "peaks_mw": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in p.items()} for p in result["phases"]],
    }
    header = (
        "# Departure offsets per line, minutes after 06:00 (then every headway), forward = from the\n"
        "# line's first point, reverse = from its last. Written by `mnmaglev timetable --write`, which\n"
        "# picks them to minimise the network's 1-second power peak, phase by phase. The power model\n"
        "# and the fusion sizing read this file; delete it to go back to aligned departures.\n"
    )
    path.write_text(header + yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

