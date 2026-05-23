"""Per-stock smart-money intelligence: combines TA, ATR levels, regime context.

Replaces the bare composite score with a structured payload a trader actually
uses to make decisions. No fabricated data — every field is derived from the
ticker's OHLCV + the current regime.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RegimeHistory
from app.services import (
    bandar_detector,
    foreign_flow_analyzer,
    reversal_scanner,
    technical_analysis,
    track_record,
    triggers,
)
from app.services.data_sync import load_ohlcv_df


def _bias_from_score(score: float) -> str:
    if score >= 0.2:
        return "long"
    if score <= -0.2:
        # IDX retail tidak bisa short. Map ke 'avoid' (jangan beli), bukan short.
        return "avoid" if settings.MARKET_MODE == "long_only" else "short"
    return "neutral"


def _long_only_action(signal_label: str) -> str:
    """Label aksi untuk long-only market (IDX retail).

    Strong Buy / Buy = BELI sinyal aktif
    Hold = TUNGGU / WATCH
    Sell / Strong Sell = AVOID (jangan beli) atau EXIT (kalau sudah hold)
    """
    mapping = {
        "Strong Buy": "BUY",
        "Buy": "BUY",
        "Hold": "WATCH",
        "Sell": "AVOID / EXIT",
        "Strong Sell": "AVOID / EXIT",
    }
    return mapping.get(signal_label, "WATCH")


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
    """Return the full smart-money intel payload for a ticker, or None if no data.

    Jika ticker belum ada di DB (di luar universe pre-sync), coba lazy-fetch dari
    yfinance dan simpan supaya panggilan berikutnya cepat.
    """
    df = load_ohlcv_df(db, ticker)
    if df.empty or len(df) < 20:
        try:
            from app.services.data_sync import sync_ohlcv

            sync_ohlcv([ticker], period="1y")
            df = load_ohlcv_df(db, ticker)
        except Exception:
            return None
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
    long_only = settings.MARKET_MODE == "long_only"

    # Hanya bangun execution_levels untuk LONG. Avoid/short tidak ada entry di IDX.
    if bias == "long":
        levels = technical_analysis.execution_levels(
            last_close,
            breakdown.get("atr14"),
            "long",
            swing_low=breakdown.get("swing_low_60d"),
            swing_high=breakdown.get("swing_high_60d"),
        )
    else:
        levels = None  # AVOID/WATCH — tidak ada entry di IDX long-only

    regime_row = db.execute(
        select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
    ).scalar_one_or_none()
    regime_name = regime_row.regime if regime_row else None
    conviction = _conviction(score, regime_name, bandar.get("phase"))

    # 60-day price history for the inline chart in SmartAnalysis.
    history_df = df.tail(60)
    history = [
        {"date": str(d), "close": float(c)}
        for d, c in zip(history_df.index, history_df["close"])
        if c is not None
    ]

    # Action label untuk long-only — yang USER ACT bedasarkan ini
    action = _long_only_action(label) if long_only else label

    # Wait conditions: kalau AVOID, kasih syarat balik bullish (bukan setup short)
    wait_conditions: list[str] | None = None
    avoid_reasons: list[str] | None = None
    if bias == "avoid":
        sw_high = breakdown.get("swing_high_60d")
        ma20 = breakdown.get("ma20")
        wait_conditions = [
            f"Tunggu close > MA20 ({ma20})" if ma20 else "Tunggu close di atas MA20.",
            "Tunggu RSI 14 menembus 45 (momentum kembali).",
            f"Tunggu break swing high {sw_high} dengan volume ≥ 1.5×." if sw_high else "Tunggu breakout dengan volume thrust.",
            "Kalau sudah hold: pertimbangkan EXIT di rebound minor ke MA20 / swing high.",
        ]

        # Alasan SPESIFIK kenapa AVOID — tampilkan drivers dari indikator.
        avoid_reasons = []
        rsi = breakdown.get("rsi14")
        if rsi is not None:
            if rsi < 40:
                avoid_reasons.append(f"RSI 14 = {rsi} (oversold tapi belum signature reversal — tunggu RSI > 45)")
            else:
                avoid_reasons.append(f"RSI 14 = {rsi} (di bawah 50, momentum lemah)")
        if breakdown.get("macd_bias") == "bearish":
            avoid_reasons.append(f"MACD bearish (hist {breakdown.get('macd_hist')})")
        ma200_d = breakdown.get("ma200_distance_pct")
        if ma200_d is not None and ma200_d < 0:
            avoid_reasons.append(f"Harga {ma200_d}% vs MA200 — di bawah tren panjang")
        vol = breakdown.get("volume_ratio_20d")
        if vol is not None and vol < 1.0:
            avoid_reasons.append(f"Volume {vol}× rata-rata 20D — kering, tidak ada minat beli")
        if bandar.get("phase") == "Markdown":
            avoid_reasons.append(f"Bandar fase Markdown (score {bandar.get('score')}) — smart money distribusi")
        rp = breakdown.get("range_position_pct")
        if rp is not None:
            avoid_reasons.append(f"Posisi {rp}% range 60D (low {breakdown.get('swing_low_60d')}, high {breakdown.get('swing_high_60d')})")
        if not conviction.get("regime_aligned"):
            avoid_reasons.append(f"Melawan regime {regime_name} — counter-trend, conviction model rendah")

    intel = {
        "ticker": ticker,
        "last_close": last_close,
        "composite_score": round(score, 3),
        "signal": label,
        "action": action,  # BUY / WATCH / AVOID / EXIT — long-only friendly
        "bias": bias,
        "market_mode": settings.MARKET_MODE,
        "indicators": breakdown,
        "bandar": bandar,
        "foreign_flow": ff,
        "levels": levels,
        "wait_conditions": wait_conditions,
        "avoid_reasons": avoid_reasons,
        "regime": {"name": regime_name, **conviction},
        "history": history,
    }
    # Execution discipline: trigger / invalidation / time stop.
    intel["triggers"] = triggers.derive_triggers(intel)
    # Track record of THIS setup historically (walk-forward, cached daily).
    track = track_record.cached_track_record(db, ticker)
    intel["track_record"] = track_record.match_current_setup(track, label, bandar.get("phase"))

    # === SMART-MONEY REVERSAL OVERLAY ===
    # Trend-following composite akan bilang "Sell" untuk saham oversold di bear
    # trend. Tapi saat regime modifier mendukung pembalikan DAN ada signature
    # reversal kuat, smart money justru AKUMULASI. Kami buat alternate setup
    # eksplisit supaya user tidak dipaksa Sell di bottom.
    intel["alternate_setup"] = _maybe_reversal_overlay(df, intel, breakdown, db, ticker)

    # Structural warning: composite Sell di support proven = setup buruk
    if score < -0.2:
        rp = breakdown.get("range_position_pct")
        if rp is not None and rp < 25:
            intel["structural_warning"] = (
                f"Composite menyarankan Sell, tapi harga berada di {rp}% range 60D "
                f"(dekat swing low {breakdown.get('swing_low_60d')}). Short di support "
                f"proven = high risk. Pertimbangkan Reversal Long overlay atau tunggu "
                f"breakdown jelas di bawah {breakdown.get('swing_low_60d')}."
            )
    return intel


def _maybe_reversal_overlay(df, intel, breakdown, db, ticker):
    """Jika kondisi mendukung Buy reversal, kembalikan overlay setup; else None.

    Triggers (longgar — supaya kasus ANTM tidak terlewat):
      A. Regime modifier = Potential Accumulation, ATAU
      B. RSI < 35 (oversold) DAN harga di bottom 25% range 60D (structural support).
    Plus salah satu: reversal_score >= 30 ATAU range_position < 15 (sangat dekat
    swing low).
    """
    regime_row = db.execute(
        select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
    ).scalar_one_or_none()
    regime_extra = regime_row.extra if regime_row else {}
    modifier = (regime_extra or {}).get("modifier") if isinstance(regime_extra, dict) else None

    rsi = breakdown.get("rsi14") or 50
    range_pos = breakdown.get("range_position_pct")
    at_structural_support = range_pos is not None and range_pos < 25

    regime_supports = modifier == "Potential Accumulation"
    oversold_at_support = rsi < 40 and at_structural_support

    if not (regime_supports or oversold_at_support):
        return None
    if rsi >= 45:  # tidak mungkin reversal kalau RSI sudah netral-bullish
        return None

    rev = reversal_scanner.scan_ticker(df)
    rev_score = rev["score"] if rev else 0
    rev_sigs = rev["signatures"] if rev else []

    # Pemicu tambahan: range position sangat rendah (di support) atau signature kuat
    if rev_score < 30 and (range_pos is None or range_pos >= 15):
        return None

    last = float(df["close"].iloc[-1])
    atr = breakdown.get("atr14") or 0
    if atr <= 0:
        return None
    levels = technical_analysis.execution_levels(
        last, atr, bias="long",
        swing_low=breakdown.get("swing_low_60d"),
        swing_high=breakdown.get("swing_high_60d"),
    )

    # Rationale yang spesifik konteks
    parts = []
    if regime_supports:
        parts.append(f"regime {modifier}")
    if at_structural_support:
        parts.append(f"harga {range_pos}% range 60D — dekat swing low {breakdown.get('swing_low_60d')}")
    if rsi < 35:
        parts.append(f"RSI {rsi} oversold")
    if rev_sigs:
        parts.append(f"signature: {', '.join(rev_sigs[:3])}")

    return {
        "bias": "long",
        "rationale": "REVERSAL LONG — " + " · ".join(parts) + ".",
        "reversal_score": rev_score,
        "signatures": rev_sigs,
        "range_position_pct": range_pos,
        "swing_low_60d": breakdown.get("swing_low_60d"),
        "swing_high_60d": breakdown.get("swing_high_60d"),
        "levels": levels,
        "rules": [
            f"Target struktural: gap fill / resistance proven {breakdown.get('swing_high_60d')}.",
            f"Setup batal jika close < {levels['stop_loss']} (2× ATR) atau menembus swing low.",
            "Setup ini override sinyal trend-following composite — jangan ambil Sell di support proven.",
            "Konfirmasi: green close + volume ≥ 1.2× rata-rata 20D (lebih longgar dari trend trade).",
            "Scaling: 1/3 saat green close konfirmasi, 1/3 saat RSI > 40, 1/3 di +1R. Trail di breakeven setelah +1R.",
        ],
    }
