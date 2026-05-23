"""Unit tests for pure-logic services (no DB/network needed)."""

import numpy as np
import pandas as pd

from app.services import (
    backtest_engine,
    bandar_detector,
    foreign_flow_analyzer,
    regime_classifier,
    technical_analysis,
)


def _synthetic_uptrend(n=120):
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    base = np.linspace(1000, 1500, n) + np.random.RandomState(0).normal(0, 5, n)
    return pd.DataFrame(
        {
            "open": base,
            "high": base * 1.01,
            "low": base * 0.99,
            "close": base,
            "volume": np.random.RandomState(1).randint(1e6, 5e6, n),
            "foreign_net": [None] * n,
        },
        index=idx.date,
    )


def test_composite_score_bounded():
    df = _synthetic_uptrend()
    score, ind = technical_analysis.composite_score(df)
    assert -1.0 <= score <= 1.0
    assert set(ind) == set(technical_analysis.WEIGHTS)
    # A clean uptrend should score bullish under the momentum-aligned composite.
    assert score > 0.2


def test_signal_labels():
    assert technical_analysis.signal_label(0.6) == "Strong Buy"
    assert technical_analysis.signal_label(0.0) == "Hold"
    assert technical_analysis.signal_label(-0.6) == "Strong Sell"


def test_regime_classify_bands():
    bullish = regime_classifier.classify_regime(
        {"breadth": 1, "ma200": 1, "foreign": 1, "fx": 1, "yield": 1, "dispersion": 1}
    )
    assert bullish["regime"] == "Risk-On Bullish"
    crash = regime_classifier.classify_regime(
        {"breadth": -1, "ma200": -1, "foreign": -1, "fx": -1, "yield": -1, "dispersion": -1}
    )
    assert crash["regime"] == "Crash Mode"
    assert 50 <= bullish["confidence"] <= 95


def test_regime_normalizers():
    assert regime_classifier.norm_breadth(300, 100) > 0
    assert regime_classifier.norm_breadth(100, 300) < 0
    assert regime_classifier.norm_yield(8.0) < 0  # high yield = risk-off


def test_foreign_flow_no_data():
    assert foreign_flow_analyzer.analyze([None, None]) == {"has_data": False}


def test_foreign_flow_net_buy():
    res = foreign_flow_analyzer.analyze([1e11, 2e11, 3e11, 1e11, 2e11])
    assert res["has_data"] and res["net_window"] > 0
    assert "Buy" in res["signal"]


def test_bandar_estimated_flag():
    out = bandar_detector.detect(_synthetic_uptrend(), foreign_net_5d=10)
    assert out["estimated"] is True
    assert out["phase"] in {"Markup", "Accumulation", "Distribution", "Markdown"}


def test_backtest_metrics_shape():
    df = _synthetic_uptrend()
    signal = pd.Series([True] + [False] * (len(df) - 1), index=df.index)
    m = backtest_engine.run(df, signal)
    assert "total_return_pct" in m and "equity_curve" in m
    assert m["total_trades"] >= 1


def test_backtest_no_trades():
    df = _synthetic_uptrend()
    signal = pd.Series([False] * len(df), index=df.index)
    m = backtest_engine.run(df, signal)
    assert m["total_trades"] == 0
