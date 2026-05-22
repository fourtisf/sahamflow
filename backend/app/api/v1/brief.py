from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import RegimeHistory, SignalCache

router = APIRouter(prefix="/brief", tags=["brief"])


@router.get("/today")
def brief_today(db: Session = Depends(get_db)):
    """AI morning brief. Generates on demand from today's regime + top signals.

    Requires ANTHROPIC_API_KEY. Caches in Redis for one day (handled in the
    narrative generator). The model is constrained to only use the data passed in.
    """
    regime = db.execute(
        select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
    ).scalar_one_or_none()
    if not regime:
        raise HTTPException(404, "No regime computed yet. Run POST /sync/regime.")

    top = db.execute(
        select(SignalCache)
        .where(SignalCache.date == regime.date)
        .order_by(SignalCache.composite_score.desc())
        .limit(settings.NARRATIVE_TOP_N)
    ).scalars().all()

    top_signals = [
        {
            "ticker": s.ticker,
            "score": float(s.composite_score) if s.composite_score is not None else None,
            "signal": (s.indicators or {}).get("signal_label"),
            "bandar_phase": s.bandar_phase,
        }
        for s in top[:10]
    ]

    market_data = {
        "regime": regime.regime,
        "confidence": float(regime.confidence) if regime.confidence is not None else None,
        "breadth": float(regime.breadth_ratio) if regime.breadth_ratio is not None else None,
        "foreign_5d": regime.foreign_flow_5d,
        "support": None,
        "resistance": None,
    }

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            503,
            "ANTHROPIC_API_KEY not configured — AI brief unavailable. "
            "Underlying data is available via /regime and /screener.",
        )

    from app.services import narrative_generator

    text = narrative_generator.generate_brief(market_data, top_signals)
    return {"date": regime.date, "market_data": market_data, "brief": text}
