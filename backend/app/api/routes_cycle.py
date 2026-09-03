"""Manual trigger for a risk-recompute cycle — lets a demo advance the
simulated feed on demand instead of waiting for the scheduler interval.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..rate_limit import RateLimiter
from ..risk.scheduler import run_cycle

router = APIRouter(prefix="/cycle", tags=["cycle"])

# Iterates every watershed's lakes, each a real satellite + weather fetch —
# the most expensive endpoint in the app per call.
_rate_limiter = RateLimiter(max_calls=2, window_seconds=30)


@router.post("/run", response_model=list[schemas.RiskScoreOut], dependencies=[Depends(_rate_limiter)])
def trigger_cycle(db: Session = Depends(get_db)):
    return run_cycle(db)
