"""Transparent, explainable risk scoring — deliberately not a black-box ML
model. For a government/NGO pitch, a reviewer needs to see exactly why a
watershed is flagged; each component below is independently inspectable.

score = 100 * (0.30*terrain_change + 0.25*lake_growth + 0.20*rainfall + 0.25*sensor)

When no ground sensor data exists (on-demand analysis of an arbitrary
glacier, see compute_adhoc_risk below), the sensor term is dropped rather
than silently treated as a confirmed 0 — the remaining three weights are
rescaled proportionally so they still sum to 1. Missing data is not the
same claim as "sensors confirm low risk," and the score/UI must not blur
that distinction.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..ingestion import weather as weather_ingestion
from ..models import Glacier, SatelliteObservation, SensorReading, Watershed

WEIGHTS = {
    "terrain_change": 0.30,
    "lake_growth": 0.25,
    "rainfall": 0.20,
    "sensor": 0.25,
}
_NO_SENSOR_WEIGHTS = {
    k: v / (1 - WEIGHTS["sensor"]) for k, v in WEIGHTS.items() if k != "sensor"
}

# Growth rate (fractional area change over the lookback window) that maps to
# a lake_growth_component of 1.0. Documented assumption, tunable per lake type.
_GROWTH_SATURATION = 0.10
_LOOKBACK_OBSERVATIONS = 5
_BASELINE_WATER_LEVEL_M = 1.2
_WATER_LEVEL_SATURATION_M = 0.6


@dataclass
class RiskComponents:
    terrain_change: float
    lake_growth: float
    rainfall: float
    sensor: float
    sensor_available: bool = True

    @property
    def score(self) -> float:
        if self.sensor_available:
            raw = (
                WEIGHTS["terrain_change"] * self.terrain_change
                + WEIGHTS["lake_growth"] * self.lake_growth
                + WEIGHTS["rainfall"] * self.rainfall
                + WEIGHTS["sensor"] * self.sensor
            )
        else:
            raw = (
                _NO_SENSOR_WEIGHTS["terrain_change"] * self.terrain_change
                + _NO_SENSOR_WEIGHTS["lake_growth"] * self.lake_growth
                + _NO_SENSOR_WEIGHTS["rainfall"] * self.rainfall
            )
        return round(min(max(raw, 0.0), 1.0) * 100, 2)

    @property
    def level(self) -> str:
        s = self.score
        if s >= 75:
            return "critical"
        if s >= 50:
            return "high"
        if s >= 25:
            return "moderate"
        return "low"


def _lake_growth_component(
    db: Session, asof: dt.datetime, *, lake_id: int | None = None, glacier_id: int | None = None
) -> float:
    filt = (
        SatelliteObservation.lake_id == lake_id
        if lake_id is not None
        else SatelliteObservation.glacier_id == glacier_id
    )
    obs = (
        db.query(SatelliteObservation)
        .filter(filt, SatelliteObservation.observed_at <= asof)
        .order_by(SatelliteObservation.observed_at.desc())
        .limit(_LOOKBACK_OBSERVATIONS)
        .all()
    )
    if len(obs) < 2:
        return 0.0
    oldest, newest = obs[-1], obs[0]
    if not oldest.surface_area_m2:
        return 0.0
    growth = (newest.surface_area_m2 - oldest.surface_area_m2) / oldest.surface_area_m2
    return round(min(max(growth / _GROWTH_SATURATION, 0.0), 1.0), 4)


def _terrain_change_component(
    db: Session, asof: dt.datetime, *, lake_id: int | None = None, glacier_id: int | None = None
) -> float:
    filt = (
        SatelliteObservation.lake_id == lake_id
        if lake_id is not None
        else SatelliteObservation.glacier_id == glacier_id
    )
    latest = (
        db.query(SatelliteObservation)
        .filter(filt, SatelliteObservation.observed_at <= asof)
        .order_by(SatelliteObservation.observed_at.desc())
        .first()
    )
    return round(latest.terrain_change_index, 4) if latest and latest.terrain_change_index else 0.0


def _sensor_component(db: Session, watershed_id: int, asof: dt.datetime) -> float:
    latest = (
        db.query(SensorReading)
        .filter(SensorReading.watershed_id == watershed_id, SensorReading.recorded_at <= asof)
        .order_by(SensorReading.recorded_at.desc())
        .first()
    )
    if not latest:
        return 0.0
    seismic = latest.seismic_activity or 0.0
    water_dev = max(0.0, (latest.water_level_m or _BASELINE_WATER_LEVEL_M) - _BASELINE_WATER_LEVEL_M)
    water_component = min(water_dev / _WATER_LEVEL_SATURATION_M, 1.0)
    return round(0.4 * seismic + 0.6 * water_component, 4)


def compute_risk(
    db: Session, watershed: Watershed, asof: dt.datetime | None = None
) -> RiskComponents:
    """Aggregates across all lakes in the watershed by taking the max
    lake-derived component (a watershed is as risky as its most dangerous
    lake), combined with watershed-level rainfall and sensor readings.

    `asof` restricts every underlying query to data recorded at or before
    that timestamp, which is what lets the same scoring logic be used both
    live (asof=None -> now) and for historical backfill/backtesting.
    """
    asof = asof or dt.datetime.utcnow()

    terrain = 0.0
    growth = 0.0
    for lake in watershed.lakes:
        terrain = max(terrain, _terrain_change_component(db, asof, lake_id=lake.id))
        growth = max(growth, _lake_growth_component(db, asof, lake_id=lake.id))

    rainfall = weather_ingestion.fetch_rainfall_anomaly(
        watershed.centroid_lat, watershed.centroid_lon, asof=asof
    )
    sensor = _sensor_component(db, watershed.id, asof)

    return RiskComponents(
        terrain_change=terrain, lake_growth=growth, rainfall=rainfall, sensor=sensor
    )


def compute_adhoc_risk(db: Session, glacier: Glacier) -> RiskComponents:
    """On-demand risk score for any glacier in the full OSM inventory, not
    just the 7 curated watersheds. No ground sensor exists at an arbitrary
    location, so `sensor_available=False` and the score formula renormalizes
    across the remaining 3 components rather than treating "no sensor" as
    "sensor confirms 0 risk." terrain_change/lake_growth start at their
    honest "no signal yet" defaults on a glacier's first-ever analysis and
    become real comparisons on repeat calls, since each call persists its
    observation (see ingestion/satellite.py).
    """
    asof = dt.datetime.utcnow()
    terrain = _terrain_change_component(db, asof, glacier_id=glacier.id)
    growth = _lake_growth_component(db, asof, glacier_id=glacier.id)
    rainfall = weather_ingestion.fetch_rainfall_anomaly(glacier.lat, glacier.lon, asof=asof)

    return RiskComponents(
        terrain_change=terrain,
        lake_growth=growth,
        rainfall=rainfall,
        sensor=0.0,
        sensor_available=False,
    )
