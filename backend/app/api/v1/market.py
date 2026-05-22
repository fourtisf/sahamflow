from fastapi import APIRouter

from app.core.redis_client import get_redis
from app.data_sources import yahoo_finance as yf

router = APIRouter(prefix="/market", tags=["market"])

# Yahoo symbols for the index header. SBN 10Y and BI Rate have no Yahoo feed, so
# they are intentionally absent (frontend shows them as static/manual).
INDICES = {
    "ihsg": "^JKSE",
    "lq45": "^JKLQ45",
    "usdidr": "IDR=X",
}

_CACHE_KEY = "market:indices"
_CACHE_TTL = 600  # 10 min — data is EOD/delayed anyway


@router.get("/indices")
def indices():
    """Latest index/FX quotes (delayed ~15 min). Cached 10 min in Redis.

    Returns null per key when Yahoo has no data, so the frontend never shows a
    fabricated number.
    """
    r = None
    try:
        r = get_redis()
        import json

        cached = r.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        r = None

    out: dict[str, dict | None] = {}
    for key, sym in INDICES.items():
        try:
            out[key] = yf.fetch_quote(sym)
        except Exception:
            out[key] = None

    if r is not None:
        try:
            import json

            r.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(out))
        except Exception:
            pass
    return out


@router.get("/ihsg-history")
def ihsg_history(days: int = 30):
    """Real IHSG (^JKSE) daily close history + support/resistance.

    Support/resistance are the recent swing low/high over the window — concrete
    levels from data, not hand-typed. Cached 10 min.
    """
    import json

    key = f"market:ihsg-history:{days}"
    r = None
    try:
        r = get_redis()
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        r = None

    period = "3mo" if days > 30 else "2mo"
    hist = yf.fetch_history("^JKSE", period=period)[-days:]
    closes = [h["close"] for h in hist]
    payload = {
        "history": hist,
        "support": round(min(closes), 2) if closes else None,
        "resistance": round(max(closes), 2) if closes else None,
        "last": closes[-1] if closes else None,
    }
    if r is not None:
        try:
            r.setex(key, _CACHE_TTL, json.dumps(payload))
        except Exception:
            pass
    return payload
