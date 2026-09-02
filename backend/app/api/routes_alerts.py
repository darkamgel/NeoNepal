from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..models import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(Alert)
        .order_by(Alert.triggered_at.desc())
        .limit(limit)
        .all()
    )
