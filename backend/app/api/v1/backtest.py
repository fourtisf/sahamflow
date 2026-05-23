from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import backtest_engine, portfolio_backtest, technical_analysis
from app.services.data_sync import load_ohlcv_df

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/portfolio")
def run_portfolio_backtest(
    lookback_days: int = Query(500, ge=120, le=2000),
    max_positions: int = Query(5, ge=1, le=20),
    min_score: float = Query(0.5, ge=0.2, le=1.0),
    starting_equity: float = Query(100_000_000, ge=10_000_000),
    db: Session = Depends(get_db),
):
    """Whole-portfolio walk-forward backtest. JAWABAN: kalau ikuti semua sinyal
    Sahamflow di seluruh universe, equity curve & metrics-nya begini.

    Long-only IDX, biaya 0.6% RT, sizing 1% risk. Limit max_positions paralel."""
    result = portfolio_backtest.run(
        db,
        lookback_days=lookback_days,
        max_positions=max_positions,
        min_score=min_score,
        starting_equity=starting_equity,
    )
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("")
def run_backtest(
    ticker: str = Query(..., description="Single ticker to backtest (MVP)"),
    strategy: str = "composite",
    min_score: float = 0.3,
    db: Session = Depends(get_db),
):
    """Backtest the composite-score strategy on one ticker's history.

    Entry signal: composite score over a rolling window crosses min_score. The
    multi-stock portfolio backtest (Bandar>80 + AI>75% + Foreign buy) lands once
    foreign/AI data is populated across the universe.
    """
    df = load_ohlcv_df(db, ticker.upper(), days=2000)
    if df.empty or len(df) < 60:
        raise HTTPException(404, f"Not enough OHLCV history for {ticker}.")

    scores = []
    for i in range(len(df)):
        window = df.iloc[: i + 1]
        if len(window) < 20:
            scores.append(0.0)
            continue
        s, _ = technical_analysis.composite_score(window)
        scores.append(s)

    import pandas as pd

    entry_signal = pd.Series([s >= min_score for s in scores], index=df.index)
    metrics = backtest_engine.run(df, entry_signal)
    return {"ticker": ticker.upper(), "strategy": strategy, "min_score": min_score, **metrics}
