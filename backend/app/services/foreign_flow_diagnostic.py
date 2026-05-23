"""Diagnostic untuk verifikasi foreign flow scraper jalan & populate DB.

Run via:
  python -c "from app.services.foreign_flow_diagnostic import run; run()"

Output:
  - Status scraper terakhir jalan
  - Coverage foreign_net per universe
  - Sample 5 ticker dengan FF data terbaru
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import OHLCVDaily

log = logging.getLogger("sahamflow.ff_diag")


def run() -> dict:
    """Return diagnostic dict."""
    summary: dict = {
        "universe_size": len(settings.universe),
        "with_ff_today": 0,
        "with_ff_5d": 0,
        "no_ff": [],
        "sample": [],
        "latest_ff_date": None,
    }

    with SessionLocal() as db:
        latest = db.execute(
            select(func.max(OHLCVDaily.date)).where(OHLCVDaily.foreign_net.isnot(None))
        ).scalar_one_or_none()
        summary["latest_ff_date"] = str(latest) if latest else None

        cutoff_5d = date.today() - timedelta(days=7)

        for t in settings.universe:
            today_row = (
                db.execute(
                    select(OHLCVDaily)
                    .where(OHLCVDaily.ticker == t)
                    .order_by(OHLCVDaily.date.desc())
                    .limit(1)
                )
                .scalar_one_or_none()
            )
            if not today_row:
                summary["no_ff"].append(f"{t} (no OHLCV)")
                continue
            if today_row.foreign_net is None:
                summary["no_ff"].append(t)
                continue
            summary["with_ff_today"] += 1

            recent = (
                db.execute(
                    select(OHLCVDaily)
                    .where(OHLCVDaily.ticker == t, OHLCVDaily.date >= cutoff_5d)
                    .where(OHLCVDaily.foreign_net.isnot(None))
                )
                .scalars()
                .all()
            )
            if recent:
                summary["with_ff_5d"] += 1
                if len(summary["sample"]) < 5:
                    fn5d = sum(int(r.foreign_net or 0) for r in recent)
                    summary["sample"].append({
                        "ticker": t,
                        "ff_5d_idr": fn5d,
                        "ff_5d_str": f"{fn5d/1e9:+.2f}B" if fn5d else "0",
                        "days_with_data": len(recent),
                    })

    summary["coverage_today_pct"] = round(
        summary["with_ff_today"] * 100 / summary["universe_size"], 1
    ) if summary["universe_size"] else 0
    return summary


def print_report() -> None:
    s = run()
    print("=" * 60)
    print("FOREIGN FLOW DIAGNOSTIC")
    print("=" * 60)
    print(f"Universe size       : {s['universe_size']}")
    print(f"Latest FF data date : {s['latest_ff_date']}")
    print(f"With FF today       : {s['with_ff_today']} ({s['coverage_today_pct']}%)")
    print(f"With FF 5D recent   : {s['with_ff_5d']}")
    print()
    if s["sample"]:
        print("Sample (5):")
        for row in s["sample"]:
            print(f"  {row['ticker']:<6}  FF 5D: {row['ff_5d_str']:>12}  ({row['days_with_data']} days)")
    print()
    if s["no_ff"]:
        print(f"Missing FF ({len(s['no_ff'])} ticker):")
        print(f"  {', '.join(s['no_ff'][:20])}")
    print()
    if s["coverage_today_pct"] == 0:
        print("⚠️  SCRAPER BELUM POPULATE DATA — cek logs sahamflow-scheduler atau run sync_foreign_flow manual.")
    elif s["coverage_today_pct"] < 50:
        print(f"⚠️  Coverage rendah ({s['coverage_today_pct']}%) — scraper sebagian jalan, perlu investigasi.")
    else:
        print(f"✅ Coverage OK ({s['coverage_today_pct']}%)")
