from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import backtest_engine, technical_analysis
from app.services.data_sync import load_ohlcv_df

router = APIRouter(prefix="/backtest", tags=["backtest"])


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
