"""AI morning brief / per-stock narrative via Anthropic (Tahap 4).

Hard rule: the model may ONLY use numbers passed in the prompt — it must not
invent figures. Cost control: callers limit this to the top-N composite scores and
results are cached in Redis for one day.
"""

from __future__ import annotations

import hashlib
import json

from app.core.claude_client import get_claude
from app.core.config import settings
from app.core.redis_client import get_redis

_SYSTEM = (
    "Kamu analis kuantitatif IHSG di sebuah institusi. Kamu menulis ringkas, "
    "tanpa hype, tanpa emoji, tanpa rekomendasi 'pasti'. ATURAN MUTLAK: hanya "
    "gunakan angka yang tersedia di data yang diberikan. JANGAN mengarang atau "
    "memperkirakan angka apa pun yang tidak ada di data."
)


def _cache_key(prefix: str, payload: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"narrative:{prefix}:{digest}"


def _generate(prompt: str, cache_key: str, max_tokens: int = 600) -> str:
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        return cached

    resp = get_claude().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text
    r.setex(cache_key, settings.NARRATIVE_CACHE_TTL, text)
    return text


def generate_brief(market_data: dict, top_signals: list[dict]) -> str:
    prompt = f"""Buat morning brief 3 paragraf Bahasa Indonesia untuk IHSG.

Sebut level support/resistance konkret dari data. Tone analis institusi.

DATA:
Regime: {market_data.get('regime')} (confidence {market_data.get('confidence')}%)
Breadth A/D: {market_data.get('breadth')}
Foreign 5D: {market_data.get('foreign_5d')}
Support/Resist: {market_data.get('support')}/{market_data.get('resistance')}
Top signals: {json.dumps(top_signals, ensure_ascii=False, default=str)}
"""
    return _generate(prompt, _cache_key("brief", {"m": market_data, "s": top_signals}))


def generate_stock_narrative(ticker: str, data: dict) -> str:
    prompt = f"""Tulis 1 paragraf analisa Bahasa Indonesia untuk saham {ticker}.

Hanya pakai data berikut, jangan tambah angka lain:
{json.dumps(data, ensure_ascii=False, default=str)}
"""
    return _generate(
        prompt, _cache_key(f"stock:{ticker}", data), max_tokens=300
    )
