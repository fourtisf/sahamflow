from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import OHLCVDaily, Stock

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("/rotation")
def sector_rotation(db: Session = Depends(get_db)):
    """5d relative strength per sector, aggregated from constituent OHLCV.

    With the 10-stock seed universe most sectors have 1-2 names; this becomes
    meaningful once the universe expands. Sectors with no price history are
    omitted rather than zero-filled.
    """
    stocks = db.execute(select(Stock)).scalars().all()
    by_sector: dict[str, list[float]] = defaultdict(list)

    for s in stocks:
        if not s.sector:
            continue
        closes = db.execute(
            select(OHLCVDaily.close)
            .where(OHLCVDaily.ticker == s.ticker)
            .order_by(OHLCVDaily.date.desc())
            .limit(6)
        ).scalars().all()
        if len(closes) >= 6 and closes[5]:
            chg_5d = (float(closes[0]) / float(closes[5]) - 1) * 100
            by_sector[s.sector].append(chg_5d)

    result = [
        {"sector": sector, "rs_5d_pct": round(sum(v) / len(v), 2), "constituents": len(v)}
        for sector, v in by_sector.items()
    ]
    result.sort(key=lambda r: r["rs_5d_pct"], reverse=True)
    return result
