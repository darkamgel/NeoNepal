"""Route-level integration tests: real FastAPI dependency injection,
request/response schema validation, and 404 handling — the wiring bugs
that pure-function unit tests (test_scoring.py, test_geo.py, etc.) can't
catch. See tests/conftest.py for why these run against a small standalone
app rather than the production app + lifespan.
"""

from app.models import GlacialLake, Glacier, Watershed


def _seed_watershed(client) -> int:
    db = client.SessionLocal()
    try:
        w = Watershed(name="Test Watershed", district="Test", centroid_lat=28.0, centroid_lon=85.5)
        db.add(w)
        db.flush()
        db.add(GlacialLake(watershed_id=w.id, name="Test Lake", lat=28.0, lon=85.5, hazard_type="glof"))
        db.commit()
        return w.id
    finally:
        db.close()


def _seed_glacier(client, **overrides) -> int:
    db = client.SessionLocal()
    try:
        defaults = dict(name="Test Glacier", lat=28.0, lon=85.5, osm_id=1, osm_type="way")
        g = Glacier(**{**defaults, **overrides})
        db.add(g)
        db.commit()
        return g.id
    finally:
        db.close()


class TestWatershedRoutes:
    def test_list_empty(self, client):
        resp = client.get("/watersheds")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_and_get_seeded_watershed(self, client):
        watershed_id = _seed_watershed(client)

        list_resp = client.get("/watersheds")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["latest_risk"] is None

        get_resp = client.get(f"/watersheds/{watershed_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Test Watershed"
        assert len(get_resp.json()["lakes"]) == 1

    def test_get_missing_watershed_is_404(self, client):
        resp = client.get("/watersheds/999")
        assert resp.status_code == 404

    def test_post_sensor_reading(self, client):
        watershed_id = _seed_watershed(client)
        resp = client.post(
            f"/watersheds/{watershed_id}/sensor-readings",
            json={"water_level_m": 1.5, "seismic_activity": 0.2},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "manual"

    def test_post_sensor_reading_missing_watershed_is_404(self, client):
        resp = client.post(
            "/watersheds/999/sensor-readings", json={"water_level_m": 1.0, "seismic_activity": 0.1}
        )
        assert resp.status_code == 404


class TestCycleRoute:
    def test_run_cycle_scores_the_seeded_watershed(self, client):
        watershed_id = _seed_watershed(client)
        resp = client.post("/cycle/run")
        assert resp.status_code == 200
        scores = resp.json()
        assert len(scores) == 1
        assert scores[0]["level"] in {"low", "moderate", "high", "critical"}

        # And it's now reflected as the watershed's latest_risk.
        watershed_resp = client.get(f"/watersheds/{watershed_id}")
        assert watershed_resp.json()["latest_risk"] is not None


class TestAlertsRoute:
    def test_list_alerts_empty(self, client):
        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGlacierRoutes:
    def test_list_glaciers(self, client):
        _seed_glacier(client)
        resp = client.get("/glaciers")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_glaciers_by_name(self, client):
        _seed_glacier(client, name="Ngozumpa Glacier", osm_id=1)
        _seed_glacier(client, name="Khumbu Glacier", osm_id=2)

        resp = client.get("/glaciers/search", params={"q": "Ngozumpa"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Ngozumpa Glacier"

    def test_stats_reflect_seeded_glaciers(self, client):
        _seed_glacier(client, name="Named One", osm_id=1, area_km2=10.0)
        _seed_glacier(client, name=None, osm_id=2, area_km2=5.0)

        resp = client.get("/glaciers/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert body["named_count"] == 1
        assert body["with_area_count"] == 2
        assert body["total_area_km2"] == 15.0

    def test_get_glacier_detail(self, client):
        glacier_id = _seed_glacier(client, geometry_geojson='{"type": "Polygon", "coordinates": []}')
        resp = client.get(f"/glaciers/{glacier_id}")
        assert resp.status_code == 200
        assert resp.json()["geometry_geojson"] is not None

    def test_get_missing_glacier_is_404(self, client):
        resp = client.get("/glaciers/999")
        assert resp.status_code == 404

    def test_analyze_glacier_returns_real_looking_score(self, client):
        glacier_id = _seed_glacier(client)
        resp = client.post(f"/glaciers/{glacier_id}/analyze")
        assert resp.status_code == 200
        body = resp.json()
        assert body["glacier_id"] == glacier_id
        assert body["sensor_available"] is False
        assert 0 <= body["score"] <= 100
        assert body["observation_count"] == 1

    def test_analyze_missing_glacier_is_404(self, client):
        resp = client.post("/glaciers/999/analyze")
        assert resp.status_code == 404

    def test_analyze_twice_does_not_duplicate_observations_within_dedup_window(self, client):
        # demo-mode ingestion always advances (unlike live mode's real
        # scene dedup), so this asserts the count grows by exactly one per
        # call rather than staying flat — still confirms no double-insert.
        glacier_id = _seed_glacier(client)
        client.post(f"/glaciers/{glacier_id}/analyze")
        second = client.post(f"/glaciers/{glacier_id}/analyze")
        assert second.json()["observation_count"] == 2

    def test_risk_history_has_one_point_per_analysis(self, client):
        glacier_id = _seed_glacier(client)
        assert client.get(f"/glaciers/{glacier_id}/risk-history").json() == []

        client.post(f"/glaciers/{glacier_id}/analyze")
        client.post(f"/glaciers/{glacier_id}/analyze")

        history = client.get(f"/glaciers/{glacier_id}/risk-history")
        assert history.status_code == 200
        points = history.json()
        assert len(points) == 2
        # chronological, and every point carries a real-shaped score/level
        assert points[0]["computed_at"] <= points[1]["computed_at"]
        for p in points:
            assert 0 <= p["score"] <= 100
            assert p["level"] in {"low", "moderate", "high", "critical"}
            assert p["sensor_component"] == 0.0

    def test_risk_history_missing_glacier_is_404(self, client):
        resp = client.get("/glaciers/999999/risk-history")
        assert resp.status_code == 404
