"""Simulated ground sensor feed.

Structured exactly as a real LoRaWAN water-level/seismic sensor payload would
be (timestamp, water_level_m, seismic_activity), so swapping in real hardware
later is a matter of changing the source of this data, not the schema. See
docs/DEPLOYMENT.md for real sensor hardware options and cost.
"""

import datetime as dt
import random

from sqlalchemy.orm import Session

from ..models import SensorReading, Watershed


def ingest_latest(db: Session, watershed: Watershed) -> SensorReading:
    last = (
        db.query(SensorReading)
        .filter(SensorReading.watershed_id == watershed.id)
        .order_by(SensorReading.recorded_at.desc())
        .first()
    )
    base_water = last.water_level_m if last else 1.0
    base_seismic = last.seismic_activity if last else 0.05

    reading = SensorReading(
        watershed_id=watershed.id,
        recorded_at=dt.datetime.utcnow(),
        water_level_m=round(max(0.0, base_water + random.uniform(-0.05, 0.05)), 2),
        seismic_activity=round(min(1.0, max(0.0, base_seismic + random.uniform(-0.01, 0.03))), 3),
        source="simulated",
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def get_latest_reading(db: Session, watershed_id: int) -> SensorReading | None:
    return (
        db.query(SensorReading)
        .filter(SensorReading.watershed_id == watershed_id)
        .order_by(SensorReading.recorded_at.desc())
        .first()
    )
