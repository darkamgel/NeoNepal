import datetime as dt

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .db import Base


class Watershed(Base):
    """A monitored river basin / valley (e.g. Langtang-Trishuli, Rasuwa)."""

    __tablename__ = "watersheds"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    district = Column(String, nullable=False)
    centroid_lat = Column(Float, nullable=False)
    centroid_lon = Column(Float, nullable=False)
    # Prototype stores boundary as GeoJSON text (SQLite has no native geometry type).
    # Production: migrate to PostGIS Geometry(Polygon) — see docs/DEPLOYMENT.md.
    boundary_geojson = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    lakes = relationship("GlacialLake", back_populates="watershed")
    sensor_readings = relationship("SensorReading", back_populates="watershed")
    risk_scores = relationship("RiskScore", back_populates="watershed")
    alerts = relationship("Alert", back_populates="watershed")


class GlacialLake(Base):
    """A glacial lake or ice mass tracked for area/instability change."""

    __tablename__ = "glacial_lakes"

    id = Column(Integer, primary_key=True)
    watershed_id = Column(Integer, ForeignKey("watersheds.id"), nullable=False)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    hazard_type = Column(String, default="glof")  # glof | ice_avalanche | debris_flow

    watershed = relationship("Watershed", back_populates="lakes")
    observations = relationship("SatelliteObservation", back_populates="lake")


class SatelliteObservation(Base):
    """One derived measurement from a satellite pass (lake area, terrain-change index).

    Attached to exactly one of `lake_id` (the 7 curated, actively-scored
    GlacialLakes) or `glacier_id` (an ad-hoc, on-demand analysis of any
    glacier in the full OSM inventory) — never both. Kept as one table
    rather than two so the ingestion/scoring math is written once and used
    identically in both paths.
    """

    __tablename__ = "satellite_observations"

    id = Column(Integer, primary_key=True)
    lake_id = Column(Integer, ForeignKey("glacial_lakes.id"), nullable=True)
    glacier_id = Column(Integer, ForeignKey("glaciers.id"), nullable=True)
    observed_at = Column(DateTime, nullable=False)
    surface_area_m2 = Column(Float, nullable=True)
    terrain_change_index = Column(Float, nullable=True)  # 0-1, higher = more instability
    source = Column(String, default="demo")  # demo | sentinel2
    source_scene_id = Column(String, nullable=True)  # real Sentinel-2 scene id, when source=sentinel2
    mean_nir_brightness = Column(Float, nullable=True)  # raw signal behind terrain_change_index, when source=sentinel2

    lake = relationship("GlacialLake", back_populates="observations")
    glacier = relationship("Glacier", back_populates="observations")


def satellite_observation_owner_filter(lake_id: int | None, glacier_id: int | None):
    """Query filter for 'the SatelliteObservation rows belonging to this
    lake, or this glacier' — exactly one of the two is ever passed. Shared
    by ingestion/satellite.py (writing observations) and risk/scoring.py
    (reading them back), which both need the same lake_id/glacier_id
    branching and previously duplicated it independently.
    """
    assert (lake_id is None) != (glacier_id is None), "exactly one of lake_id/glacier_id required"
    if lake_id is not None:
        return SatelliteObservation.lake_id == lake_id
    return SatelliteObservation.glacier_id == glacier_id


def satellite_observation_owner_kwargs(lake_id: int | None, glacier_id: int | None) -> dict:
    """The constructor kwargs matching satellite_observation_owner_filter,
    for creating a new row attached to the same owner.
    """
    assert (lake_id is None) != (glacier_id is None), "exactly one of lake_id/glacier_id required"
    return {"lake_id": lake_id} if lake_id is not None else {"glacier_id": glacier_id}


class Glacier(Base):
    """A glacier from OpenStreetMap's Nepal inventory — the full searchable
    set. Distinct from GlacialLake, which is the small, actively risk-scored
    subset with documented GLOF history.
    """

    __tablename__ = "glaciers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    osm_id = Column(Integer, nullable=False, unique=True)
    osm_type = Column(String, nullable=False)  # way | relation
    area_km2 = Column(Float, nullable=True)  # approximate, see import_glaciers.py / geo.py
    geometry_geojson = Column(Text, nullable=True)  # polygon outline, when computable
    wikipedia = Column(String, nullable=True)
    wikidata = Column(String, nullable=True)

    observations = relationship("SatelliteObservation", back_populates="glacier")


class SensorReading(Base):
    """A reading from a (real or simulated) ground sensor."""

    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    watershed_id = Column(Integer, ForeignKey("watersheds.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    water_level_m = Column(Float, nullable=True)
    seismic_activity = Column(Float, nullable=True)  # normalized 0-1
    source = Column(String, default="simulated")  # simulated | lorawan

    watershed = relationship("Watershed", back_populates="sensor_readings")


class RiskScore(Base):
    """Computed composite risk score for a watershed at a point in time."""

    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True)
    watershed_id = Column(Integer, ForeignKey("watersheds.id"), nullable=False)
    computed_at = Column(DateTime, nullable=False, default=dt.datetime.utcnow)
    score = Column(Float, nullable=False)  # 0-100
    level = Column(String, nullable=False)  # low | moderate | high | critical
    lake_growth_component = Column(Float, default=0.0)
    terrain_change_component = Column(Float, default=0.0)
    rainfall_component = Column(Float, default=0.0)
    sensor_component = Column(Float, default=0.0)

    watershed = relationship("Watershed", back_populates="risk_scores")


class Alert(Base):
    """A dispatched (or simulated) alert triggered by a risk threshold crossing."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    watershed_id = Column(Integer, ForeignKey("watersheds.id"), nullable=False)
    triggered_at = Column(DateTime, nullable=False, default=dt.datetime.utcnow)
    risk_score = Column(Float, nullable=False)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(String, default="log")  # log | sms | ivr | webhook

    watershed = relationship("Watershed", back_populates="alerts")
