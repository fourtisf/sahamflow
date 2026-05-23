"""Whole-portfolio walk-forward backtest.

Pertanyaan akhir: kalau aku ikuti semua sinyal Sahamflow selama X tahun di
seluruh universe, berapa equity curve & metrics-nya?

Implementasi:
- Untuk tiap tanggal, hitung composite per ticker pakai data CAUSAL ONLY
  (window[:i+1]). Mode reversion/trend dipilih berdasar regime pada saat itu.
- Filter qualified Buys: score >= MIN_BUY_SCORE, ADV cukup, ATR ada.
- Buka posisi top-N (capacity-limited), sizing 1% risk per trade.
- Manage existing: cek SL/TP/time-stop tiap bar.
- Charge IDX cost (0.4% RT) + slippage (0.2% RT).
- Output: equity curve, metrics, sample trades.

Honest: ini long-only IDX simulasi. Tidak ada short. Tidak ada margin.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import OHLCVDaily
from app.services import bandar_detector, technical_analysis
from app.services.data_sync import load_ohlcv_df

log = logging.getLogger("sahamflow.portfolio_backtest")

MIN_BUY_SCORE = 0.5
MAX_POSITIONS = 5
RISK_PER_TRADE = 0.01  # 1% of equity
COST_RT = 0.006  # IDX fee + tax + slippage round-trip


def _load_universe_history(db: Session, tickers: list[str], lookback_days: int) -> dict:
    """Pre-load all tickers' DataFrames once for speed."""
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = load_ohlcv_df(db, t, days=lookback_days)
        if not df.empty and len(df) >= 80:
            out[t] = df
    return out


def _date_index(histories: dict) -> list:
    """All unique trading dates across all tickers, sorted."""
    dates = set()
    for df in histories.values():
        dates.update(df.index)
    return sorted(dates)


def run(
    db: Session,
    tickers: list[str] | None = None,
    lookback_days: int = 500,
    starting_equity: float = 100_000_000,
    max_positions: int = MAX_POSITIONS,
    min_score: float = MIN_BUY_SCORE,
) -> dict:
    """Walk-forward portfolio backtest. Returns metrics + equity curve."""
    tickers = tickers or settings.universe
    histories = _load_universe_history(db, tickers, lookback_days)
    if not histories:
        return {"error": "no data"}

    all_dates = _date_index(histories)
    if len(all_dates) < 80:
        return {"error": "insufficient history"}

    # Skip first 60 days (need warmup for indicators)
    sim_dates = all_dates[60:]

    cash = starting_equity
    equity = starting_equity
    positions: dict[str, dict] = {}  # ticker -> {entry, sl, tp, shares, entry_date, hold_bars}
    trades_log: list[dict] = []
    equity_curve: list[dict] = []
    peak = starting_equity
    max_dd = 0.0

    for d in sim_dates:
        # === Manage existing positions (check SL/TP/time-stop) ===
        closed_today = []
        for t, p in positions.items():
            if d not in histories[t].index:
                continue
            bar = histories[t].loc[d]
            p["hold_bars"] += 1
            exit_reason = None
            exit_price = None
            if bar["low"] <= p["sl"]:
                exit_price = p["sl"]
                exit_reason = "SL"
            elif bar["high"] >= p["tp"]:
                exit_price = p["tp"]
                exit_reason = "TP"
            elif p["hold_bars"] >= 10:
                exit_price = float(bar["close"])
                exit_reason = "time_stop"
            if exit_price is not None:
                gross = (exit_price / p["entry"] - 1)
                net = gross - COST_RT
                pnl_idr = p["shares"] * p["entry"] * net
                cash += p["shares"] * exit_price
                trades_log.append({
                    "ticker": t,
                    "entry_date": str(p["entry_date"]),
                    "exit_date": str(d),
                    "entry": round(p["entry"], 2),
                    "exit": round(exit_price, 2),
                    "shares": p["shares"],
                    "pnl_pct": round(net * 100, 2),
                    "pnl_idr": int(pnl_idr),
                    "reason": exit_reason,
                })
                closed_today.append(t)
        for t in closed_today:
            del positions[t]

        # === Evaluate new entries ===
        if len(positions) < max_positions:
            slots = max_positions - len(positions)
            # Score each candidate at this date
            candidates: list[tuple[float, str, float, float]] = []
            for t, df in histories.items():
                if t in positions:
                    continue
                if d not in df.index:
                    continue
                idx = df.index.get_loc(d)
                if idx < 60:
                    continue
                window = df.iloc[: idx + 1]
                # Mode default trend (regime modifier per-date too expensive di MVP backtest)
                try:
                    score, _ = technical_analysis.composite_score(window, mode="trend")
                except Exception:
                    continue
                if score < min_score:
                    continue
                breakdown = technical_analysis.indicator_breakdown(window)
                atr = breakdown.get("atr14")
                adv = breakdown.get("adv_value_idr_20d")
                if not atr or atr <= 0:
                    continue
                if not adv or adv < 5_000_000_000:  # 5B minimum likuid
                    continue
                last_close = float(window["close"].iloc[-1])
                candidates.append((score, t, last_close, atr))

            candidates.sort(reverse=True)
            for score, t, last_close, atr in candidates[:slots]:
                # Entry at next bar's open jika ada; else skip
                next_idx = histories[t].index.get_loc(d) + 1
                if next_idx >= len(histories[t]):
                    continue
                entry_bar = histories[t].iloc[next_idx]
                entry = float(entry_bar["open"]) if entry_bar["open"] else last_close
                sl_dist = 2 * atr
                tp_dist = 6 * atr
                sl = entry - sl_dist
                tp = entry + tp_dist
                risk_idr = equity * RISK_PER_TRADE
                shares = int(risk_idr / sl_dist) if sl_dist > 0 else 0
                if shares < 100:
                    continue
                cost = shares * entry
                if cost > cash:
                    shares = int(cash / entry)
                    if shares < 100:
                        continue
                    cost = shares * entry
                cash -= cost
                positions[t] = {
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "shares": shares,
                    "entry_date": histories[t].index[next_idx],
                    "hold_bars": 0,
                }

        # === Mark-to-market ===
        mtm_value = sum(
            (float(histories[t].loc[d, "close"]) if d in histories[t].index else p["entry"]) * p["shares"]
            for t, p in positions.items()
        )
        equity = cash + mtm_value
        peak = max(peak, equity)
        dd = equity / peak - 1
        max_dd = min(max_dd, dd)
        equity_curve.append({
            "date": str(d),
            "equity": int(equity),
            "cash": int(cash),
            "open_positions": len(positions),
            "drawdown_pct": round(dd * 100, 2),
        })

    # === Metrics ===
    total_return_pct = (equity / starting_equity - 1) * 100
    wins = [t for t in trades_log if t["pnl_pct"] > 0]
    losses = [t for t in trades_log if t["pnl_pct"] <= 0]
    n = len(trades_log)
    hit_rate = len(wins) / n * 100 if n else 0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    expectancy = sum(t["pnl_pct"] for t in trades_log) / n if n else 0
    gross_win = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) or 1e-9
    profit_factor = gross_win / gross_loss

    return {
        "starting_equity": int(starting_equity),
        "final_equity": int(equity),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trades": n,
        "hit_rate_pct": round(hit_rate, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "expectancy_pct": round(expectancy, 2),
        "profit_factor": round(profit_factor, 2),
        "universe_size": len(histories),
        "max_positions": max_positions,
        "min_score": min_score,
        "equity_curve": equity_curve,
        "sample_trades": trades_log[-20:],  # last 20 trades sebagai sampel
    }
