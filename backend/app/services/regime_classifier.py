"""IHSG market regime detector (Tahap 1).

Classifies the market into 5 regimes from a multi-factor score. Every factor is
normalized to [-1, +1] before weighting so the composite is bounded and the
thresholds in classify_regime are meaningful.

Factors (and their data needs):
  breadth     advance/decline ratio across the universe
  foreign     foreign net 5d flow (needs IDX scraper; 0 until available)
  ma200       IHSG close vs its 200d MA
  fx          USD/IDR 30d trend (rupiah weakening = risk-off)
  yield       SBN 10y signal (>7% = risk-off threshold)
  dispersion  sector dispersion 5d (high = late cycle)

The API/sync layer is responsible for sourcing the raw inputs; this module only
does the math, so it stays testable and never invents data.
"""

from __future__ import annotations

import numpy as np

WEIGHTS = {
    "breadth": 0.25,
    "foreign": 0.20,
    "ma200": 0.15,
    "fx": 0.15,
    "yield": 0.15,
    "dispersion": 0.10,
}

REGIMES = [
    (0.7, "Risk-On Bullish"),
    (0.3, "Accumulation Phase"),
    (-0.3, "Transition"),
    (-0.7, "Risk-Off Defensive"),
]
CRASH = "Crash Mode"


def _clip(x: float) -> float:
    return float(np.clip(x, -1.0, 1.0))


def norm_breadth(advances: int, declines: int) -> float:
    """A/D ratio: >2 bullish, <0.5 bearish. Maps log-ratio to [-1,1]."""
    if declines <= 0:
        return 1.0 if advances > 0 else 0.0
    ratio = advances / declines
    # log2(2)=1 -> ~+0.5; log2(0.5)=-1 -> ~-0.5; scaled and clipped.
    return _clip(np.log2(max(ratio, 1e-6)) / 2)


def norm_foreign(net_5d_idr: float) -> float:
    """>+500B IDR = strongly bullish. Linear up to ±1T."""
    return _clip(net_5d_idr / 1_000_000_000_000)


def norm_ma200(ihsg_close: float, ma200: float) -> float:
    if not ma200:
        return 0.0
    # ±10% from the 200d MA saturates the signal.
    return _clip(((ihsg_close - ma200) / ma200) / 0.10)


def norm_fx(usdidr_change_pct_30d: float) -> float:
    """Rupiah weakening (positive change) is risk-off, so we invert."""
    return _clip(-usdidr_change_pct_30d / 5.0)


def norm_yield(sbn_10y_pct: float) -> float:
    """>7% is the risk-off threshold; below 6% is supportive."""
    return _clip((6.5 - sbn_10y_pct) / 1.0)


def norm_dispersion(dispersion_5d: float) -> float:
    """High dispersion = late cycle (mildly risk-off). Centered around 10."""
    return _clip((10.0 - dispersion_5d) / 10.0)


def confidence(score: float) -> float:
    """Map |score| within a regime band to a 50-95% confidence figure."""
    return round(min(95.0, 50.0 + abs(score) * 60.0), 1)


def classify_regime(factors: dict[str, float]) -> dict:
    """factors: already-normalized values keyed by WEIGHTS keys.

    Returns regime name, confidence, raw score, and the factor contributions.
    Missing factors default to 0 (neutral).
    """
    contributions = {k: _clip(factors.get(k, 0.0)) * w for k, w in WEIGHTS.items()}
    score = _clip(sum(contributions.values()))

    regime = CRASH
    for threshold, name in REGIMES:
        if score > threshold:
            regime = name
            break

    return {
        "regime": regime,
        "confidence": confidence(score),
        "raw_score": round(score, 3),
        "factors": {k: round(factors.get(k, 0.0), 3) for k in WEIGHTS},
        "contributions": {k: round(v, 3) for k, v in contributions.items()},
    }
