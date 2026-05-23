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
    "Kamu analis buy-side seperti di hedge fund IHSG — skeptis, terstruktur, "
    "berorientasi risk-reward asimetris. Bahasa Indonesia formal. JANGAN pakai "
    "hype, emoji, atau kata 'pasti'/'dijamin'/'kaya cepat'. JANGAN beri "
    "rekomendasi investasi — sebut sebagai 'setup', 'skenario', atau "
    "'asimetri R:R'. Pakai bahasa probabilistik (\"setup berpotensi…\", \"jika X "
    "tervalidasi…\"). Sebut konteks regime market ketika menilai sinyal: sinyal "
    "yang melawan regime = keyakinan rendah. ATURAN MUTLAK: hanya gunakan angka "
    "yang ada di data — jangan mengarang angka apa pun. Selalu sebutkan apa yang "
    "akan MEMBATALKAN setup (invalidation level)."
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


def generate_stock_narrative(ticker: str, intel: dict) -> str:
    """3-paragraph buy-side analysis for one ticker, using the intel payload only."""
    prompt = f"""Tulis analisis saham {ticker} dalam 3 paragraf Bahasa Indonesia:

PARAGRAF 1 — Setup teknikal. Sebut RSI, MACD histogram, posisi vs MA200 (%),
volume ratio 20D, fase Wyckoff (bandar). Pakai angkanya dari data.

PARAGRAF 2 — Konteks regime & smart money. Apakah sinyal selaras dengan regime
market saat ini? Foreign flow mendukung atau melawan? Sebut conviction.

PARAGRAF 3 — Asimetri risk-reward. Sebut level entry/SL/TP dari ATR, R:R,
DAN level/kondisi yang membatalkan setup (invalidation). Akhiri dengan kalimat:
"Ini analisis data, bukan rekomendasi investasi."

DATA (HANYA INI yang boleh kamu pakai — jangan ada angka lain):
{json.dumps(intel, ensure_ascii=False, default=str, indent=2)}
"""
    return _generate(
        prompt, _cache_key(f"stock:{ticker}", intel), max_tokens=550
    )
