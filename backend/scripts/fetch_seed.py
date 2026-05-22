"""Tahap 0 deliverable: pull 30d OHLCV for the 10 seed stocks into the database.

Usage (from backend/):
    python -m scripts.fetch_seed            # seed stocks + ohlcv + regime + signals
    python -m scripts.fetch_seed --check    # validate yfinance only, no DB writes

Run `alembic upgrade head` first so the tables exist.
"""

from __future__ import annotations

import sys

from app.core.config import SEED_TICKERS
from app.data_sources import yahoo_finance as yf


def check_only() -> int:
    """Validate that yfinance still returns IDX data — no DB needed."""
    ok = 0
    for t in SEED_TICKERS:
        df = yf.fetch_ohlcv(t, period="1mo")
        rows = len(df)
        last = df["close"].iloc[-1] if rows else None
        status = "OK " if rows else "EMPTY"
        print(f"  [{status}] {t:<5} rows={rows:<3} last_close={last}")
        if rows:
            ok += 1
    print(f"\nyfinance validation: {ok}/{len(SEED_TICKERS)} tickers returned data.")
    return 0 if ok else 1


def run() -> int:
    from app.services import data_sync

    print("Seeding stock metadata...")
    print(f"  seeded {data_sync.seed_stocks()} stocks")

    print("Syncing 30d OHLCV...")
    summary = data_sync.sync_ohlcv(period="1mo")
    for t, n in summary.items():
        print(f"  {t:<5} {n} rows")

    print("Computing regime...")
    regime = data_sync.compute_regime()
    print(f"  {regime['regime']} (conf {regime['confidence']}%, score {regime['raw_score']})")

    print("Generating signals...")
    signals = data_sync.generate_signals()
    for t, s in sorted(signals.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t:<5} composite={s}")

    return 0


if __name__ == "__main__":
    sys.exit(check_only() if "--check" in sys.argv else run())
