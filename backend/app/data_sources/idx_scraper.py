"""IDX official data scraper — foreign flow (EOD).

STATUS: stub for Tahap 3. yfinance does not expose foreign buy/sell, so foreign
flow must come from idx.co.id/market-data (legal, EOD) or a paid feed.

This module is intentionally a typed placeholder so the foreign-flow analyzer and
sync pipeline can be wired now and swapped to a real implementation later. It must
NEVER fabricate numbers — callers treat an empty result as "no data".
See docs/DATA_SOURCES.md for the legality notes and the scraping plan.
"""

from __future__ import annotations

from datetime import date


def fetch_foreign_flow(target_date: date) -> list[dict]:
    """Return per-ticker foreign buy/sell/net for a trading date.

    Returns [] until a real IDX scraper / paid feed is connected. Each record:
    {"ticker": str, "date": date, "foreign_buy": int, "foreign_sell": int,
     "foreign_net": int}.
    """
    return []
