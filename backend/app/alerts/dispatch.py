"""Alert dispatch — prototype logs + persists; production would fan out via
SMS/IVR through a local telecom gateway or Twilio, and integrate with
NDRRMA's existing alert infrastructure. See docs/DEPLOYMENT.md.
"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from ..models import Alert, RiskScore, Watershed

logger = logging.getLogger("neonepal.alerts")

_ALERT_THRESHOLD_LEVELS = {"high", "critical"}
_DEBOUNCE_WINDOW = dt.timedelta(hours=1)


def maybe_dispatch_alert(
    db: Session, watershed: Watershed, risk_score: RiskScore, at: dt.datetime | None = None
) -> Alert | None:
    """`at` is the evaluation timestamp — defaults to now for live cycles, but
    is passed explicitly during historical backfill so debouncing is relative
    to the backfilled timeline rather than wall-clock time.
    """
    if risk_score.level not in _ALERT_THRESHOLD_LEVELS:
        return None
    at = at or dt.datetime.utcnow()

    recent = (
        db.query(Alert)
        .filter(Alert.watershed_id == watershed.id)
        .order_by(Alert.triggered_at.desc())
        .first()
    )
    if recent and (at - recent.triggered_at) < _DEBOUNCE_WINDOW and recent.level == risk_score.level:
        return None

    message = (
        f"[{risk_score.level.upper()}] Glacial hazard risk score {risk_score.score}/100 "
        f"for {watershed.name} ({watershed.district}). Immediate review recommended."
    )
    alert = Alert(
        watershed_id=watershed.id,
        triggered_at=at,
        risk_score=risk_score.score,
        level=risk_score.level,
        message=message,
        channel="log",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    logger.warning("ALERT DISPATCHED: %s", message)
    return alert
