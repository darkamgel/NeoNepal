import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..models import RiskScore, SatelliteObservation, SensorReading, Watershed

router = APIRouter(prefix="/watersheds", tags=["watersheds"])


def _latest_risk(db: Session, watershed_id: int) -> RiskScore | None:
    return (
        db.query(RiskScore)
        .filter(RiskScore.watershed_id == watershed_id)
        .order_by(RiskScore.computed_at.desc())
        .first()
    )


@router.get("", response_model=list[schemas.WatershedWithRiskOut])
def list_watersheds(db: Session = Depends(get_db)):
    watersheds = db.query(Watershed).all()
    out = []
    for w in watersheds:
        item = schemas.WatershedWithRiskOut.model_validate(w)
        item.latest_risk = _latest_risk(db, w.id)
        out.append(item)
    return out


@router.get("/{watershed_id}", response_model=schemas.WatershedWithRiskOut)
def get_watershed(watershed_id: int, db: Session = Depends(get_db)):
    w = db.query(Watershed).filter(Watershed.id == watershed_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watershed not found")
    item = schemas.WatershedWithRiskOut.model_validate(w)
    item.latest_risk = _latest_risk(db, w.id)
    return item


@router.get("/{watershed_id}/risk-history", response_model=list[schemas.RiskScoreOut])
def get_risk_history(watershed_id: int, limit: int = 100, db: Session = Depends(get_db)):
    scores = (
        db.query(RiskScore)
        .filter(RiskScore.watershed_id == watershed_id)
        .order_by(RiskScore.computed_at.asc())
        .limit(limit)
        .all()
    )
    return scores


@router.get("/{watershed_id}/observations", response_model=list[schemas.SatelliteObservationOut])
def get_observations(watershed_id: int, db: Session = Depends(get_db)):
    w = db.query(Watershed).filter(Watershed.id == watershed_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watershed not found")
    lake_ids = [lake.id for lake in w.lakes]
    return (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.lake_id.in_(lake_ids))
        .order_by(SatelliteObservation.observed_at.asc())
        .all()
    )


@router.get("/{watershed_id}/sensor-readings", response_model=list[schemas.SensorReadingOut])
def get_sensor_readings(watershed_id: int, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(SensorReading)
        .filter(SensorReading.watershed_id == watershed_id)
        .order_by(SensorReading.recorded_at.asc())
        .limit(limit)
        .all()
    )


@router.post("/{watershed_id}/sensor-readings", response_model=schemas.SensorReadingOut)
def post_sensor_reading(
    watershed_id: int, reading: schemas.SensorReadingIn, db: Session = Depends(get_db)
):
    """Manual ingestion endpoint — demos the path a real LoRaWAN gateway would use."""
    w = db.query(Watershed).filter(Watershed.id == watershed_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watershed not found")

    record = SensorReading(
        watershed_id=watershed_id,
        recorded_at=dt.datetime.utcnow(),
        water_level_m=reading.water_level_m,
        seismic_activity=reading.seismic_activity,
        source="manual",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
