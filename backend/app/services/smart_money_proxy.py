"""Smart Money Proxy — pengganti foreign flow ketika data berbayar tidak tersedia.

IDX retail tidak ada akses gratis ke broker summary akurat. Sebagai gantinya
kami komposisi sinyal yang bisa dihitung dari OHLCV publik untuk MENDEKATI
behavior smart money:

- Bandar phase (Wyckoff proxy): Accumulation/Markup positif, Distribution/Markdown negatif
- Volume thrust di green/red day: tinggi di hijau = beli; tinggi di merah = panic
- Range position 60D: di support = akumulasi territory; di resistance = distribusi
- Reversal signature + RSI extremes
- Composite score sebagai weak signal

Output: smart_money_score -100..+100, label, list driver bukti.

LABEL JUJUR di UI: 'proxy' bukan 'foreign flow nyata'.
"""

from __future__ import annotations

import pandas as pd

from app.services import technical_analysis


def score_ticker(df: pd.DataFrame, breakdown: dict, bandar: dict) -> dict:
    """Compute smart money proxy score for one ticker."""
    if df.empty or len(df) < 20:
        return {"score": 0, "label": "Insufficient Data", "drivers": []}

    score = 0
    drivers: list[str] = []
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    # 1. Bandar phase (Wyckoff proxy)
    phase = bandar.get("phase", "")
    if phase == "Accumulation":
        score += 30
        drivers.append("Bandar fase Accumulation (+30)")
    elif phase == "Markup":
        score += 25
        drivers.append("Bandar fase Markup (+25)")
    elif phase == "Distribution":
        score -= 25
        drivers.append("Bandar fase Distribution (−25)")
    elif phase == "Markdown":
        score -= 30
        drivers.append("Bandar fase Markdown (−30)")

    # 2. Volume × direction signature
    vol_ratio = breakdown.get("volume_ratio_20d") or 1.0
    is_green = last["close"] > prev["close"]
    if vol_ratio >= 1.5 and is_green:
        score += 20
        drivers.append(f"Volume thrust {vol_ratio}× di green close (+20) — institusi serap")
    elif vol_ratio >= 1.5 and not is_green:
        score -= 20
        drivers.append(f"Volume thrust {vol_ratio}× di red close (−20) — panic dump")
    elif vol_ratio < 0.7 and not is_green:
        score += 10
        drivers.append(f"Volume kering {vol_ratio}× di red (+10) — supply exhausted")

    # 3. Range position 60D
    rp = breakdown.get("range_position_pct")
    if rp is not None:
        if rp < 20:
            score += 15
            drivers.append(f"Range position {rp}% (dekat support, akumulasi area) +15")
        elif rp > 80:
            score -= 15
            drivers.append(f"Range position {rp}% (dekat resistance, distribusi area) −15")

    # 4. RSI extreme + arah harga
    rsi = breakdown.get("rsi14")
    if rsi is not None:
        if rsi < 35 and is_green:
            score += 15
            drivers.append(f"RSI {rsi} oversold + green close (+15) — reversal awal")
        elif rsi > 70 and not is_green:
            score -= 15
            drivers.append(f"RSI {rsi} overbought + red close (−15) — distribusi awal")

    # 5. vs MA200 distance (strength of trend)
    ma200_d = breakdown.get("ma200_distance_pct")
    if ma200_d is not None:
        if ma200_d > 5:
            score += 5
            drivers.append(f"+{ma200_d}% vs MA200 (uptrend kuat) +5")
        elif ma200_d < -10:
            score -= 5
            drivers.append(f"{ma200_d}% vs MA200 (downtrend dalam) −5")

    # Clip
    score = max(-100, min(100, score))

    if score >= 50:
        label = "Strong Accumulation"
    elif score >= 20:
        label = "Accumulation"
    elif score > -20:
        label = "Neutral"
    elif score > -50:
        label = "Distribution"
    else:
        label = "Strong Distribution"

    return {"score": score, "label": label, "drivers": drivers}
