"""Great-circle geometry."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def min_curve_radius_m(speed_kmh: float, superelevation_deg: float, unbalanced: float) -> float:
    """Smallest horizontal radius at a speed: v^2 / (g tan(cant) + unbalanced lateral accel)."""
    v = speed_kmh / 3.6
    return v * v / (9.80665 * math.tan(math.radians(superelevation_deg)) + unbalanced)
