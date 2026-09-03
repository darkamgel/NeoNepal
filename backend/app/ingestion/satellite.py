"""Satellite-derived glacial hazard indicators.

Works against either a curated `GlacialLake` (via `lake_id`, used by the
scheduled 5-minute recompute for the 7 actively risk-scored watersheds) or
an arbitrary `Glacier` from the full OSM inventory (via `glacier_id`, used
for on-demand analysis triggered from the Glacier Directory). Exactly one
of the two is passed per call — the underlying satellite math (NDWI,
scene dedup, terrain-change proxy) is identical either way, only which
foreign key gets set on the resulting row differs.

Live mode (default): pulls real Sentinel-2 L2A imagery from Microsoft's
Planetary Computer — STAC search, anonymous SAS-token signing, and windowed
COG reads are all available with zero credentials at prototype scale. Only
creates a new observation when a genuinely newer scene is available; a
5-minute scheduler tick otherwise reuses the last real observation, since
Sentinel-2 revisits any given point roughly every 5 days (less in monsoon
cloud cover) — this is honest behavior, not a bug.

Demo mode (SATELLITE_MODE=demo, and always in tests): extends the existing
observation history with a small random-walk step instead, so
development/CI never depends on network access.

See docs/DEPLOYMENT.md for the terrain-change proxy's limitations and what
a production-grade instability signal (SAR/InSAR) would add.
"""

import datetime as dt
import logging
import os
import random

import httpx
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from sqlalchemy.orm import Session

from ..models import (
    SatelliteObservation,
    satellite_observation_owner_filter as _owner_filter,
    satellite_observation_owner_kwargs as _owner_kwargs,
)

logger = logging.getLogger("neonepal.ingestion.satellite")

SATELLITE_MODE = os.getenv("SATELLITE_MODE", "live")

_STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
_SAS_TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"
_COLLECTION = "sentinel-2-l2a"
_SEARCH_LOOKBACK_DAYS = 30
_BBOX_BUFFER_DEG = 0.02  # ~2km
_WATER_NDWI_THRESHOLD = 0.1


def _demo_next_observation(
    db: Session, lat: float, lon: float, *, lake_id: int | None = None, glacier_id: int | None = None
) -> SatelliteObservation:
    last = (
        db.query(SatelliteObservation)
        .filter(_owner_filter(lake_id, glacier_id))
        .order_by(SatelliteObservation.observed_at.desc())
        .first()
    )
    base_area = last.surface_area_m2 if last else 100_000.0
    base_terrain = last.terrain_change_index if last else 0.05

    area = max(0.0, base_area * (1 + random.uniform(-0.01, 0.02)))
    terrain = min(1.0, max(0.0, base_terrain + random.uniform(-0.005, 0.02)))

    return SatelliteObservation(
        **_owner_kwargs(lake_id, glacier_id),
        observed_at=dt.datetime.utcnow(),
        surface_area_m2=round(area, 1),
        terrain_change_index=round(terrain, 4),
        source="demo",
    )


