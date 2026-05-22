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
