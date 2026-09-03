import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_alerts, routes_cycle, routes_glaciers, routes_watersheds
from app.db import Base, get_db
from app.ingestion import satellite as satellite_ingestion


@pytest.fixture(autouse=True)
def force_demo_satellite_mode(monkeypatch):
    """Tests must never depend on network access to Planetary Computer."""
    monkeypatch.setattr(satellite_ingestion, "SATELLITE_MODE", "demo")


@pytest.fixture
def client(monkeypatch):
    """A TestClient over the real routers, wired to an isolated in-memory
    DB, deliberately NOT going through main.py's production `lifespan`
    (which seeds real historical data and imports ~3,300 real glaciers via
    live network calls on startup — exactly what a test suite must not
    depend on). Route wiring, dependency injection, and response schemas
    are still exercised end-to-end against the actual router objects the
    app serves.
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    test_app = FastAPI()
    test_app.include_router(routes_watersheds.router)
    test_app.include_router(routes_alerts.router)
    test_app.include_router(routes_cycle.router)
    test_app.include_router(routes_glaciers.router)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    # The rate limiters are module-level singletons shared by every test
    # that imports these routers (same underlying route function object),
    # so without this, tests would interfere with each other's call counts
    # depending on run order. Disable them here; test_rate_limiting.py
    # verifies the real limiting behavior against its own isolated app.
    test_app.dependency_overrides[routes_cycle._rate_limiter] = lambda: None
    test_app.dependency_overrides[routes_glaciers._analyze_rate_limiter] = lambda: None

    # No real network for rainfall during route-level tests either.
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.1)

    http_client = TestClient(test_app)
    http_client.app_module = test_app  # convenience handle for dependency_overrides in tests
    http_client.SessionLocal = TestSessionLocal  # convenience handle for seeding test data
    return http_client
