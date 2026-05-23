"""Historical win rate per gap pattern (cached daily).

Untuk setiap saham di universe, scan N hari ke belakang. Untuk setiap hari,
klasifikasikan pola gap (sama logic seperti gap_detector.classify_gap_pattern),
lalu cek next-day return. Akumulasi stats per pola:

  - n_observations  : total kejadian pola ini
  - win_rate_pct    : % yang next-day return > 0
  - avg_return_pct  : average next-day close vs today close (%)
  - median_return_pct

Cache di file JSON, refresh max 1×/hari (heavy compute).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import OHLCVDaily

log = logging.getLogger("sahamflow.pattern_stats")

_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "pattern_stats.json"
_CACHE_TTL_HOURS = 24


def _classify(gap_pct: float, day_pct: float) -> str | None:
    if abs(gap_pct) < 1.0:
        return None
    if gap_pct > 0 and day_pct > 0:
        return "GAP_AND_GO"
    if gap_pct > 0 and day_pct <= 0:
        return "GAP_UP_FAIL"
    if gap_pct <= 0 and day_pct > 0:
        return "GAP_FILL_BULL"
    return "GAP_DN_CONT"


def compute(lookback_days: int = 90) -> dict:
    """Heavy compute — scan last N days × all universe, tally per pattern."""
    stats: dict[str, list[float]] = {
        "GAP_FILL_BULL": [],
        "GAP_AND_GO": [],
        "GAP_UP_FAIL": [],
        "GAP_DN_CONT": [],
    }
    with SessionLocal() as db:
        for ticker in settings.universe:
            rows = (
                db.execute(
                    select(OHLCVDaily)
                    .where(OHLCVDaily.ticker == ticker)
                    .order_by(OHLCVDaily.date.desc())
                    .limit(lookback_days + 2)
                )
                .scalars()
                .all()
            )
            if len(rows) < 3:
                continue
            rows = list(reversed(rows))  # oldest → newest
            for i in range(1, len(rows) - 1):
                today = rows[i]
                prev = rows[i - 1]
                next_ = rows[i + 1]
                if not all([today.open, today.close, prev.close, next_.close]):
                    continue
                gap_pct = (float(today.open) / float(prev.close) - 1) * 100
                day_pct = (float(today.close) / float(prev.close) - 1) * 100
                pattern = _classify(gap_pct, day_pct)
                if not pattern:
                    continue
                next_return = (float(next_.close) / float(today.close) - 1) * 100
                stats[pattern].append(round(next_return, 2))

    result: dict[str, dict] = {}
    for pat, returns in stats.items():
        n = len(returns)
        if n == 0:
            result[pat] = {"n": 0, "win_rate_pct": None, "avg_return_pct": None, "median_return_pct": None}
            continue
        wins = sum(1 for r in returns if r > 0)
        result[pat] = {
            "n": n,
            "win_rate_pct": round(wins / n * 100, 1),
            "avg_return_pct": round(sum(returns) / n, 2),
            "median_return_pct": round(median(returns), 2),
        }
    result["_meta"] = {"computed_at": datetime.utcnow().isoformat(), "lookback_days": lookback_days}
    return result


def get_cached(force_refresh: bool = False) -> dict:
    """Return cached stats; refresh kalau expired atau force_refresh=True."""
    if not force_refresh and _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text())
            meta = data.get("_meta") or {}
            computed = datetime.fromisoformat(meta["computed_at"])
            if datetime.utcnow() - computed < timedelta(hours=_CACHE_TTL_HOURS):
                return data
        except Exception as e:
            log.debug("Cache read failed, recomputing: %s", e)

    data = compute()
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(_CACHE_PATH)
    except Exception as e:
        log.warning("Cache write failed: %s", e)
    return data
