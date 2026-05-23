"""IDX foreign flow scraper — best-effort EOD dari idx.co.id.

Endpoint resmi IDX: /primary/StockData/GetSecuritiesStock untuk daily summary.
Format JSON; berisi foreign buy/sell per ticker.

CATATAN JUJUR:
- IDX kadang ubah endpoint/format tanpa pemberitahuan → scraper bisa break.
- Untuk akurasi presisi (broker code per ticker), TETAP butuh feed berbayar
  (RTI Business / Stockbit Pro). Module ini menutup gap "n/a" sebagian saja.
- Return [] kalau gagal, JANGAN mengarang angka.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx

log = logging.getLogger("sahamflow.idx_scraper")

IDX_URL = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Sahamflow research bot)",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.idx.co.id/en/market-data/stocks-data/stock-list/",
}


def fetch_foreign_flow(target_date: date) -> list[dict]:
    """Try to fetch daily summary; populate foreign_buy/sell/net per ticker.

    Returns list of {ticker, date, foreign_buy, foreign_sell, foreign_net}.
    Returns [] silently if IDX endpoint is unavailable or format changed.
    """
    params = {
        "code": "",
        "start": 0,
        "length": 9999,
        "TradingDate": target_date.strftime("%Y%m%d"),
        "language": "en-us",
    }
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            r = client.get(IDX_URL, params=params)
            if r.status_code != 200:
                log.warning("IDX %s for %s", r.status_code, target_date)
                return []
            data = r.json()
    except Exception as e:
        log.warning("IDX scrape failed: %s", e)
        return []

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    out: list[dict] = []
    for it in items:
        code = (it.get("StockCode") or it.get("Code") or "").upper()
        if not code or len(code) > 6:
            continue
        try:
            f_buy = int(it.get("ForeignBuy") or 0)
            f_sell = int(it.get("ForeignSell") or 0)
        except (TypeError, ValueError):
            continue
        out.append({
            "ticker": code,
            "date": target_date,
            "foreign_buy": f_buy,
            "foreign_sell": f_sell,
            "foreign_net": f_buy - f_sell,
        })
    log.info("IDX scrape: %d tickers for %s", len(out), target_date)
    return out
