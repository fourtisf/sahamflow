"""Walk-forward track record per ticker per setup.

Pertanyaan smart-money: "Setup yang aktif sekarang, historis berapa kali jalan?"
Kami replay sinyal dengan data CAUSAL ONLY (window[:i+1]), simulasi entry di bar
berikutnya, exit di SL/TP/time-stop. Hasil ter-agregasi by (signal_label, bandar
phase) supaya user lihat track record SETUP YANG SAMA — bukan rata-rata semua.

Dikenakan IDX cost 0.6% round-trip. Hasil di-cache di Redis 1 hari.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.services import bandar_detector, technical_analysis
from app.services.data_sync import load_ohlcv_df

COST_RT = 0.006  # fee + tax + slippage round-trip
MAX_HOLD = 10


def _simulate(future: pd.DataFrame, entry: float, atr: float, bias: str) -> float:
    sl_dist = 2 * atr
    tp_dist = 6 * atr
    if bias == "long":
        sl, tp = entry - sl_dist, entry + tp_dist
        for _, row in future.iterrows():
            if row["low"] <= sl:
                return -sl_dist / entry - COST_RT
            if row["high"] >= tp:
                return tp_dist / entry - COST_RT
        return float(future["close"].iloc[-1]) / entry - 1 - COST_RT
    else:
        sl, tp = entry + sl_dist, entry - tp_dist
        for _, row in future.iterrows():
            if row["high"] >= sl:
                return -sl_dist / entry - COST_RT
            if row["low"] <= tp:
                return tp_dist / entry - COST_RT
        return 1 - float(future["close"].iloc[-1]) / entry - COST_RT


def compute_track_record(db: Session, ticker: str, lookback_days: int = 1000) -> dict | None:
    df = load_ohlcv_df(db, ticker, days=lookback_days)
    if df.empty or len(df) < 80:
        return None

    trades: list[dict] = []
    for i in range(60, len(df) - 1):
        window = df.iloc[: i + 1]
        score, _ = technical_analysis.composite_score(window)
        label = technical_analysis.signal_label(score)
        if label == "Hold":
            continue
        bias = "long" if score >= 0.2 else "short"

        breakdown = technical_analysis.indicator_breakdown(window)
        atr = breakdown.get("atr14")
        if not atr:
            continue
        foreign_5d = (
            int(window["foreign_net"].dropna().tail(5).sum())
            if window["foreign_net"].notna().any()
            else None
        )
        bandar = bandar_detector.detect(window, foreign_5d)

        entry = float(window["close"].iloc[-1])
        future = df.iloc[i + 1 : i + 1 + MAX_HOLD]
        if future.empty:
            continue
        ret = _simulate(future, entry, atr, bias)
        trades.append({"label": label, "phase": bandar["phase"], "ret": ret, "win": ret > 0})

    if not trades:
        return None

    def _agg(rows: list[dict]) -> dict:
        n = len(rows)
        wins = sum(1 for r in rows if r["win"])
        win_rets = [r["ret"] for r in rows if r["win"]]
        loss_rets = [r["ret"] for r in rows if not r["win"]]
        avg_win = sum(win_rets) / len(win_rets) * 100 if win_rets else 0.0
        avg_loss = sum(loss_rets) / len(loss_rets) * 100 if loss_rets else 0.0
        exp = sum(r["ret"] for r in rows) / n * 100
        gw = sum(win_rets)
        gl = abs(sum(loss_rets)) or 1e-9
        return {
            "n": n,
            "hit_rate_pct": round(wins / n * 100, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "expectancy_pct": round(exp, 2),
            "profit_factor": round(gw / gl, 2),
        }

    by_setup: dict[str, list[dict]] = {}
    for t in trades:
        by_setup.setdefault(f"{t['label']} | {t['phase']}", []).append(t)

    return {
        "overall": _agg(trades),
        "by_setup": {k: _agg(v) for k, v in by_setup.items() if len(v) >= 3},
        "sample_years_approx": round(len(df) / 252, 1),
    }


def cached_track_record(db: Session, ticker: str) -> dict | None:
    key = f"track_record:{ticker.upper()}"
    try:
        r = get_redis()
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        r = None

    payload = compute_track_record(db, ticker.upper())
    if payload and r is not None:
        try:
            r.setex(key, 86400, json.dumps(payload))
        except Exception:
            pass
    return payload


def match_current_setup(track: dict | None, signal_label: str, bandar_phase: str) -> dict | None:
    """Pick the historical row matching the currently-active setup, with fallback."""
    if not track:
        return None
    key = f"{signal_label} | {bandar_phase}"
    if key in (track.get("by_setup") or {}):
        return {"setup": key, **track["by_setup"][key]}
    # fallback: same label, any phase
    for k, v in (track.get("by_setup") or {}).items():
        if k.startswith(signal_label + " |"):
            return {"setup": k + " (label match)", **v}
    return {"setup": "overall (no specific match)", **track.get("overall", {})}
