"""Spatial geometry utilities for collision detection.

Pure-math implementations with zero external dependencies.
Used by the Flink UDFs (inside Docker) and directly testable
on the host without PyFlink or Shapely.

Functions:
    bounding_box_contains — O(1) AABB pre-filter
    point_in_polygon      — O(n) ray-casting exact test
    haversine_distance    — Great-circle distance in km
    estimate_delay        — Deterministic delay heuristic

All coordinate inputs are (lat, lon) in decimal degrees (WGS-84).
"""

from __future__ import annotations

import math

# Earth mean radius in kilometers (WGS-84 approximation)
_EARTH_RADIUS_KM = 6371.0


def bounding_box_contains(
    polygon: list[tuple[float, float]],
    point: tuple[float, float],
) -> bool:
    """Fast AABB containment check — eliminates obvious non-collisions.

    Args:
        polygon: List of (lat, lon) tuples defining the polygon vertices.
        point: (lat, lon) of the point to test.

    Returns:
        True if the point falls within the polygon's axis-aligned bounding box.
    """
    if not polygon:
        return False

    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    return min_lat <= point[0] <= max_lat and min_lon <= point[1] <= max_lon


def point_in_polygon(
    polygon: list[tuple[float, float]],
    point: tuple[float, float],
) -> bool:
    """Ray-casting algorithm for point-in-polygon test.

    Casts a horizontal ray from the point and counts edge crossings.
    Odd crossings = inside, even = outside.

    Args:
        polygon: List of (lat, lon) tuples (minimum 3 vertices).
        point: (lat, lon) to test.

    Returns:
        True if the point is inside the polygon.
    """
    if len(polygon) < 3:
        return False

    px, py = point
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        # Check if the ray crosses this edge
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


def haversine_distance(
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Great-circle distance between two points in kilometers.

    Uses the Haversine formula. Accurate to ~0.5% for distances
    under 10,000 km (sufficient for logistics collision detection).

    Args:
        p1: (lat, lon) in decimal degrees.
        p2: (lat, lon) in decimal degrees.

    Returns:
        Distance in kilometers.
    """
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_KM * c


def polygon_centroid(polygon: list[tuple[float, float]]) -> tuple[float, float]:
    """Simple centroid (average of vertices).

    Not the geometric centroid of the polygon area, but sufficient
    for distance-based delay estimation.
    """
    if not polygon:
        return (0.0, 0.0)
    avg_lat = sum(p[0] for p in polygon) / len(polygon)
    avg_lon = sum(p[1] for p in polygon) / len(polygon)
    return (avg_lat, avg_lon)


def check_collision(
    ship_lat: float,
    ship_lon: float,
    polygon: list[tuple[float, float]],
) -> bool:
    """Two-stage collision check: bounding box → point-in-polygon.

    This is the function called by the Flink UDF. It performs the
    cheap AABB check first, then the exact ray-casting test only
    if the bounding box passes.

    Args:
        ship_lat: Shipment latitude.
        ship_lon: Shipment longitude.
        polygon: Threat impact zone vertices as (lat, lon) tuples.

    Returns:
        True if the shipment is inside the threat polygon.
    """
    point = (ship_lat, ship_lon)

    # Stage 1: cheap bounding-box filter
    if not bounding_box_contains(polygon, point):
        return False

    # Stage 2: exact ray-casting
    return point_in_polygon(polygon, point)


# Transport mode delay multipliers:
# SEA is slow to reroute, AIR is fast, ROAD is in between
_MODE_DELAY_MULTIPLIER: dict[str, float] = {
    "SEA": 1.5,
    "AIR": 0.5,
    "ROAD": 1.0,
}


def estimate_delay(
    severity: int,
    transport_mode: str,
    ship_lat: float | None = None,
    ship_lon: float | None = None,
    polygon: list[tuple[float, float]] | None = None,
) -> float:
    """Deterministic delay estimate in hours.

    Formula:
        base_delay = severity * 2.0 hours
        mode_factor = { SEA: 1.5, ROAD: 1.0, AIR: 0.5 }
        proximity_factor = 1.0 + (1.0 - normalized_distance) * 0.5
            (closer to threat center = more delay, max +50%)

    Args:
        severity: Threat severity (1–10).
        transport_mode: "SEA", "AIR", or "ROAD".
        ship_lat: Optional shipment latitude for proximity calculation.
        ship_lon: Optional shipment longitude for proximity calculation.
        polygon: Optional threat polygon for proximity calculation.

    Returns:
        Estimated delay in hours (always >= 0).
    """
    base_delay = severity * 2.0
    mode_factor = _MODE_DELAY_MULTIPLIER.get(transport_mode.upper(), 1.0)

    proximity_factor = 1.0
    if ship_lat is not None and ship_lon is not None and polygon:
        centroid = polygon_centroid(polygon)
        distance_km = haversine_distance((ship_lat, ship_lon), centroid)
        # Normalize: assume max relevant distance is 500km
        normalized = min(distance_km / 500.0, 1.0)
        proximity_factor = 1.0 + (1.0 - normalized) * 0.5

    return round(base_delay * mode_factor * proximity_factor, 2)
