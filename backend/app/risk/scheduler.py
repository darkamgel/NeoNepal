"""Periodic risk recomputation. Also exposed as `run_cycle` so it can be
triggered on-demand from the API for demoing without waiting on the interval.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from ..alerts.dispatch import maybe_dispatch_alert
from ..db import SessionLocal
from ..ingestion import satellite as satellite_ingestion
from ..ingestion import sensors as sensors_ingestion
from ..models import RiskScore, Watershed
from .scoring import compute_risk

logger = logging.getLogger("neonepal.scheduler")

RECOMPUTE_INTERVAL_SECONDS = 300


def run_cycle(db: Session) -> list[RiskScore]:
    results = []
    watersheds = db.query(Watershed).all()
    for watershed in watersheds:
        for lake in watershed.lakes:
            satellite_ingestion.ingest_latest(db, lake.lat, lake.lon, lake_id=lake.id)
        sensors_ingestion.ingest_latest(db, watershed)

        components = compute_risk(db, watershed)
        risk_score = RiskScore(
            watershed_id=watershed.id,
            score=components.score,
            level=components.level,
            lake_growth_component=components.lake_growth,
            terrain_change_component=components.terrain_change,
            rainfall_component=components.rainfall,
            sensor_component=components.sensor,
        )
        db.add(risk_score)
        db.commit()
        db.refresh(risk_score)
        results.append(risk_score)

        maybe_dispatch_alert(db, watershed, risk_score, at=risk_score.computed_at)

    return results


def _scheduled_job():
    db = SessionLocal()
    try:
        results = run_cycle(db)
        logger.info("Risk recompute cycle complete: %d watersheds scored", len(results))
    finally:
        db.close()


_scheduler = BackgroundScheduler()


def start_scheduler():
    if not _scheduler.running:
        _scheduler.add_job(
            _scheduled_job,
            "interval",
            seconds=RECOMPUTE_INTERVAL_SECONDS,
            id="risk_recompute",
            replace_existing=True,
        )
        _scheduler.start()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
