"""One-time (idempotent) import of Nepal's glacier inventory from
OpenStreetMap via the Overpass API — real, freely queryable, no account
needed. Chosen over the official Randolph Glacier Inventory because RGI is
shapefile-only and may sit behind an Earthdata login; OSM returns plain
JSON for ~3,300 `natural=glacier` features tagged in Nepal.

Fetches full polygon geometry — for simple ways directly, and for
multipolygon relations (large glacier complexes mapped as outer/inner
member ways, e.g. Ngozumpa, Nepal's longest glacier) via their expanded
members — so a real, approximate area can be computed for effectively the
whole inventory, not just the simpler "way" features. See
docs/ARCHITECTURE.md for what the area approximation does and doesn't
cover.

Safe to re-run: upserts by osm_id, skips entirely if already populated.
"""

import json

import httpx
from sqlalchemy.orm import Session

from .db import SessionLocal
from .geo import multipolygon_area_km2, polygon_area_km2
from .models import Glacier

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass's usage policy asks for a descriptive User-Agent; some deployments
# reject the default httpx one outright (406 Not Acceptable). Note: `out
# geom;` (not `out tags geom;`) is required to get relation *member*
# geometry, not just the relation's own bounds.
_HEADERS = {"User-Agent": "NeoNepal-glacial-hazard-prototype/1.0"}
_QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="NP"][admin_level=2]->.nepal;
(
  way["natural"="glacier"](area.nepal);
  relation["natural"="glacier"](area.nepal);
);
out geom;
"""


def _ring(points: list[dict]) -> list[tuple[float, float]]:
    return [(pt["lon"], pt["lat"]) for pt in points]


def _build_way(el: dict) -> tuple[float, float, float | None, str | None]:
    ring = _ring(el["geometry"])
    lat = sum(p[1] for p in ring) / len(ring)
    lon = sum(p[0] for p in ring) / len(ring)
    area_km2 = round(polygon_area_km2(ring), 4)
    geometry_geojson = json.dumps({"type": "Polygon", "coordinates": [[[p[0], p[1]] for p in ring]]})
    return lat, lon, area_km2, geometry_geojson


def _build_relation(el: dict) -> tuple[float, float, float | None, str | None]:
    outer_rings, inner_rings = [], []
    for member in el.get("members", []):
        geom = member.get("geometry")
        if not geom or len(geom) < 3:
            continue
        ring = _ring(geom)
        (outer_rings if member.get("role") == "outer" else inner_rings).append(ring)

    bounds = el["bounds"]
    lat = (bounds["minlat"] + bounds["maxlat"]) / 2
    lon = (bounds["minlon"] + bounds["maxlon"]) / 2

    if not outer_rings:
        return lat, lon, None, None

    area_km2 = round(multipolygon_area_km2(outer_rings, inner_rings), 4)
    if len(outer_rings) == 1:
        coords = [[[p[0], p[1]] for p in outer_rings[0]]] + [
            [[p[0], p[1]] for p in r] for r in inner_rings
        ]
        geometry_geojson = json.dumps({"type": "Polygon", "coordinates": coords})
    else:
        # Multi-part glacier complex: render each outer part; holes omitted
        # in this rarer branch for simplicity (area total still accounts
        # for them via multipolygon_area_km2 above).
        geometry_geojson = json.dumps(
            {
                "type": "MultiPolygon",
                "coordinates": [[[[p[0], p[1]] for p in r]] for r in outer_rings],
            }
        )
    return lat, lon, area_km2, geometry_geojson


def _build_glacier(el: dict) -> Glacier | None:
    tags = el.get("tags", {})

    if el["type"] == "way" and el.get("geometry"):
        lat, lon, area_km2, geometry_geojson = _build_way(el)
    elif el["type"] == "relation":
        lat, lon, area_km2, geometry_geojson = _build_relation(el)
    else:
        return None

    return Glacier(
        name=tags.get("name"),
        lat=lat,
        lon=lon,
        osm_id=el["id"],
        osm_type=el["type"],
        area_km2=area_km2,
        geometry_geojson=geometry_geojson,
        wikipedia=tags.get("wikipedia"),
        wikidata=tags.get("wikidata"),
    )


def import_glaciers(db: Session) -> int:
    if db.query(Glacier).count() > 0:
        print("Glaciers already imported, skipping.")
        return 0

    resp = httpx.post(_OVERPASS_URL, data={"data": _QUERY}, headers=_HEADERS, timeout=180.0)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])

    count = 0
    for el in elements:
        glacier = _build_glacier(el)
        if glacier is None:
            continue
        db.add(glacier)
        count += 1
    db.commit()
    print(f"Imported {count} glaciers from OpenStreetMap.")
    return count


if __name__ == "__main__":
    db = SessionLocal()
    try:
        import_glaciers(db)
    finally:
        db.close()
