from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Trade
from app.schemas.responses import TradeIn, TradeOut

router = APIRouter(prefix="/trades", tags=["trades"])


def _pnl_pct(entry: float | None, exit_: float | None) -> float | None:
    if entry and exit_:
        return round((exit_ / entry - 1) * 100, 2)
    return None


@router.post("", response_model=TradeOut)
def create_trade(payload: TradeIn, db: Session = Depends(get_db)):
    trade = Trade(
        ticker=payload.ticker.upper(),
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        shares=payload.shares,
        entry_date=payload.entry_date,
        exit_date=payload.exit_date,
        pnl_pct=_pnl_pct(payload.entry_price, payload.exit_price),
        source=payload.source,
        notes=payload.notes,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.get("", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    rows = db.execute(select(Trade).order_by(Trade.entry_date.desc())).scalars().all()
    return rows


@router.get("/attribution")
def attribution(db: Session = Depends(get_db)):
    """P&L breakdown: Sahamflow signals vs discretionary trades."""
    rows = db.execute(select(Trade)).scalars().all()
    buckets: dict[str, dict] = {
        "sahamflow": {"count": 0, "wins": 0, "pnl_sum": 0.0},
        "diskresi": {"count": 0, "wins": 0, "pnl_sum": 0.0},
    }
    for r in rows:
        if r.pnl_pct is None:
            continue
        b = buckets.get(r.source or "diskresi")
        if b is None:
            continue
        b["count"] += 1
        b["pnl_sum"] += float(r.pnl_pct)
        if float(r.pnl_pct) > 0:
            b["wins"] += 1

    for b in buckets.values():
        b["win_rate"] = round(b["wins"] / b["count"] * 100, 1) if b["count"] else 0.0
        b["pnl_sum"] = round(b["pnl_sum"], 2)

    return buckets
