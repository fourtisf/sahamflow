"""Bandar (smart-money) detection — Wyckoff phase estimate (Tahap 3).

IMPORTANT (per spec): precise bandar detection needs accurate paid broker-summary
data. For the MVP this is a PROXY built from price/volume + foreign flow patterns,
and every result is flagged estimated=True so the UI can label it honestly.

Phase heuristic:
  Accumulation  flat/down price, rising volume, foreign net buy
  Markup        rising price, rising volume
  Distribution  flat/up price stalling, high volume, foreign net sell
  Markdown      falling price, elevated volume
"""

from __future__ import annotations

import pandas as pd


def detect(ohlcv: pd.DataFrame, foreign_net_5d: int | None = None) -> dict:
    """ohlcv: DataFrame with close/volume, oldest-to-newest. Needs >= 10 rows."""
    if ohlcv is None or len(ohlcv) < 10:
        return {"phase": "Unknown", "score": 0, "estimated": True}

    close = ohlcv["close"]
    vol = ohlcv["volume"] if "volume" in ohlcv else pd.Series(dtype=float)

    price_chg_5d = (close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0.0
    vol_ratio = (
        vol.iloc[-5:].mean() / vol.iloc[-20:].mean()
        if len(vol) >= 20 and vol.iloc[-20:].mean()
        else 1.0
    )
    foreign_buy = (foreign_net_5d or 0) > 0

    if price_chg_5d > 0.03 and vol_ratio > 1.1:
        phase, base = "Markup", 80
    elif abs(price_chg_5d) <= 0.03 and vol_ratio > 1.1 and foreign_buy:
        phase, base = "Accumulation", 75
    elif price_chg_5d < -0.03 and vol_ratio > 1.0:
        phase, base = "Markdown", 45
    elif vol_ratio > 1.2 and not foreign_buy:
        phase, base = "Distribution", 60
    else:
        phase, base = "Accumulation", 55

    # Nudge score by the strength of the volume thrust.
    score = int(min(99, max(1, base + (vol_ratio - 1) * 20)))
    return {
        "phase": phase,
        "score": score,
        "vol_ratio": round(float(vol_ratio), 2),
        "price_chg_5d": round(float(price_chg_5d), 4),
        "estimated": True,
    }
