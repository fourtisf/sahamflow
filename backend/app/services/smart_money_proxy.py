"""Smart Money Proxy — regime-aware heuristik pengganti foreign flow.

Versi sebelumnya tidak sadar regime: di Potential Accumulation, saham yang
historis Markdown phase (turun + volume tinggi) tetap diberi label Distribution,
padahal itu justru kapitulasi yang biasanya = bottom. Hasilnya: Composite
bilang BUY (reversion mode), SmartMoney bilang Distribution → kontradiksi.

Versi ini: function score_ticker(df, breakdown, bandar, regime_modifier).
- Default mode: skoring biasa (bandar phase, volume direction, range, RSI)
- regime_modifier='Potential Accumulation': flip interpretasi sinyal merah
  jadi konstruktif (capitulation, supply exhausted, oversold bounce setup)
- regime_modifier='Distribution Risk': sinyal hijau ekstrem dianggap warning
"""

from __future__ import annotations

import pandas as pd


def score_ticker(
    df: pd.DataFrame,
    breakdown: dict,
    bandar: dict,
    regime_modifier: str | None = None,
) -> dict:
    """Compute smart money proxy score, regime-aware."""
    if df.empty or len(df) < 20:
        return {"score": 0, "label": "Insufficient Data", "drivers": []}

    score = 0
    drivers: list[str] = []
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    is_green = last["close"] > prev["close"]
    bottom_context = regime_modifier in {"Potential Accumulation", "Markdown Capitulation"}
    top_context = regime_modifier == "Distribution Risk"

    # 1. Bandar phase — interpretasi tergantung context
    phase = bandar.get("phase", "")
    if bottom_context:
        # Di bottom regime: Markdown = kapitulasi (positif), Distribution = late
        # late distribution juga = exhaustion. Markup/Accumulation = early reversal
        if phase == "Accumulation":
            score += 35
            drivers.append("Bandar Accumulation di regime bottom (+35) — smart money serap")
        elif phase == "Markup":
            score += 30
            drivers.append("Bandar Markup di regime bottom (+30) — pembalikan kuat")
        elif phase == "Distribution":
            score += 5
            drivers.append("Bandar Distribution di regime bottom (+5) — late seller, exhaustion")
        elif phase == "Markdown":
            score += 10
            drivers.append("Bandar Markdown di regime bottom (+10) — kapitulasi, near exhaustion")
    elif top_context:
        # Di top regime: Markup/Accum = overextension, Distribution/Markdown = early sign
        if phase == "Distribution":
            score -= 30
            drivers.append("Bandar Distribution di regime top (−30) — smart money keluar")
        elif phase == "Markdown":
            score -= 25
            drivers.append("Bandar Markdown di regime top (−25) — distribusi confirmed")
        elif phase in {"Accumulation", "Markup"}:
            score -= 10
            drivers.append(f"Bandar {phase} di regime top (−10) — overextension warning")
    else:
        # Netral context: skoring lurus
        if phase == "Accumulation":
            score += 30
            drivers.append("Bandar Accumulation (+30)")
        elif phase == "Markup":
            score += 25
            drivers.append("Bandar Markup (+25)")
        elif phase == "Distribution":
            score -= 25
            drivers.append("Bandar Distribution (−25)")
        elif phase == "Markdown":
            score -= 30
            drivers.append("Bandar Markdown (−30)")

    # 2. Volume × direction — interpretasi tergantung context
    vol_ratio = breakdown.get("volume_ratio_20d") or 1.0
    if vol_ratio >= 1.5 and is_green:
        score += 20
        drivers.append(f"Volume thrust {vol_ratio}× di green close (+20) — institusi serap")
    elif vol_ratio >= 1.5 and not is_green:
        if bottom_context:
            score += 10
            drivers.append(f"Volume thrust {vol_ratio}× di red close (+10) — KAPITULASI, supply dumped")
        else:
            score -= 20
            drivers.append(f"Volume thrust {vol_ratio}× di red close (−20) — panic dump")
    elif vol_ratio < 0.7 and not is_green:
        score += 10
        drivers.append(f"Volume kering {vol_ratio}× di red (+10) — supply exhausted")

    # 3. Range position 60D
    rp = breakdown.get("range_position_pct")
    if rp is not None:
        if rp < 20:
            score += 20 if bottom_context else 15
            drivers.append(f"Range position {rp}% (dekat support, akumulasi area) +{20 if bottom_context else 15}")
        elif rp > 80:
            score -= 20 if top_context else 15
            drivers.append(f"Range position {rp}% (dekat resistance, distribusi area) −{20 if top_context else 15}")

    # 4. RSI extreme + arah harga
    rsi = breakdown.get("rsi14")
    if rsi is not None:
        if rsi < 35 and is_green:
            score += 20 if bottom_context else 15
            drivers.append(f"RSI {rsi} oversold + green close (+{20 if bottom_context else 15}) — reversal awal")
        elif rsi < 30 and not is_green:
            score += 8 if bottom_context else 0
            if bottom_context:
                drivers.append(f"RSI {rsi} oversold ekstrem (+8) — selling exhaustion mungkin dekat")
        elif rsi > 70 and not is_green:
            score -= 15
            drivers.append(f"RSI {rsi} overbought + red close (−15) — distribusi awal")

    # 5. vs MA200 distance
    ma200_d = breakdown.get("ma200_distance_pct")
    if ma200_d is not None:
        if ma200_d > 5:
            score += 5
            drivers.append(f"+{ma200_d}% vs MA200 (uptrend kuat) +5")
        elif ma200_d < -10:
            # Di bottom regime, ini bukan "downtrend dalam" tapi "diskon tajam"
            if bottom_context:
                score += 5
                drivers.append(f"{ma200_d}% vs MA200 (diskon tajam di regime bottom) +5")
            else:
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

    return {"score": score, "label": label, "drivers": drivers, "regime_context": regime_modifier}
