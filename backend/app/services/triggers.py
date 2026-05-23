"""Konversi sinyal → aturan eksekusi machine-actionable.

Smart-money desk tidak pernah taruh "Sell" tanpa: kapan masuk, kapan setup gugur,
kapan menyerah karena tidak gerak. Module ini menerjemahkan composite + ATR
menjadi trigger / invalidation / time-stop yang konkret.
"""

from __future__ import annotations


def derive_triggers(intel: dict) -> dict | None:
    """intel: payload dari signal_intelligence.build_intel.

    Long-only (IDX): hanya bangun trigger untuk bias='long'. Avoid/short tidak
    diberi trigger entry karena IDX retail tidak bisa short.
    """
    last = intel.get("last_close")
    atr = (intel.get("indicators") or {}).get("atr14")
    bias = intel.get("bias") or (intel.get("regime") or {}).get("bias")
    score = intel.get("composite_score", 0) or 0

    if not last or not atr or bias != "long":
        return None

    strong = abs(score) >= 0.5
    confirm_buffer = 0.5 * atr
    pullback_buffer = 0.5 * atr

    trigger = {
        "type": "long_breakout_or_pullback",
        "entry_breakout_above": round(last + confirm_buffer, 2),
        "entry_pullback_at": round(last - pullback_buffer, 2),
        "require_volume_x": 1.5,
        "preferred_entry": "breakout" if strong else "pullback",
    }
    invalidation = {
        "level": round(last - 2 * atr, 2),
        "rule": "Setup gugur jika close di bawah level invalidasi.",
    }

    time_stop_bars = 10 if strong else 7
    return {
        "trigger": trigger,
        "invalidation": invalidation,
        "time_stop_bars": time_stop_bars,
        "rules": [
            f"Konfirmasi entry hanya saat volume ≥ {trigger['require_volume_x']}× rata-rata 20D.",
            f"Setup BATAL jika close menembus {invalidation['level']}.",
            f"Time stop: keluar jika tidak ada follow-through dalam {time_stop_bars} bar.",
            "Scale: 1/3 saat trigger, 1/3 di +1R, 1/3 di +2R. Trail stop di breakeven setelah +1R.",
        ],
    }
