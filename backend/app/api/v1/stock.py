from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Fundamentals
from app.services import signal_intelligence

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/{ticker}/analysis")
def stock_analysis(ticker: str, db: Session = Depends(get_db)):
    """Full smart-money intel: composite, indicator breakdown, ATR levels,
    bandar, foreign flow, regime-aware conviction. No narrative (call /narrative)."""
    intel = signal_intelligence.build_intel(db, ticker.upper())
    if not intel:
        raise HTTPException(404, f"No OHLCV for {ticker}. Run POST /sync/ohlcv.")
    return intel


@router.get("/{ticker}/narrative")
def stock_narrative(ticker: str, db: Session = Depends(get_db)):
    """Buy-side analyst narrative (3 paragraphs, Bahasa Indonesia).

    Requires ANTHROPIC_API_KEY. Uses the same intel payload as /analysis so the
    model is constrained to the actual numbers — no hallucinated figures.
    """
    intel = signal_intelligence.build_intel(db, ticker.upper())
    if not intel:
        raise HTTPException(404, f"No OHLCV for {ticker}. Run POST /sync/ohlcv.")

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            503,
            "ANTHROPIC_API_KEY not configured — narrative unavailable. "
            "The structured analysis at /stock/{ticker}/analysis still works.",
        )

    from app.services import narrative_generator

    text = narrative_generator.generate_stock_narrative(ticker.upper(), intel)
    return {"ticker": ticker.upper(), "intel": intel, "narrative": text}


@router.get("/{ticker}/fundamental")
def stock_fundamental(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    row = db.get(Fundamentals, ticker)
    if not row:
        raise HTTPException(404, f"No fundamentals for {ticker}.")
    return {
        "ticker": row.ticker,
        "per": float(row.per) if row.per is not None else None,
        "pbv": float(row.pbv) if row.pbv is not None else None,
        "roe": float(row.roe) if row.roe is not None else None,
        "der": float(row.der) if row.der is not None else None,
        "revenue_yoy": float(row.revenue_yoy) if row.revenue_yoy is not None else None,
        "net_margin": float(row.net_margin) if row.net_margin is not None else None,
        "quality_score": float(row.quality_score) if row.quality_score is not None else None,
        "earnings_date": row.earnings_date,
        "red_flags": row.red_flags,
    }
