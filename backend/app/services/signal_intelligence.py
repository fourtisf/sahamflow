"""Per-stock smart-money intelligence: combines TA, ATR levels, regime context.

Replaces the bare composite score with a structured payload a trader actually
uses to make decisions. No fabricated data — every field is derived from the
ticker's OHLCV + the current regime.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegimeHistory
from app.services import bandar_detector, foreign_flow_analyzer, technical_analysis
from app.services.data_sync import load_ohlcv_df


def _bias_from_score(score: float) -> str:
    if score >= 0.2:
        return "long"
    if score <= -0.2:
        return "short"
    return "neutral"


def _conviction(score: float, regime: str | None, bandar_phase: str | None) -> dict:
    """Regime-aware conviction modifier.

    A Strong-Sell signal during 'Distribution Phase' or 'Markdown' bandar is
    high-conviction (aligned with macro & smart-money behavior). The same signal
    during 'Risk-On Bullish' is counter-trend → lower conviction.
    """
    bias = _bias_from_score(score)
    aligned = False
    note = ""
    if bias == "short" and regime in {"Distribution Phase", "Risk-Off Defensive", "Crash Mode"}:
        aligned = True
        note = f"selaras dengan regime {regime}"
    elif bias == "long" and regime in {"Risk-On Bullish", "Accumulation Phase"}:
        aligned = True
        note = f"selaras dengan regime {regime}"
    elif bias != "neutral":
        note = f"counter-trend terhadap regime {regime or 'unknown'} — keyakinan lebih rendah"

    if bias == "short" and bandar_phase == "Markdown":
        note += "; bandar fase Markdown memperkuat setup jual"
    if bias == "long" and bandar_phase in {"Accumulation", "Markup"}:
        note += f"; bandar fase {bandar_phase} memperkuat setup beli"

    base = abs(score) * 100
    if aligned:
        base = min(95, base * 1.3)
    return {"bias": bias, "regime_aligned": aligned, "conviction_pct": round(base, 1), "note": note}


def build_intel(db: Session, ticker: str) -> dict | None:
    """Return the full smart-money intel payload for a ticker, or None if no data."""
    df = load_ohlcv_df(db, ticker)
    if df.empty or len(df) < 20:
        return None

    score, indicators_raw = technical_analysis.composite_score(df)
    label = technical_analysis.signal_label(score)
    breakdown = technical_analysis.indicator_breakdown(df)

    foreign_5d = (
        int(df["foreign_net"].dropna().tail(5).sum())
        if df["foreign_net"].notna().any()
        else None
    )
    bandar = bandar_detector.detect(df, foreign_5d)
    ff = foreign_flow_analyzer.analyze(list(df["foreign_net"]))

    last_close = float(df["close"].iloc[-1])
    bias = _bias_from_score(score)
    levels = technical_analysis.execution_levels(last_close, breakdown.get("atr14"), bias)

    regime_row = db.execute(
        select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
    ).scalar_one_or_none()
    regime_name = regime_row.regime if regime_row else None
    conviction = _conviction(score, regime_name, bandar.get("phase"))

    return {
        "ticker": ticker,
        "last_close": last_close,
        "composite_score": round(score, 3),
        "signal": label,
        "indicators": breakdown,
        "bandar": bandar,
        "foreign_flow": ff,
        "levels": levels,
        "regime": {"name": regime_name, **conviction},
    }
