"""Small geometry helpers shared across ingestion modules. Pure functions,
no network/DB — kept dependency-free (no shapely/pyproj) since the shapes
involved (single glacier outlines) are small enough that a simple
equirectangular approximation is accurate; not survey-grade, but honest
and documented, consistent with other approximations in this project
(see terrain_change_index in ingestion/satellite.py).
"""

import math

_KM_PER_DEGREE_LAT = 111.32


def polygon_area_km2(ring: list[tuple[float, float]]) -> float:
    """Approximate area of a (lon, lat) polygon ring in km².

    Projects degrees to km using a flat-earth approximation scaled by the
    ring's mean latitude, then applies the shoelace formula. Accurate for
    small polygons (a few km across, like individual glaciers); not
    appropriate for anything continent-scale.
    """
    if len(ring) < 3:
        return 0.0

    mean_lat = sum(lat for _, lat in ring) / len(ring)
    km_per_degree_lon = _KM_PER_DEGREE_LAT * math.cos(math.radians(mean_lat))

    xy = [(lon * km_per_degree_lon, lat * _KM_PER_DEGREE_LAT) for lon, lat in ring]
    area = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def multipolygon_area_km2(
    outer_rings: list[list[tuple[float, float]]], inner_rings: list[list[tuple[float, float]]]
) -> float:
    """Area of an OSM multipolygon relation: sum of outer-ring areas minus
    sum of inner-ring (hole) areas. Same approximation caveats as
    polygon_area_km2.
    """
    outer_area = sum(polygon_area_km2(r) for r in outer_rings)
    inner_area = sum(polygon_area_km2(r) for r in inner_rings)
    return max(outer_area - inner_area, 0.0)
