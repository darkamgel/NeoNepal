"""Verifies the rate limiters are actually wired onto the routes end-to-end
— deliberately does NOT use the shared `client` fixture, since that
fixture disables rate limiting (to avoid cross-test interference from the
module-level limiter singletons; see conftest.py). This builds its own
isolated app per test with fresh RateLimiter instances instead, so it's
independent of both the shared fixture and any other test's call count.
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.rate_limit import RateLimiter


def _make_isolated_client(monkeypatch, max_calls: int):
    """Builds a fresh app with the real routers, substituting a fresh,
    low-limit RateLimiter in for both rate-limited routes via FastAPI's
    `dependency_overrides` — NOT by monkeypatching the routes_*
    `_rate_limiter` module attribute, which wouldn't work: `Depends(...)`
    captures that object reference at route-decoration time (import time),
    so reassigning the module attribute afterwards doesn't change what the
    already-registered route depends on.
    """
    from app.api import routes_cycle, routes_glaciers, routes_watersheds

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    fresh_limiter = RateLimiter(max_calls=max_calls, window_seconds=60)

    test_app = FastAPI()
    test_app.include_router(routes_watersheds.router)
    test_app.include_router(routes_cycle.router)
    test_app.include_router(routes_glaciers.router)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[routes_cycle._rate_limiter] = fresh_limiter
    test_app.dependency_overrides[routes_glaciers._analyze_rate_limiter] = fresh_limiter
    monkeypatch.setattr("app.risk.scoring.weather_ingestion.fetch_rainfall_anomaly", lambda *a, **k: 0.1)

    client = TestClient(test_app)
    client.SessionLocal = TestSessionLocal
    return client


def test_cycle_run_is_rate_limited(monkeypatch):
    client = _make_isolated_client(monkeypatch, max_calls=2)

    assert client.post("/cycle/run").status_code == 200
    assert client.post("/cycle/run").status_code == 200
    third = client.post("/cycle/run")
    assert third.status_code == 429
    assert "Rate limit exceeded" in third.json()["detail"]


def test_analyze_glacier_is_rate_limited(monkeypatch):
    from app.models import Glacier

    client = _make_isolated_client(monkeypatch, max_calls=1)
    db = client.SessionLocal()
    glacier = Glacier(name="Test", lat=28.0, lon=85.5, osm_id=1, osm_type="way")
    db.add(glacier)
    db.commit()
    glacier_id = glacier.id
    db.close()

    assert client.post(f"/glaciers/{glacier_id}/analyze").status_code == 200
    second = client.post(f"/glaciers/{glacier_id}/analyze")
    assert second.status_code == 429
