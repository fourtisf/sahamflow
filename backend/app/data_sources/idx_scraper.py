"""IDX foreign flow scraper — best-effort EOD dari idx.co.id.

Approach v2: pakai curl_cffi dengan browser TLS impersonation untuk menembus
Cloudflare. Plain httpx dapat 403 Forbidden karena IDX cek fingerprint TLS.

Flow:
1. Warm-up session: kunjungi homepage IDX → dapat cookie & session
2. Call endpoint resmi /primary/StockData/GetSecuritiesStock
3. Fallback ke endpoint /umbraco/surface/... kalau primary gagal

CATATAN JUJUR:
- IDX kadang ubah endpoint/format tanpa pemberitahuan → scraper bisa break.
- Untuk akurasi presisi (broker code per ticker per detik), TETAP butuh feed
  berbayar (RTI Business / Stockbit Pro).
- Return [] kalau semua gagal — JANGAN mengarang angka.
"""

from __future__ import annotations

import logging
from datetime import date

log = logging.getLogger("sahamflow.idx_scraper")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.idx.co.id/en/market-data/stocks-data/stock-list/",
    "Origin": "https://www.idx.co.id",
}

ENDPOINTS = [
    "https://www.idx.co.id/primary/StockData/GetSecuritiesStock",
    "https://www.idx.co.id/umbraco/surface/StockData/GetSecuritiesStock",
]


def _try_curl_cffi(url: str, params: dict) -> dict | None:
    """Coba pakai curl_cffi (browser TLS impersonation) — bypass Cloudflare."""
    try:
        from curl_cffi import requests as cf
    except ImportError:
        log.warning("curl_cffi tidak terpasang, skip")
        return None

    try:
        with cf.Session(impersonate="chrome120") as session:
            # Warm-up: kunjungi homepage dulu agar dapat cookie
            session.get(
                "https://www.idx.co.id/en/",
                headers={"User-Agent": CHROME_UA, "Accept-Language": "en-US,en;q=0.9"},
                timeout=15,
            )
            r = session.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                log.warning("curl_cffi %s -> %s", url, r.status_code)
                return None
            return r.json()
    except Exception as e:
        log.warning("curl_cffi %s failed: %s", url, e)
        return None


def _try_httpx(url: str, params: dict) -> dict | None:
    """Fallback ke httpx polos (kalau curl_cffi tidak ada)."""
    try:
        import httpx
        with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            client.get("https://www.idx.co.id/en/", timeout=15)  # warm
            r = client.get(url, params=params)
            if r.status_code != 200:
                log.warning("httpx %s -> %s", url, r.status_code)
                return None
            return r.json()
    except Exception as e:
        log.warning("httpx %s failed: %s", url, e)
        return None


def fetch_foreign_flow(target_date: date) -> list[dict]:
    """Try multiple endpoints/methods. Returns list of per-ticker foreign flow,
    or [] if all attempts fail."""
    params = {
        "code": "",
        "start": 0,
        "length": 9999,
        "TradingDate": target_date.strftime("%Y%m%d"),
        "language": "en-us",
    }

    data = None
    for url in ENDPOINTS:
        data = _try_curl_cffi(url, params)
        if data:
            log.info("IDX scrape via curl_cffi @ %s OK", url)
            break
        data = _try_httpx(url, params)
        if data:
            log.info("IDX scrape via httpx @ %s OK", url)
            break

    if not data:
        log.warning("IDX scrape semua endpoint gagal untuk %s", target_date)
        return []

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        log.warning("IDX response format tidak dikenali")
        return []

    out: list[dict] = []
    for it in items:
        code = (it.get("StockCode") or it.get("Code") or "").upper()
        if not code or len(code) > 6:
            continue
        try:
            f_buy = int(it.get("ForeignBuy") or it.get("forBuy") or 0)
            f_sell = int(it.get("ForeignSell") or it.get("forSell") or 0)
        except (TypeError, ValueError):
            continue
        out.append({
            "ticker": code,
            "date": target_date,
            "foreign_buy": f_buy,
            "foreign_sell": f_sell,
            "foreign_net": f_buy - f_sell,
        })
    log.info("IDX scrape: %d tickers parsed for %s", len(out), target_date)
    return out
