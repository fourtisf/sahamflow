"""Technical indicators + composite score (Tahap 2).

Indicators are implemented directly on pandas to avoid the numpy/pandas-ta
version friction seen on Python 3.11+. Each indicator signal is normalized to
[-1, +1] so the weighted composite is comparable across stocks.

Inputs are a DataFrame with at least a 'close' column (and 'high'/'low'/'volume'
where the indicator needs them), oldest-to-newest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "rsi": 0.15,
    "macd": 0.15,
    "volume": 0.20,  # heaviest weight for IDX stocks (bandar-driven)
    "ma": 0.15,
    "stoch_rsi": 0.15,
    "psar": 0.10,
    "bb": 0.10,
}


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd_line, 9)
    return macd_line, signal, macd_line - signal


def stoch_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    r = rsi(close, period)
    lo = r.rolling(period).min()
    hi = r.rolling(period).max()
    return ((r - lo) / (hi - lo).replace(0, np.nan)).fillna(0.5)


def bollinger(close: pd.Series, period: int = 20, std: float = 2.0):
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std()
    return ma + std * sd, ma, ma - std * sd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR. Needs high/low/close. Used for volatility-aware sizing."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def parabolic_sar(df: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    sar = np.zeros(n)
    if n < 2:
        return pd.Series(sar, index=df.index)
    up = True
    af = step
    ep = high[0]
    sar[0] = low[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if up:
            if low[i] < sar[i]:
                up = False
                sar[i] = ep
                ep = low[i]
                af = step
            elif high[i] > ep:
                ep = high[i]
                af = min(af + step, max_step)
        else:
            if high[i] > sar[i]:
                up = True
                sar[i] = ep
                ep = high[i]
                af = step
            elif low[i] < ep:
                ep = low[i]
                af = min(af + step, max_step)
    return pd.Series(sar, index=df.index)


def _clip(x: float) -> float:
    return float(np.clip(x, -1.0, 1.0))


def rsi_signal(df: pd.DataFrame) -> float:
    r = rsi(df["close"]).iloc[-1]
    # Momentum-aligned: above 50 bullish. Taper above 80 to avoid chasing blow-offs.
    base = (r - 50) / 30
    if r > 80:
        base -= (r - 80) / 30
    return _clip(base)


def macd_signal(df: pd.DataFrame) -> float:
    _, _, hist = macd(df["close"])
    norm = hist.iloc[-1] / df["close"].iloc[-1]
    return _clip(norm * 100)


def volume_signal(df: pd.DataFrame) -> float:
    if "volume" not in df or df["volume"].tail(20).sum() == 0:
        return 0.0
    avg = df["volume"].rolling(20).mean().iloc[-1]
    if not avg:
        return 0.0
    ratio = df["volume"].iloc[-1] / avg
    direction = 1 if df["close"].iloc[-1] >= df["close"].iloc[-2] else -1
    return _clip(direction * (ratio - 1))


def ma_alignment(df: pd.DataFrame) -> float:
    c = df["close"]
    ma20, ma50, ma200 = (
        c.rolling(20).mean().iloc[-1],
        c.rolling(50).mean().iloc[-1],
        c.rolling(min(200, len(c))).mean().iloc[-1],
    )
    price = c.iloc[-1]
    score = 0.0
    for ma in (ma20, ma50, ma200):
        if pd.notna(ma):
            score += 1 / 3 if price > ma else -1 / 3
    return _clip(score)


def stoch_rsi_signal(df: pd.DataFrame) -> float:
    k = stoch_rsi(df["close"]).iloc[-1]
    # Momentum-aligned: high stoch RSI = strength.
    return _clip((k - 0.5) * 2)


def psar_signal(df: pd.DataFrame) -> float:
    if not {"high", "low"}.issubset(df.columns):
        return 0.0
    sar = parabolic_sar(df).iloc[-1]
    return 1.0 if df["close"].iloc[-1] > sar else -1.0


def bollinger_signal(df: pd.DataFrame) -> float:
    upper, mid, lower = bollinger(df["close"])
    price = df["close"].iloc[-1]
    u, m, lo = upper.iloc[-1], mid.iloc[-1], lower.iloc[-1]
    if pd.isna(u) or u == lo:
        return 0.0
    pct_b = (price - lo) / (u - lo)
    # Momentum-aligned: riding the upper band = strength.
    return _clip((pct_b - 0.5) * 2)


def composite_score(ohlcv: pd.DataFrame) -> tuple[float, dict[str, float]]:
    """Weighted composite of all indicator signals, in [-1, +1]."""
    ind = {
        "rsi": rsi_signal(ohlcv),
        "macd": macd_signal(ohlcv),
        "volume": volume_signal(ohlcv),
        "ma": ma_alignment(ohlcv),
        "stoch_rsi": stoch_rsi_signal(ohlcv),
        "psar": psar_signal(ohlcv),
        "bb": bollinger_signal(ohlcv),
    }
    score = sum(ind[k] * WEIGHTS[k] for k in WEIGHTS)
    return _clip(score), ind


def indicator_breakdown(df: pd.DataFrame) -> dict:
    """Human-readable indicator snapshot — the numbers a trader actually reads."""
    close = df["close"]
    last = float(close.iloc[-1])
    r = float(rsi(close).iloc[-1])
    macd_line, signal_line, hist = macd(close)
    k = float(stoch_rsi(close).iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200_window = min(200, len(close))
    ma200v = float(close.rolling(ma200_window).mean().iloc[-1]) if ma200_window else None
    vol = df["volume"] if "volume" in df else None
    vol_ratio = (
        float(vol.iloc[-1] / vol.rolling(20).mean().iloc[-1])
        if vol is not None and vol.rolling(20).mean().iloc[-1]
        else None
    )
    atr14 = float(atr(df).iloc[-1]) if {"high", "low"}.issubset(df.columns) else None
    return {
        "rsi14": round(r, 2),
        "macd_hist": round(float(hist.iloc[-1]), 4),
        "macd_bias": "bullish" if hist.iloc[-1] > 0 else "bearish",
        "stoch_rsi": round(k, 2),
        "ma20": round(ma20, 2) if ma20 else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma200": round(ma200v, 2) if ma200v else None,
        "ma200_distance_pct": round((last / ma200v - 1) * 100, 2) if ma200v else None,
        "volume_ratio_20d": round(vol_ratio, 2) if vol_ratio else None,
        "atr14": round(atr14, 2) if atr14 else None,
        "atr_pct": round(atr14 / last * 100, 2) if atr14 and last else None,
    }


def execution_levels(last_close: float, atr_value: float | None, bias: str) -> dict | None:
    """Volatility-aware entry/SL/TP using ATR, with R:R = 1:3.

    bias='long' / 'short'. Returns None if ATR unavailable.
    """
    if not atr_value or atr_value <= 0:
        return None
    sl_dist = 2 * atr_value
    tp_dist = 6 * atr_value
    if bias == "short":
        sl, tp = last_close + sl_dist, last_close - tp_dist
    else:
        sl, tp = last_close - sl_dist, last_close + tp_dist
    return {
        "entry": round(last_close, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "risk_pct": round(sl_dist / last_close * 100, 2),
        "reward_pct": round(tp_dist / last_close * 100, 2),
        "rr_ratio": 3.0,
    }


def signal_label(score: float) -> str:
    if score >= 0.5:
        return "Strong Buy"
    if score >= 0.2:
        return "Buy"
    if score > -0.2:
        return "Hold"
    if score > -0.5:
        return "Sell"
    return "Strong Sell"
