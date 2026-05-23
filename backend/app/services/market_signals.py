"""Price-action signals for IHSG (and generic OHLC series).

Captures the things a real trader reads off the chart but the heuristic regime
model is blind to:
- consecutive down/up streaks (capitulation territory)
- reversal day after a streak (potential turn)
- gap-down close (gap filled = supply exhausted)
- recent returns (path dependence — distinguishes Distribution-from-top vs
  Markdown-tail vs Accumulation-bottom)
"""

from __future__ import annotations


def _close(bars: list[dict]) -> list[float]:
    return [b["close"] for b in bars]


def consecutive_down_streak(bars: list[dict]) -> int:
    """Number of consecutive down closes ending at the latest bar.

    The latest bar itself counts as down if close[-1] < close[-2]. If the latest
    bar is up, the streak is broken (returns 0) — use reversal_after_streak() to
    detect the just-broken streak.
    """
    closes = _close(bars)
    if len(closes) < 2:
        return 0
    n = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            n += 1
        else:
            break
    return n


def reversal_after_streak(bars: list[dict], min_streak: int = 5) -> dict | None:
    """Detect: the prior N bars were a down-streak AND the latest bar closed green.

    That's the classic capitulation-then-reclaim setup. Returns details if found.
    """
    closes = _close(bars)
    if len(closes) < min_streak + 2:
        return None
    if closes[-1] <= closes[-2]:
        return None  # latest bar must be green
    # count down-streak ending at bar -2 (the bar before the green reversal)
    n = 0
    for i in range(len(closes) - 2, 0, -1):
        if closes[i] < closes[i - 1]:
            n += 1
        else:
            break
    if n < min_streak:
        return None
    return {
        "streak_length": n,
        "reversal_close": closes[-1],
        "reversal_pct": round((closes[-1] / closes[-2] - 1) * 100, 2),
    }


def gap_filled_today(bars: list[dict]) -> dict | None:
    """Was a recent down-gap filled by the latest bar?

    A down-gap on bar i: low[i] > high[i+1] (gap to the downside next day, i.e.
    open[i+1] gaps below low[i] and high[i+1] stays below low[i]).
    Filled = latest bar's high >= the gap top (low[i]).
    """
    if len(bars) < 3:
        return None
    last = bars[-1]
    for i in range(len(bars) - 2, max(0, len(bars) - 15), -1):
        prev = bars[i - 1] if i >= 1 else None
        cur = bars[i]
        if not prev:
            continue
        gap_top = prev["low"]
        gap_bottom = cur["high"]
        if gap_bottom < gap_top:  # there was a down-gap between prev and cur
            if last["high"] >= gap_top:
                return {
                    "gap_date": cur["date"],
                    "gap_top": gap_top,
                    "gap_bottom": gap_bottom,
                    "filled_on": last["date"],
                }
    return None


def return_pct(bars: list[dict], lookback: int) -> float | None:
    closes = _close(bars)
    if len(closes) <= lookback:
        return None
    first = closes[-(lookback + 1)]
    if not first:
        return None
    return round((closes[-1] / first - 1) * 100, 2)


def regime_path_modifier(bars: list[dict]) -> dict:
    """Derive a path-aware regime modifier from IHSG OHLC.

    Returns: {modifier, signals{...}} — modifier is one of:
      - 'Potential Accumulation'  (deep drop + reversal/capitulation signature)
      - 'Markdown Capitulation'   (deep drop, no reversal yet)
      - 'Distribution Risk'       (large rally + signs of weakening)
      - None                      (no strong path signal)
    """
    ret_30d = return_pct(bars, 22) or 0.0  # ~30 calendar = ~22 trading days
    ret_90d = return_pct(bars, 66) or 0.0
    streak = consecutive_down_streak(bars)
    reversal = reversal_after_streak(bars, min_streak=5)
    gap = gap_filled_today(bars)

    signals = {
        "return_30d_pct": ret_30d,
        "return_90d_pct": ret_90d,
        "streak_down": streak,
        "reversal_day": reversal,
        "gap_filled_today": gap,
    }

    modifier = None
    if ret_30d <= -8.0:
        # deep drop territory
        if reversal or gap or streak == 0:
            modifier = "Potential Accumulation"
        else:
            modifier = "Markdown Capitulation"
    elif ret_30d >= 12.0:
        modifier = "Distribution Risk"

    return {"modifier": modifier, "signals": signals}
