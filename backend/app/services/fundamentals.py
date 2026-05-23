"""Fundamental quality scoring — bluechip exception.

Tanpa ini, BBCA (ROE 21%, NPL terendah IDX, market leader) bisa dapat AVOID
di pullback 9%. Itu kontra-smart-money. Bluechip layak threshold lebih longgar.

quality_score 0-100 dari yfinance fundamentals:
- ROE: > 20% (+30), > 15% (+20), > 10% (+10)
- Profit margin: > 20% (+15), > 10% (+10)
- Market cap: > Rp 200T mega (+20), > Rp 50T large (+10)
- PE: 0-25 wajar (+10), > 50 overvalued (-10), negatif/rugi (-15)
- DER: < 1.0 (+10), > 2.0 (-10)

Tier:
- >= 75: BLUE CHIP (threshold AVOID lebih ketat = -0.65, beri kepercayaan ekstra)
- 50-74: STANDARD (threshold normal -0.50)
- < 50:  JUNK / SPECULATIVE (threshold lebih longgar -0.35, easier AVOID)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.redis_client import get_redis
from app.data_sources import yahoo_finance as yf_src

log = logging.getLogger("sahamflow.fundamentals")
_CACHE_TTL = 86400  # 24 jam


def _fetch_yf_info(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    try:
        info = yf.Ticker(yf_src.to_yahoo_symbol(ticker)).info or {}
    except Exception:
        info = {}
    return info


def compute_quality_score(info: dict[str, Any]) -> tuple[int, dict]:
    """Hitung quality_score 0-100 + breakdown driver."""
    score = 0
    drivers: dict[str, Any] = {}

    roe = info.get("returnOnEquity")
    if isinstance(roe, (int, float)):
        roe_pct = roe * 100 if abs(roe) < 1 else roe
        drivers["roe_pct"] = round(roe_pct, 1)
        if roe_pct > 20:
            score += 30
        elif roe_pct > 15:
            score += 20
        elif roe_pct > 10:
            score += 10

    pm = info.get("profitMargins")
    if isinstance(pm, (int, float)):
        pm_pct = pm * 100 if abs(pm) < 1 else pm
        drivers["profit_margin_pct"] = round(pm_pct, 1)
        if pm_pct > 20:
            score += 15
        elif pm_pct > 10:
            score += 10
        elif pm_pct < 0:
            score -= 15

    mcap = info.get("marketCap")
    if isinstance(mcap, (int, float)):
        drivers["market_cap_idr"] = int(mcap)
        if mcap > 200e12:
            score += 20
        elif mcap > 50e12:
            score += 10

    pe = info.get("trailingPE") or info.get("forwardPE")
    if isinstance(pe, (int, float)):
        drivers["pe"] = round(pe, 1)
        if 0 < pe <= 25:
            score += 10
        elif pe > 50:
            score -= 10
    elif pe is None and info.get("trailingEps", 0) <= 0:
        score -= 15
        drivers["pe"] = None
        drivers["earnings"] = "negative / no data"

    der = info.get("debtToEquity")
    if isinstance(der, (int, float)):
        # yfinance kadang persen kadang rasio
        der_norm = der / 100 if der > 10 else der
        drivers["der"] = round(der_norm, 2)
        if der_norm < 1.0:
            score += 10
        elif der_norm > 2.0:
            score -= 10

    score = max(0, min(100, score))
    drivers["score"] = score
    if score >= 75:
        drivers["tier"] = "BLUE CHIP"
    elif score >= 50:
        drivers["tier"] = "STANDARD"
    else:
        drivers["tier"] = "JUNK / SPECULATIVE"
    return score, drivers


def get_quality(ticker: str) -> dict:
    """Cached quality assessment for a ticker."""
    key = f"quality:{ticker.upper()}"
    r = None
    try:
        r = get_redis()
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        r = None

    info = _fetch_yf_info(ticker)
    if not info:
        return {"score": None, "tier": "UNKNOWN", "drivers": {}, "source": "unavailable"}

    score, drivers = compute_quality_score(info)
    payload = {
        "score": score,
        "tier": drivers["tier"],
        "drivers": drivers,
        "source": "yfinance",
    }
    if r is not None:
        try:
            r.setex(key, _CACHE_TTL, json.dumps(payload, default=str))
        except Exception:
            pass
    return payload


def avoid_threshold_for(quality_score: int | None) -> float:
    """Quality-adjusted AVOID threshold. Bluechip dapat keringanan."""
    if quality_score is None:
        return -0.5
    if quality_score >= 75:
        return -0.65  # bluechip — butuh sinyal lebih ekstrem sebelum AVOID
    if quality_score >= 50:
        return -0.5
    return -0.35  # junk — lebih ketat
