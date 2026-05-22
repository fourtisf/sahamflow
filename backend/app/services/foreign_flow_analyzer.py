"""Foreign flow analytics (Tahap 3).

Computes net buy/sell over a window, consistency (how many days same-direction),
and a z-score of today's net vs the trailing window. Requires foreign_net on the
OHLCV rows — which only exists once the IDX scraper feeds it. With Yahoo-only data
foreign_net is None, so analyze() reports has_data=False rather than guessing.
"""

from __future__ import annotations

import statistics


def analyze(foreign_net_series: list[int | None], window: int = 5) -> dict:
    """foreign_net_series: oldest-to-newest daily foreign net (IDR), may contain None."""
    vals = [v for v in foreign_net_series if v is not None]
    if not vals:
        return {"has_data": False}

    recent = vals[-window:]
    net_window = sum(recent)
    positive_days = sum(1 for v in recent if v > 0)
    consistency = positive_days / len(recent)

    if len(vals) >= 2:
        mean = statistics.fmean(vals)
        stdev = statistics.pstdev(vals)
        z = (vals[-1] - mean) / stdev if stdev else 0.0
    else:
        z = 0.0

    if net_window > 500_000_000_000:
        signal = "Strong Net Buy"
    elif net_window > 0:
        signal = "Net Buy"
    elif net_window > -500_000_000_000:
        signal = "Net Sell"
    else:
        signal = "Strong Net Sell"

    return {
        "has_data": True,
        "net_window": net_window,
        "window": len(recent),
        "consistency": round(consistency, 2),
        "z_score": round(z, 2),
        "signal": signal,
    }
