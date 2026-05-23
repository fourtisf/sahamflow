"""yfinance data source for IDX stocks.

IDX tickers use the ".JK" Yahoo suffix (e.g. BBCA -> BBCA.JK). yfinance returns
EOD OHLCV, delayed ~15 min. This is the MVP source — see docs/DATA_SOURCES.md.

Yahoo does NOT provide foreign buy/sell flow, so those columns stay None here and
are filled by the IDX scraper in a later phase.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


def to_yahoo_symbol(ticker: str) -> str:
    """BBCA -> BBCA.JK. Idempotent if the suffix is already present."""
    ticker = ticker.upper().strip()
    return ticker if ticker.endswith(".JK") else f"{ticker}.JK"


def from_yahoo_symbol(symbol: str) -> str:
    return symbol.upper().replace(".JK", "").strip()


def fetch_ohlcv(ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV for a single ticker.

    Returns a DataFrame indexed by date with columns:
    open, high, low, close, volume, value (close*volume approximation).
    Empty DataFrame if Yahoo has no data for the symbol.
    """
    symbol = to_yahoo_symbol(ticker)
    raw = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()

    # yfinance may return a MultiIndex column frame for a single ticker.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "close", "volume"]].copy()

    df = df.dropna(subset=["close"])
    df["value"] = (df["close"] * df["volume"]).round().astype("Int64")
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    return df


def fetch_ohlcv_records(ticker: str, period: str = "1mo") -> list[dict]:
    """Fetch and flatten to a list of dicts ready for DB upsert."""
    df = fetch_ohlcv(ticker, period=period)
    records: list[dict] = []
    for idx, row in df.iterrows():
        d: date = idx if isinstance(idx, date) else idx.date()
        records.append(
            {
                "ticker": ticker.upper(),
                "date": d,
                "open": float(row["open"]) if pd.notna(row["open"]) else None,
                "high": float(row["high"]) if pd.notna(row["high"]) else None,
                "low": float(row["low"]) if pd.notna(row["low"]) else None,
                "close": float(row["close"]) if pd.notna(row["close"]) else None,
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
                "value": int(row["value"]) if pd.notna(row["value"]) else None,
            }
        )
    return records


def fetch_quote(symbol: str) -> dict | None:
    """Latest close + change vs previous close for an index/FX symbol.

    symbol is a raw Yahoo symbol (e.g. '^JKSE', 'IDR=X') — no .JK mangling.
    Returns None if Yahoo has no data. Delayed (~15 min), not real-time tick.
    """
    raw = yf.download(
        symbol, period="5d", interval="1d", auto_adjust=False, progress=False, threads=False
    )
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    closes = raw["Close"].dropna()
    if closes.empty:
        return None
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
    change = last - prev
    pct = (change / prev * 100) if prev else 0.0
    return {"value": round(last, 2), "change": round(change, 2), "change_pct": round(pct, 2)}


def fetch_history(symbol: str, period: str = "1mo") -> list[dict]:
    """Raw close history for an index/FX symbol (no .JK mangling).

    Returns [{"date": "YYYY-MM-DD", "close": float}], oldest-to-newest. [] if none.
    """
    raw = yf.download(
        symbol, period=period, interval="1d", auto_adjust=False, progress=False, threads=False
    )
    if raw is None or raw.empty:
        return []
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    closes = raw["Close"].dropna()
    out = []
    for idx, val in closes.items():
        d = idx if isinstance(idx, date) else idx.date()
        out.append({"date": str(d), "close": round(float(val), 2)})
    return out


def fetch_ohlc_history(symbol: str, period: str = "3mo") -> list[dict]:
    """OHLC history for an index/FX symbol. Needed for gap/streak/reversal detection."""
    raw = yf.download(
        symbol, period=period, interval="1d", auto_adjust=False, progress=False, threads=False
    )
    if raw is None or raw.empty:
        return []
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw[["Open", "High", "Low", "Close"]].dropna()
    out = []
    for idx, row in df.iterrows():
        d = idx if isinstance(idx, date) else idx.date()
        out.append({
            "date": str(d),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        })
    return out


def usdidr_change_pct_30d() -> float | None:
    """USD/IDR % change over the trailing ~30d. Positive = rupiah weakening."""
    hist = fetch_history("IDR=X", period="2mo")
    if len(hist) < 2:
        return None
    recent = hist[-22:]  # ~1 trading month
    first, last = recent[0]["close"], recent[-1]["close"]
    if not first:
        return None
    return round((last / first - 1) * 100, 2)


def fetch_info(ticker: str) -> dict:
    """Fetch metadata (name, sector, market cap) for stocks table seeding."""
    symbol = to_yahoo_symbol(ticker)
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        info = {}
    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "market_cap": info.get("marketCap"),
    }
