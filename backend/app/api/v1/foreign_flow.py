from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SEED_TICKERS
from app.core.database import get_db
from app.models import OHLCVDaily
from app.services import foreign_flow_analyzer

router = APIRouter(prefix="/foreign-flow", tags=["foreign-flow"])


@router.get("/today")
def foreign_flow_today(db: Session = Depends(get_db)):
    """Per-ticker foreign flow analysis over the trailing window.

    Returns has_data=False per ticker until the IDX scraper feeds foreign_net
    (Yahoo does not provide it). Honest by design — no fabricated flow.
    """
    out = []
    for t in SEED_TICKERS:
        rows = db.execute(
            select(OHLCVDaily.foreign_net)
            .where(OHLCVDaily.ticker == t)
            .order_by(OHLCVDaily.date)
        ).scalars().all()
        analysis = foreign_flow_analyzer.analyze(list(rows))
        out.append({"ticker": t, **analysis})
    return out
