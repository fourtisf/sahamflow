"""Gate ketat: apakah sebuah sinyal LAYAK dikirim sebagai actionable alert?

Filosofi: "Sinyal tanpa reason = noise. Jangan kirim apapun yang tidak punya
edge terbukti + regime mendukung + likuiditas cukup + invalidation jelas."

Ini yang membedakan dumb-AI ("BBCA Strong Sell") dari buy-side desk ticket
("BUY BBCA @ trigger 5,920, SL 6,202, TP 4,993, reason: setup historis hit
62% n=18, regime selaras, ATR 2.6%, ADV 145B → likuiditas OK").
"""

from __future__ import annotations

MIN_ABS_SCORE = 0.5              # hanya Strong Buy / Strong Sell
MIN_HIT_RATE = 50.0              # setup historis ≥ 50% hit
MIN_EXPECTANCY_PCT = 0.0         # expectancy harus positif
MIN_SAMPLE_N = 5                 # minimum 5 trade historis
MIN_ADV_VALUE_IDR = 10_000_000_000  # min ADV 10 miliar/hari biar likuid
MAX_POSITION_PCT_OF_ADV = 5.0    # cap maks 5% volume harian


def qualify(intel: dict, account_size_idr: float = 500_000_000) -> dict:
    """Decide if a signal is alert-worthy and build the reasoning chain.

    Returns {qualified, score_setup, reasons[], blockers[], position}.
    'reasons' lists evidence supporting; 'blockers' lists why it doesn't qualify.
    Even non-qualified signals return their evaluation — so user can audit.
    """
    score = intel.get("composite_score", 0) or 0
    label = intel.get("signal", "Hold")
    ind = intel.get("indicators") or {}
    bandar = intel.get("bandar") or {}
    regime = intel.get("regime") or {}
    track = intel.get("track_record") or {}
    levels = intel.get("levels")
    triggers = intel.get("triggers")
    last_close = intel.get("last_close") or 0

    reasons: list[str] = []
    blockers: list[str] = []

    # --- HARD GATES (long-only) ---
    # IDX retail = no short. Hanya kirim alert untuk BUY setup (score positif).
    if score < MIN_ABS_SCORE:
        if score <= -MIN_ABS_SCORE:
            blockers.append(
                f"Composite {score} = Strong Sell. IDX retail tidak bisa short — "
                f"sinyal ini tidak actionable sebagai trade baru. (Reversal overlay "
                f"akan muncul terpisah jika kondisi bottom-fishing memenuhi.)"
            )
        else:
            blockers.append(f"Composite {score} < +{MIN_ABS_SCORE} — bukan high-conviction Buy.")
    else:
        reasons.append(f"Composite {score} ({label}) — high conviction BUY.")

    if not regime.get("regime_aligned"):
        blockers.append(f"Counter-trend terhadap regime {regime.get('name')} — keyakinan rendah.")
    else:
        reasons.append(f"Selaras dengan regime {regime.get('name')} → conviction modifier aktif.")

    # Track record gate (skip if no history)
    tr_n = track.get("n", 0)
    if tr_n >= MIN_SAMPLE_N:
        hit = track.get("hit_rate_pct", 0)
        exp = track.get("expectancy_pct", 0)
        if hit < MIN_HIT_RATE:
            blockers.append(f"Track record hit rate {hit}% < {MIN_HIT_RATE}% (n={tr_n}).")
        elif exp <= MIN_EXPECTANCY_PCT:
            blockers.append(f"Expectancy {exp}% ≤ {MIN_EXPECTANCY_PCT}% — bukan edge positif.")
        else:
            reasons.append(
                f"Track record setup ini: hit {hit}% · exp {exp}% · n={tr_n} · "
                f"PF {track.get('profit_factor')} (walk-forward, biaya 0.6% RT)."
            )
    else:
        reasons.append(f"Track record sample tipis (n={tr_n}) — perlakukan sebagai eksploratif.")

    # Liquidity gate
    adv = ind.get("adv_value_idr_20d") or 0
    if adv < MIN_ADV_VALUE_IDR:
        blockers.append(
            f"ADV 20D ≈ Rp {adv/1e9:.1f}B < Rp {MIN_ADV_VALUE_IDR/1e9:.0f}B — likuiditas tidak cukup."
        )
    else:
        reasons.append(f"Likuiditas OK: ADV 20D ≈ Rp {adv/1e9:.1f}B/hari.")

    # --- SUPPORTING EVIDENCE ---
    rsi = ind.get("rsi14")
    if rsi is not None:
        if score > 0 and rsi < 35:
            reasons.append(f"RSI {rsi} oversold mendukung Buy.")
        elif score < 0 and rsi > 65:
            reasons.append(f"RSI {rsi} overbought mendukung Sell.")
        else:
            reasons.append(f"RSI {rsi} ({'>50' if rsi > 50 else '<50'}).")

    if ind.get("macd_bias"):
        reasons.append(f"MACD {ind['macd_bias']} (hist {ind.get('macd_hist')}).")

    if ind.get("ma200_distance_pct") is not None:
        d = ind["ma200_distance_pct"]
        reasons.append(f"vs MA200: {d}% — {'di atas tren' if d > 0 else 'di bawah tren'}.")

    if ind.get("volume_ratio_20d"):
        v = ind["volume_ratio_20d"]
        if v >= 1.5:
            reasons.append(f"Volume {v}× rata-rata 20D — thrust kuat.")
        elif v < 0.7:
            reasons.append(f"Volume {v}× rata-rata 20D — kering, butuh konfirmasi.")

    if bandar.get("phase"):
        reasons.append(f"Bandar fase {bandar['phase']} (score {bandar.get('score')}, estimasi).")

    # --- POSITION SIZE RECOMMENDATION ---
    position = None
    if levels and adv:
        risk_idr = account_size_idr * 0.01  # 1% risk
        risk_per_share = abs(last_close - levels["stop_loss"])
        shares = int(risk_idr / risk_per_share) if risk_per_share > 0 else 0
        notional = shares * last_close
        # Cap by liquidity
        max_notional_by_adv = adv * MAX_POSITION_PCT_OF_ADV / 100
        if notional > max_notional_by_adv:
            shares_capped = int(max_notional_by_adv / last_close)
            position = {
                "shares": shares_capped,
                "notional_idr": int(shares_capped * last_close),
                "risk_idr": int(shares_capped * risk_per_share),
                "capped_by": "liquidity (5% ADV)",
            }
            reasons.append(
                f"Sizing di-cap likuiditas: {shares_capped:,} lbr (5% ADV) bukan {shares:,} lbr risk-based."
            )
        else:
            position = {
                "shares": shares,
                "notional_idr": int(notional),
                "risk_idr": int(risk_idr),
                "capped_by": "risk (1% account)",
            }

    qualified = len(blockers) == 0 and triggers is not None
    return {
        "qualified": qualified,
        "score_setup": round(abs(score) * 100, 0),
        "reasons": reasons,
        "blockers": blockers,
        "position": position,
    }
