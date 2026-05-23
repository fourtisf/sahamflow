import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
        stop_loss=getattr(payload, "stop_loss", None),
        take_profit=getattr(payload, "take_profit", None),
        setup=getattr(payload, "setup", None),
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


@router.get("/equity-curve")
def equity_curve(db: Session = Depends(get_db)):
    """Equity curve dari trade nyata (closed only), oldest-to-newest.

    Hasil: list {date, cumulative_pnl_pct}. Drawdown dihitung dari peak.
    Inilah ukuran sebenarnya apakah tool ini menghasilkan uang.
    """
    rows = (
        db.execute(
            select(Trade)
            .where(Trade.exit_date.isnot(None), Trade.pnl_pct.isnot(None))
            .order_by(Trade.exit_date)
        )
        .scalars()
        .all()
    )
    curve = []
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in rows:
        cum += float(t.pnl_pct)
        peak = max(peak, cum)
        dd = cum - peak
        max_dd = min(max_dd, dd)
        curve.append({
            "date": str(t.exit_date.date()) if t.exit_date else None,
            "ticker": t.ticker,
            "pnl_pct": float(t.pnl_pct),
            "cumulative_pct": round(cum, 2),
            "drawdown_pct": round(dd, 2),
            "source": t.source,
            "setup": t.setup,
        })
    return {
        "trades": len(curve),
        "final_pnl_pct": round(cum, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "curve": curve,
    }


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    """Download semua trade sebagai CSV — untuk journal manual / spreadsheet."""
    rows = db.execute(select(Trade).order_by(Trade.entry_date.desc())).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ticker", "entry_date", "exit_date", "entry_price", "exit_price",
        "stop_loss", "take_profit", "pnl_pct", "setup", "source", "notes",
    ])
    for r in rows:
        writer.writerow([
            r.ticker,
            r.entry_date.isoformat() if r.entry_date else "",
            r.exit_date.isoformat() if r.exit_date else "",
            float(r.entry_price) if r.entry_price else "",
            float(r.exit_price) if r.exit_price else "",
            float(r.stop_loss) if r.stop_loss else "",
            float(r.take_profit) if r.take_profit else "",
            float(r.pnl_pct) if r.pnl_pct else "",
            r.setup or "",
            r.source or "",
            (r.notes or "").replace("\n", " ")[:200],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sahamflow_trades.csv"},
    )


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
