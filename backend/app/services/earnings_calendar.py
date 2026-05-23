"""Earnings calendar — hybrid yfinance auto-fetch + manual override.

Strategy:
1. Auto: yfinance `Ticker.calendar` di-pull mingguan untuk semua universe.
   Cache di file JSON (atomic write).
2. Manual: user bisa override via file di EARNINGS_CALENDAR_PATH (env).
   Format identik. Manual entry MENANG atas auto.
3. Lookup: `get_earnings_date(ticker)` cek manual dulu, fallback auto.

CATATAN JUJUR:
- yfinance untuk IDX coverage ~60%, sering null untuk small-mid cap.
- Manual override penting untuk ticker yang Anda hold tapi yfinance kosong.
- Refresh tidak sering (mingguan) karena earnings tidak berubah harian.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from app.core.config import settings

log = logging.getLogger("sahamflow.earnings")

_AUTO_PATH = Path(__file__).resolve().parents[2] / "data" / "earnings_auto.json"


def _ensure_dir() -> None:
    _AUTO_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.replace(path)


def _extract_earnings_date(calendar_obj) -> date | None:
    """Robust extractor — yfinance Ticker.calendar bisa dict atau DataFrame
    tergantung versi. Return earliest upcoming earnings date or None."""
    if calendar_obj is None:
        return None
    try:
        # Newer yfinance: dict with 'Earnings Date': [datetime, ...] or single
        if isinstance(calendar_obj, dict):
            val = calendar_obj.get("Earnings Date") or calendar_obj.get("earningsDate")
            if not val:
                return None
            if isinstance(val, (list, tuple)):
                val = val[0] if val else None
            if hasattr(val, "date"):
                return val.date()
            if isinstance(val, str):
                return date.fromisoformat(val[:10])
            return None
        # Older: pandas DataFrame
        if hasattr(calendar_obj, "loc"):
            row = calendar_obj.loc["Earnings Date"] if "Earnings Date" in calendar_obj.index else None
            if row is not None and len(row) > 0:
                v = row.iloc[0]
                return v.date() if hasattr(v, "date") else None
    except Exception as e:
        log.debug("Calendar parse failed: %s", e)
    return None


def refresh_from_yfinance(tickers: list[str] | None = None) -> dict:
    """Fetch earnings dates dari yfinance, cache ke file. Best-effort per ticker.

    Returns summary {fetched, with_date, errors}.
    """
    import yfinance as yf
    from app.data_sources.yahoo_finance import to_yahoo_symbol

    if tickers is None:
        tickers = settings.universe

    _ensure_dir()
    existing = _read_json(_AUTO_PATH)
    out = {k: v for k, v in existing.items() if not k.startswith("_")}

    summary = {"fetched": 0, "with_date": 0, "errors": 0}
    for t in tickers:
        try:
            summary["fetched"] += 1
            cal = yf.Ticker(to_yahoo_symbol(t)).calendar
            d = _extract_earnings_date(cal)
            if d:
                out[t.upper()] = {"earnings_date": d.isoformat(), "source": "yfinance"}
                summary["with_date"] += 1
        except Exception as e:
            summary["errors"] += 1
            log.debug("Earnings fetch %s failed: %s", t, e)

    out["_meta"] = {"updated_at": datetime.utcnow().isoformat()}
    _atomic_write(_AUTO_PATH, out)
    log.info("Earnings calendar refreshed: %s", summary)
    return summary


def _load_manual() -> dict:
    path = settings.EARNINGS_CALENDAR_PATH
    if not path:
        return {}
    return _read_json(Path(path))


def get_earnings_date(ticker: str) -> date | None:
    """Manual override wins; fallback yfinance auto-cache."""
    t = ticker.upper()
    for source in (_load_manual(), _read_json(_AUTO_PATH)):
        entry = source.get(t)
        if not entry:
            continue
        try:
            return date.fromisoformat(entry["earnings_date"][:10])
        except Exception:
            continue
    return None


def is_in_earnings_window(ticker: str, block_days: int | None = None) -> tuple[bool, date | None, int | None]:
    """Return (in_window, earnings_date, days_delta)."""
    block = block_days if block_days is not None else settings.EARNINGS_BLOCK_DAYS
    ed = get_earnings_date(ticker)
    if not ed:
        return False, None, None
    delta = abs((ed - date.today()).days)
    return delta <= block, ed, delta
