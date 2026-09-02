import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import GlacialLake, Glacier, SatelliteObservation, SensorReading, Watershed
from app.risk.scoring import RiskComponents, compute_adhoc_risk, compute_risk


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_watershed(db):
    w = Watershed(name="Test", district="Test", centroid_lat=28.0, centroid_lon=85.5)
    db.add(w)
    db.flush()
    lake = GlacialLake(watershed_id=w.id, name="Test Lake", lat=28.0, lon=85.5, hazard_type="glof")
    db.add(lake)
    db.flush()
    db.commit()
    db.refresh(w)
    return w, lake


def test_low_risk_when_no_signal(db, monkeypatch):
    w, lake = _make_watershed(db)
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.0)

    components = compute_risk(db, w)
    assert components.score < 25
    assert components.level == "low"


def test_high_risk_with_rapid_lake_growth_and_terrain_change(db, monkeypatch):
    w, lake = _make_watershed(db)
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.9)

    now = dt.datetime.utcnow()
    db.add(
        SatelliteObservation(
            lake_id=lake.id,
            observed_at=now - dt.timedelta(days=10),
            surface_area_m2=100_000,
            terrain_change_index=0.1,
            source="demo",
        )
    )
    db.add(
        SatelliteObservation(
            lake_id=lake.id,
            observed_at=now,
            surface_area_m2=120_000,  # 20% growth, above saturation
            terrain_change_index=0.9,
            source="demo",
        )
    )
    db.add(
        SensorReading(
            watershed_id=w.id,
            recorded_at=now,
            water_level_m=2.0,
            seismic_activity=0.8,
            source="simulated",
        )
    )
    db.commit()

    components = compute_risk(db, w)
    assert components.score >= 75
    assert components.level == "critical"


def test_risk_components_score_and_level_boundaries():
    assert RiskComponents(0, 0, 0, 0).level == "low"
    assert RiskComponents(1, 1, 1, 1).score == 100.0
    assert RiskComponents(1, 1, 1, 1).level == "critical"


def test_missing_sensor_renormalizes_instead_of_counting_as_zero():
    # Same terrain/growth/rainfall, but one has real sensor data confirming
    # 0 risk and the other simply has no sensor at all. These must not score
    # the same — missing data isn't the same claim as "confirmed low risk."
    with_zero_sensor = RiskComponents(1, 1, 1, 0, sensor_available=True)
    without_sensor = RiskComponents(1, 1, 1, 0, sensor_available=False)

    assert with_zero_sensor.score == 75.0  # 0.30+0.25+0.20, sensor term genuinely 0
    assert without_sensor.score == 100.0  # renormalized across the 3 available components
    assert without_sensor.score > with_zero_sensor.score


def _make_glacier(db):
    g = Glacier(name="Test Glacier", lat=28.0, lon=85.5, osm_id=1, osm_type="way")
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def test_compute_adhoc_risk_has_no_sensor_and_uses_real_rainfall(db, monkeypatch):
    glacier = _make_glacier(db)
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.42)

    components = compute_adhoc_risk(db, glacier)

    assert components.sensor_available is False
    assert components.sensor == 0.0
    assert components.rainfall == 0.42
    # No observations exist yet for this glacier — honest "no signal" defaults.
    assert components.terrain_change == 0.0
    assert components.lake_growth == 0.0


def test_compute_adhoc_risk_reflects_persisted_observations(db, monkeypatch):
    glacier = _make_glacier(db)
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.0)

    now = dt.datetime.utcnow()
    db.add(
        SatelliteObservation(
            glacier_id=glacier.id,
            observed_at=now - dt.timedelta(days=5),
            surface_area_m2=50_000,
            terrain_change_index=0.1,
            source="demo",
        )
    )
    db.add(
        SatelliteObservation(
            glacier_id=glacier.id,
            observed_at=now,
            surface_area_m2=60_000,  # 20% growth, above saturation
            terrain_change_index=0.8,
            source="demo",
        )
    )
    db.commit()

    components = compute_adhoc_risk(db, glacier)
    assert components.terrain_change == 0.8
    assert components.lake_growth == 1.0  # saturated
