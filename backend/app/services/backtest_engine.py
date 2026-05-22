"""Backtest engine (Tahap 6).

Simulates the composite strategy (entry when bandar > 80 + AI > 75% + foreign net
buy, where data exists) over historical OHLCV. Computes the metrics shown in the
Backtest panel: total return, win rate, Sharpe, max DD, profit factor, expectancy,
plus an equity curve.

Operates purely on data passed in; if there are no qualifying trades it returns
zeroed metrics rather than fabricating a track record.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    # Annualize assuming the avg hold is a few days (~50 trades/yr scale).
    return round((mean / sd) * math.sqrt(50), 2)


def run(
    ohlcv: pd.DataFrame,
    entry_signal: pd.Series,
    sl_pct: float = 0.06,
    tp_pct: float = 0.18,
    max_hold: int = 10,
    cost_pct: float = 0.004,
    slippage_pct: float = 0.002,
) -> dict:
    """ohlcv indexed by date with a 'close' column; entry_signal: bool per row.

    On each entry-signal bar, enter at next close and exit at TP, SL, or max_hold.

    Honest costs: every round-trip is charged `cost_pct` (IDX broker fees + 0.1%
    sell tax + levy, default ~0.4%) plus `slippage_pct` (default ~0.2% round-trip).
    This is what separates a real backtest from a fantasy equity curve.
    """
    round_trip_cost = cost_pct + slippage_pct
    close = ohlcv["close"].reset_index(drop=True)
    signals = entry_signal.reset_index(drop=True)
    dates = list(ohlcv.index)

    trades: list[float] = []
    equity = [100.0]
    equity_dates: list[date] = [dates[0]] if dates else []
    i = 0
    n = len(close)
    while i < n - 1:
        if bool(signals.iloc[i]):
            entry = close.iloc[i + 1] if i + 1 < n else close.iloc[i]
            sl = entry * (1 - sl_pct)
            tp = entry * (1 + tp_pct)
            ret = 0.0
            exit_i = min(i + 1 + max_hold, n - 1)
            for j in range(i + 1, min(i + 1 + max_hold, n)):
                if close.iloc[j] <= sl:
                    ret = -sl_pct
                    exit_i = j
                    break
                if close.iloc[j] >= tp:
                    ret = tp_pct
                    exit_i = j
                    break
            else:
                ret = close.iloc[exit_i] / entry - 1
            ret -= round_trip_cost  # charge fees + slippage on every trade
            trades.append(ret)
            equity.append(equity[-1] * (1 + ret))
            equity_dates.append(dates[exit_i])
            i = exit_i + 1
        else:
            i += 1

    return _metrics(trades, equity, equity_dates)


def _metrics(trades: list[float], equity: list[float], equity_dates: list) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "sharpe": 0.0,
            "max_dd_pct": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy_pct": 0.0,
            "equity_curve": [{"date": str(d), "value": round(v, 2)} for d, v in zip(equity_dates, equity)],
        }

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, v / peak - 1)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "total_trades": len(trades),
        "total_return_pct": round((equity[-1] / equity[0] - 1) * 100, 1),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "sharpe": _sharpe(trades),
        "max_dd_pct": round(max_dd * 100, 1),
        "avg_win_pct": round((sum(wins) / len(wins)) * 100, 1) if wins else 0.0,
        "avg_loss_pct": round((sum(losses) / len(losses)) * 100, 1) if losses else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else 0.0,
        "expectancy_pct": round(sum(trades) / len(trades) * 100, 2),
        "equity_curve": [
            {"date": str(d), "value": round(v, 2)} for d, v in zip(equity_dates, equity)
        ],
    }
