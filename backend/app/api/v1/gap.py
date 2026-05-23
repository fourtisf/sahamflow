"""Gap Radar API — serve data terstruktur untuk frontend."""

from fastapi import APIRouter

from app.services import gap_detector, pattern_stats

router = APIRouter(prefix="/gap", tags=["gap"])


@router.get("/radar")
def radar():
    """Return gap radar data dengan IHSG + classified patterns + stats."""
    ihsg, notable = gap_detector.scan_universe_gaps()
    stats = pattern_stats.get_cached()
    # Group by pattern for frontend convenience
    groups: dict[str, list[dict]] = {p: [] for p in gap_detector.PATTERN_META}
    for n in notable:
        pat = n.get("pattern")
        if pat in groups:
            row = dict(n)
            row["entry_plan"] = gap_detector._entry_plan(n)
            groups[pat].append(row)
    # Sort each group
    for pat, items in groups.items():
        items.sort(key=gap_detector.PATTERN_META[pat]["sort_key"])

    total = (ihsg or {}).get("_total_scanned", 0)
    bullish = len(groups["GAP_FILL_BULL"]) + len(groups["GAP_AND_GO"])
    bearish = len(groups["GAP_UP_FAIL"]) + len(groups["GAP_DN_CONT"])
    return {
        "ihsg": ihsg,
        "groups": groups,
        "stats": stats,
        "breadth": {
            "total_scanned": total,
            "bullish": bullish,
            "bearish": bearish,
            "bullish_pct": round(bullish * 100 / total, 1) if total else 0,
            "bearish_pct": round(bearish * 100 / total, 1) if total else 0,
            "label": "BULLISH SKEW" if bullish > bearish * 1.5 else "BEARISH SKEW" if bearish > bullish * 1.5 else "MIXED",
        },
    }
