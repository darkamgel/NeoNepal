import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..ingestion import satellite as satellite_ingestion
from ..models import Glacier, SatelliteObservation
from ..rate_limit import RateLimiter
from ..risk.scoring import compute_adhoc_risk
from .deps import get_or_404

router = APIRouter(prefix="/glaciers", tags=["glaciers"])

# One real satellite + weather fetch per call. Looser than /cycle/run since
# it targets a single glacier rather than iterating all watersheds, but
# still bounded — the directory has ~3,300 glaciers and nothing should be
# able to script through all of them quickly.
_analyze_rate_limiter = RateLimiter(max_calls=5, window_seconds=60)


@router.get("/search", response_model=list[schemas.GlacierOut])
def search_glaciers(q: str, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(Glacier)
        .filter(Glacier.name.ilike(f"%{q}%"))
        .order_by(Glacier.name)
        .limit(limit)
        .all()
    )


@router.get("/stats", response_model=schemas.GlacierStatsOut)
def glacier_stats(db: Session = Depends(get_db)):
    total_count = db.query(Glacier).count()
    named_count = db.query(Glacier).filter(Glacier.name.isnot(None)).count()
    with_area_count = db.query(Glacier).filter(Glacier.area_km2.isnot(None)).count()
    total_area_km2 = db.query(func.sum(Glacier.area_km2)).scalar() or 0.0
    largest = (
        db.query(Glacier)
        .filter(Glacier.area_km2.isnot(None))
        .order_by(Glacier.area_km2.desc())
        .limit(10)
        .all()
    )
    return schemas.GlacierStatsOut(
        total_count=total_count,
        named_count=named_count,
        with_area_count=with_area_count,
        total_area_km2=round(total_area_km2, 1),
        largest=largest,
    )


@router.get("/{glacier_id}", response_model=schemas.GlacierDetailOut)
def get_glacier(glacier_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Glacier, glacier_id, "Glacier not found")


@router.post(
    "/{glacier_id}/analyze",
    response_model=schemas.GlacierRiskOut,
    dependencies=[Depends(_analyze_rate_limiter)],
)
def analyze_glacier(glacier_id: int, db: Session = Depends(get_db)):
    """On-demand risk analysis for any glacier — real satellite/weather
    fetch, so this does real work (a few seconds), not an instant lookup.
    Persists the satellite observation, so a second call on the same
    glacier produces a real terrain-change comparison instead of the
    "no prior observation" default.
    """
    glacier = get_or_404(db, Glacier, glacier_id, "Glacier not found")

    satellite_ingestion.ingest_latest(db, glacier.lat, glacier.lon, glacier_id=glacier.id)
    components = compute_adhoc_risk(db, glacier)
    observation_count = (
        db.query(SatelliteObservation).filter(SatelliteObservation.glacier_id == glacier.id).count()
    )

    return schemas.GlacierRiskOut(
        glacier_id=glacier.id,
        score=components.score,
        level=components.level,
        terrain_change_component=components.terrain_change,
        lake_growth_component=components.lake_growth,
        rainfall_component=components.rainfall,
        sensor_available=components.sensor_available,
        observation_count=observation_count,
        computed_at=dt.datetime.utcnow(),
    )


@router.get("/{glacier_id}/risk-history", response_model=list[schemas.GlacierRiskHistoryPointOut])
def get_glacier_risk_history(glacier_id: int, db: Session = Depends(get_db)):
    """A glacier's real risk history, built by replaying compute_adhoc_risk
    at each of its past observation timestamps (see that function's
    docstring) — not a separately persisted score table. Read-only against
    Planetary Computer (no new satellite fetch); real historical rainfall
    is still fetched per point via the existing Open-Meteo archive path,
    naturally bounded since observation count is gated by how many times
    "Analyze risk" has been clicked for this glacier (already rate-limited).
    """
    glacier = get_or_404(db, Glacier, glacier_id, "Glacier not found")

    observations = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.glacier_id == glacier.id)
        .order_by(SatelliteObservation.observed_at.asc())
        .all()
    )

    points = []
    for obs in observations:
        components = compute_adhoc_risk(db, glacier, asof=obs.observed_at)
        points.append(
            schemas.GlacierRiskHistoryPointOut(
                computed_at=obs.observed_at,
                score=components.score,
                level=components.level,
                terrain_change_component=components.terrain_change,
                lake_growth_component=components.lake_growth,
                rainfall_component=components.rainfall,
            )
        )
    return points


@router.get("", response_model=list[schemas.GlacierOut])
def list_glaciers(
    limit: int = 100,
    offset: int = 0,
    sort: str = "name",
    db: Session = Depends(get_db),
):
    query = db.query(Glacier)
    if sort == "area_desc":
        query = query.order_by(Glacier.area_km2.desc().nullslast())
    else:
        query = query.order_by(Glacier.name.isnot(None).desc(), Glacier.name, Glacier.id)
    return query.offset(offset).limit(limit).all()
