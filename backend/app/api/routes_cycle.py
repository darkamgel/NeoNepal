"""Manual trigger for a risk-recompute cycle — lets a demo advance the
simulated feed on demand instead of waiting for the scheduler interval.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..risk.scheduler import run_cycle

router = APIRouter(prefix="/cycle", tags=["cycle"])


@router.post("/run", response_model=list[schemas.RiskScoreOut])
def trigger_cycle(db: Session = Depends(get_db)):
    return run_cycle(db)
