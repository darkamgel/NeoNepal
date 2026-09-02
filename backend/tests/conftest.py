import pytest

from app.ingestion import satellite as satellite_ingestion


@pytest.fixture(autouse=True)
def force_demo_satellite_mode(monkeypatch):
    """Tests must never depend on network access to Planetary Computer."""
    monkeypatch.setattr(satellite_ingestion, "SATELLITE_MODE", "demo")
