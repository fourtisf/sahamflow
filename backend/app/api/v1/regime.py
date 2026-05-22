from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RegimeHistory
from app.schemas.responses import RegimeResponse

router = APIRouter(prefix="/regime", tags=["regime"])


def _to_response(row: RegimeHistory) -> RegimeResponse:
    return RegimeResponse(
        date=row.date,
        regime=row.regime,
        confidence=float(row.confidence) if row.confidence is not None else None,
        raw_score=float(row.raw_score) if row.raw_score is not None else None,
        breadth_ratio=float(row.breadth_ratio) if row.breadth_ratio is not None else None,
        foreign_flow_5d=row.foreign_flow_5d,
        factors=(row.extra or {}).get("factors"),
    )


@router.get("/current", response_model=RegimeResponse)
def current_regime(db: Session = Depends(get_db)):
    row = db.execute(
        select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No regime computed yet. Run POST /sync/regime.")
    return _to_response(row)


@router.get("/history", response_model=list[RegimeResponse])
def regime_history(days: int = 30, db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(RegimeHistory)
        .where(RegimeHistory.date >= since)
        .order_by(RegimeHistory.date.desc())
    ).scalars().all()
    return [_to_response(r) for r in rows]