def _find_latest_scene(lat: float, lon: float) -> dict | None:
    now = dt.datetime.utcnow()
    start = now - dt.timedelta(days=_SEARCH_LOOKBACK_DAYS)
    bbox = [lon - _BBOX_BUFFER_DEG, lat - _BBOX_BUFFER_DEG, lon + _BBOX_BUFFER_DEG, lat + _BBOX_BUFFER_DEG]
    resp = httpx.post(
        _STAC_SEARCH_URL,
        json={
            "collections": [_COLLECTION],
            "bbox": bbox,
            "datetime": f"{start.isoformat()}Z/{now.isoformat()}Z",
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
            "limit": 1,
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    return features[0] if features else None


def _ndwi_water_fraction(green, nir) -> float:
    """Fraction of pixels classified as water by NDWI. Pure function of the
    two band arrays — independently testable without network/rasterio.
    """
    ndwi = (green - nir) / (green + nir + 1e-6)
    return float((ndwi > _WATER_NDWI_THRESHOLD).mean())


def _terrain_change_from_brightness(mean_nir: float, prev_mean_nir: float | None) -> float:
    """Coarse first-approximation instability proxy: normalized brightness
    shift vs. the previous real observation. Not a substitute for
    SAR/InSAR-based terrain-change detection — see docs/DEPLOYMENT.md.
    """
    if not prev_mean_nir:
        return 0.05
    return min(abs(mean_nir - prev_mean_nir) / (prev_mean_nir + 1e-6), 1.0)


def _read_ndwi_and_brightness(scene: dict, lat: float, lon: float) -> tuple[float, float]:
    green_href = scene["assets"]["B03"]["href"]
    nir_href = scene["assets"]["B08"]["href"]
    token = httpx.get(_SAS_TOKEN_URL, timeout=20.0).json()["token"]

    bounds_4326 = (
        lon - _BBOX_BUFFER_DEG,
        lat - _BBOX_BUFFER_DEG,
        lon + _BBOX_BUFFER_DEG,
        lat + _BBOX_BUFFER_DEG,
    )
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(f"/vsicurl/{green_href}?{token}") as g, rasterio.open(
            f"/vsicurl/{nir_href}?{token}"
        ) as n:
            left, bottom, right, top = transform_bounds("EPSG:4326", g.crs, *bounds_4326)
            win = from_bounds(left, bottom, right, top, g.transform)
            green = g.read(1, window=win).astype(float)
            nir = n.read(1, window=win).astype(float)
            pixel_area_m2 = abs(g.transform.a * g.transform.e)

    water_fraction = _ndwi_water_fraction(green, nir)
    surface_area_m2 = water_fraction * green.size * pixel_area_m2
    mean_nir_brightness = float(nir.mean())
    return surface_area_m2, mean_nir_brightness


def _live_next_observation(
    db: Session, lat: float, lon: float, *, lake_id: int | None = None, glacier_id: int | None = None
) -> SatelliteObservation:
    # Compare against the last *real* observation specifically, by insertion
    # order — not the latest by observed_at. In this demo, synthetic backfill
    # rows can carry later calendar dates than a real scene's actual
    # acquisition date, which would otherwise break scene-id deduplication.
    last_real = (
        db.query(SatelliteObservation)
        .filter(_owner_filter(lake_id, glacier_id), SatelliteObservation.source == "sentinel2")
        .order_by(SatelliteObservation.id.desc())
        .first()
    )

    scene = _find_latest_scene(lat, lon)
    if not scene:
        raise RuntimeError(f"No recent Sentinel-2 scene found near ({lat}, {lon})")

    if last_real and last_real.source_scene_id == scene["id"]:
        return last_real  # no newer imagery available yet — reuse, don't duplicate

    surface_area_m2, mean_nir = _read_ndwi_and_brightness(scene, lat, lon)

    prev_mean_nir = last_real.mean_nir_brightness if last_real else None
    terrain_change = _terrain_change_from_brightness(mean_nir, prev_mean_nir)

    return SatelliteObservation(
        **_owner_kwargs(lake_id, glacier_id),
        observed_at=dt.datetime.fromisoformat(scene["properties"]["datetime"].replace("Z", "+00:00")).replace(tzinfo=None),
        surface_area_m2=round(surface_area_m2, 1),
        terrain_change_index=round(terrain_change, 4),
        source="sentinel2",
        source_scene_id=scene["id"],
        mean_nir_brightness=round(mean_nir, 2),
    )


def ingest_latest(
    db: Session, lat: float, lon: float, *, lake_id: int | None = None, glacier_id: int | None = None
) -> SatelliteObservation:
    if SATELLITE_MODE == "live":
        try:
            obs = _live_next_observation(db, lat, lon, lake_id=lake_id, glacier_id=glacier_id)
        except Exception as e:  # network error, no scene, read failure, etc.
            logger.warning(
                "Live satellite ingestion failed for (lake_id=%s, glacier_id=%s) (%s); using demo fallback",
                lake_id,
                glacier_id,
                e,
            )
            obs = _demo_next_observation(db, lat, lon, lake_id=lake_id, glacier_id=glacier_id)
    else:
        obs = _demo_next_observation(db, lat, lon, lake_id=lake_id, glacier_id=glacier_id)

    if obs.id is None:  # only persist genuinely new observations
        db.add(obs)
        db.commit()
        db.refresh(obs)
    return obs


def get_latest_observation(db: Session, lake_id: int) -> SatelliteObservation | None:
    return (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.lake_id == lake_id)
        .order_by(SatelliteObservation.observed_at.desc())
        .first()
    )
