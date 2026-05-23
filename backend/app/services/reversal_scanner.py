"""Reversal candidate scanner — untuk bottom-fishing saat regime turun.

Saat regime modifier = 'Potential Accumulation', sinyal momentum-only akan ramai
Strong Sell semua (trend-following bawaan). Tapi yang dicari trader di bottom
adalah hal sebaliknya: saham yang menunjukkan SIGNATURE PEMBALIKAN — oversold
ekstrem + divergensi + reversal day + volume thrust di green close.

Output: score 0..100 reversal probability per ticker, plus daftar signature.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import technical_analysis
from app.services.data_sync import load_ohlcv_df
from app.services.market_signals import (
    consecutive_down_streak,
    gap_filled_today,
    reversal_after_streak,
)


def _bullish_rsi_divergence(close: pd.Series, lookback: int = 20) -> bool:
    """Price prints lower low vs prior lookback, but RSI prints higher low."""
    if len(close) < lookback + 5:
        return False
    r = technical_analysis.rsi(close)
    recent_low_idx = close.iloc[-lookback:].idxmin()
    prior = close.iloc[-(lookback * 2): -lookback]
    if prior.empty:
        return False
    prior_low_idx = prior.idxmin()
    if close.loc[recent_low_idx] >= close.loc[prior_low_idx]:
        return False  # no lower low in price
    if r.loc[recent_low_idx] <= r.loc[prior_low_idx]:
        return False  # RSI also lower → no divergence
    return True


def _green_volume_thrust(df: pd.DataFrame) -> bool:
    """Latest bar is green AND volume > 1.5× 20-day average."""
    if len(df) < 21:
        return False
    last = df.iloc[-1]
    if last["close"] <= last["open"]:
        return False
    avg = df["volume"].rolling(20).mean().iloc[-1]
    return bool(avg and last["volume"] > 1.5 * avg)


def scan_ticker(df: pd.DataFrame) -> dict | None:
    if df.empty or len(df) < 30 or not {"high", "low", "close", "volume"}.issubset(df.columns):
        return None
    bars = [
        {
            "date": str(idx),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        for idx, row in df.iterrows()
    ]
    last = df.iloc[-1]
    rsi_v = float(technical_analysis.rsi(df["close"]).iloc[-1])
    stoch = float(technical_analysis.stoch_rsi(df["close"]).iloc[-1])

    signatures: list[str] = []
    score = 0

    if rsi_v < 30:
        signatures.append(f"RSI oversold ({rsi_v:.0f})")
        score += 25
    elif rsi_v < 40:
        signatures.append(f"RSI rendah ({rsi_v:.0f})")
        score += 12

    if stoch < 0.2:
        signatures.append("StochRSI oversold")
        score += 10

    streak = consecutive_down_streak(bars)
    if streak >= 5:
        signatures.append(f"Streak turun {streak}D (capitulation)")
        score += 15

    rev = reversal_after_streak(bars, min_streak=4)
    if rev:
        signatures.append(f"Reversal day +{rev['reversal_pct']}% setelah {rev['streak_length']}D turun")
        score += 25

    if _green_volume_thrust(df):
        signatures.append("Volume thrust di green close (>1.5× 20D)")
        score += 15

    if _bullish_rsi_divergence(df["close"]):
        signatures.append("Bullish RSI divergence (price LL, RSI HL)")
        score += 20

    gap = gap_filled_today(bars)
    if gap:
        signatures.append(f"Gap closed (gap {gap['gap_date']} ke-fill)")
        score += 10

    # Leading indicators — partial credit untuk setup yang BELUM sempurna
    # Bantu kandidat marginal muncul saat market belum extreme oversold.
    if 40 <= rsi_v < 50 and stoch < 0.4:
        signatures.append(f"Pre-oversold (RSI {rsi_v:.0f}, StochRSI {stoch:.2f})")
        score += 5
    if streak >= 3 and streak < 5:
        signatures.append(f"Streak turun {streak}D (early capitulation)")
        score += 8

    score = min(100, score)
    if score < 10:
        return None  # threshold longgar (10) untuk capture early-stage reversal

    return {
        "score": score,
        "rsi": round(rsi_v, 1),
        "stoch_rsi": round(stoch, 2),
        "last_close": float(last["close"]),
        "signatures": signatures,
    }


def scan_universe(db: Session, top_n: int = 20) -> list[dict]:
    """Scan SEMUA ticker yang punya OHLCV di DB (bukan hanya LQ45 hardcoded).

    Includes saham yang user pernah klik (lazy-fetched dari yfinance).
    Threshold longgar (>=15) supaya kandidat tetap muncul saat market belum
    extreme oversold.
    """
    from app.models import OHLCVDaily
    from sqlalchemy import select, distinct

    tickers = db.execute(select(distinct(OHLCVDaily.ticker))).scalars().all()
    out: list[dict] = []
    for t in tickers:
        df = load_ohlcv_df(db, t)
        result = scan_ticker(df)
        if result:
            out.append({"ticker": t, **result})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_n]
