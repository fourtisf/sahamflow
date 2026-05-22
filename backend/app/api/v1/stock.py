from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Fundamentals, SignalCache
from app.schemas.responses import StockAnalysis
from app.services import bandar_detector, foreign_flow_analyzer, technical_analysis
from app.services.data_sync import load_ohlcv_df

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/{ticker}/analysis", response_model=StockAnalysis)
def stock_analysis(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    df = load_ohlcv_df(db, ticker)
    if df.empty:
        raise HTTPException(404, f"No OHLCV for {ticker}. Run POST /sync/ohlcv.")

    score, indicators = technical_analysis.composite_score(df)
    foreign_5d = (
        int(df["foreign_net"].dropna().tail(5).sum())
        if df["foreign_net"].notna().any()
        else None
    )
    bandar = bandar_detector.detect(df, foreign_5d)
    ff = foreign_flow_analyzer.analyze(list(df["foreign_net"]))

    cached = db.execute(
        select(SignalCache)
        .where(SignalCache.ticker == ticker)
        .order_by(SignalCache.date.desc())
        .limit(1)
    ).scalar_one_or_none()

    return StockAnalysis(
        ticker=ticker,
        last_close=float(df["close"].iloc[-1]),
        composite_score=round(score, 3),
        signal=technical_analysis.signal_label(score),
        indicators=indicators,
        bandar=bandar,
        foreign_flow=ff,
        narrative=cached.narrative if cached else None,
    )


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
