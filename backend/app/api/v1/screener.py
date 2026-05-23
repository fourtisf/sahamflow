from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import SignalCache
from app.schemas.responses import ScreenerRow
from app.services import reversal_scanner

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("", response_model=list[ScreenerRow])
def screener(min_score: float = 0.0, db: Session = Depends(get_db)):
    """Latest signals across the universe, filtered by composite score."""
    latest_date = db.execute(
        select(SignalCache.date).order_by(SignalCache.date.desc()).limit(1)
    ).scalar_one_or_none()
    if latest_date is None:
        return []

    rows = db.execute(
        select(SignalCache)
        .where(SignalCache.date == latest_date)
        .where(SignalCache.composite_score >= min_score)
        .order_by(SignalCache.composite_score.desc())
    ).scalars().all()

    return [
        ScreenerRow(
            ticker=r.ticker,
            composite_score=float(r.composite_score) if r.composite_score is not None else None,
            signal=(r.indicators or {}).get("signal_label"),
            bandar_phase=r.bandar_phase,
            bandar_score=r.bandar_score,
            foreign_signal=r.foreign_signal,
            indicators=r.indicators,
        )
        for r in rows
    ]


@router.get("/reversals")
def reversals(top_n: int = 15, db: Session = Depends(get_db)):
    """Reversal candidates — saham dengan signature pembalikan saat market bottoming.

    Skor 0-100 berdasar: RSI/StochRSI oversold, streak turun, reversal day,
    volume thrust di green close, bullish RSI divergence, gap closed.
    """
    return reversal_scanner.scan_universe(db, top_n=top_n)
