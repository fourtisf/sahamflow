"""Live PnL Summary API — same data as Telegram pinned message, untuk web."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import OHLCVDaily, Trade

router = APIRouter(prefix="/pnl", tags=["pnl"])


def _last_close(db: Session, ticker: str) -> float | None:
    row = db.execute(
        select(OHLCVDaily.close)
        .where(OHLCVDaily.ticker == ticker)
        .order_by(OHLCVDaily.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Live PnL summary: open positions, closed trades, win rate, equity curve."""
    trades = db.execute(select(Trade).order_by(Trade.entry_date.desc())).scalars().all()
    open_t = [t for t in trades if t.exit_date is None]
    closed_t = [t for t in trades if t.exit_date is not None]
    wins = [t for t in closed_t if t.pnl_pct and float(t.pnl_pct) > 0]
    losses = [t for t in closed_t if t.pnl_pct and float(t.pnl_pct) <= 0]
    total_pnl = sum(float(t.pnl_pct or 0) for t in closed_t)
    avg_win = (sum(float(t.pnl_pct) for t in wins) / len(wins)) if wins else 0
    avg_loss = (sum(float(t.pnl_pct) for t in losses) / len(losses)) if losses else 0
    win_rate = (len(wins) / len(closed_t) * 100) if closed_t else 0

    open_positions = []
    for t in open_t:
        last = _last_close(db, t.ticker) or float(t.entry_price or 0)
        entry = float(t.entry_price or 0)
        unrealized = ((last / entry - 1) * 100) if entry else 0
        open_positions.append({
            "ticker": t.ticker,
            "entry": entry,
            "last": last,
            "unrealized_pct": round(unrealized, 2),
            "setup": t.setup,
            "stop_loss": float(t.stop_loss) if t.stop_loss else None,
            "take_profit": float(t.take_profit) if t.take_profit else None,
            "entry_date": t.entry_date.isoformat() if t.entry_date else None,
        })

    closed_recent = [
        {
            "ticker": t.ticker,
            "entry": float(t.entry_price) if t.entry_price else None,
            "exit": float(t.exit_price) if t.exit_price else None,
            "pnl_pct": float(t.pnl_pct) if t.pnl_pct else 0,
            "setup": t.setup,
            "exit_date": t.exit_date.isoformat() if t.exit_date else None,
        }
        for t in closed_t[:20]
    ]

    # Equity curve (cumulative %)
    closed_chrono = sorted(closed_t, key=lambda x: x.exit_date or datetime.min)
    cum = 0.0
    curve = []
    for t in closed_chrono:
        cum += float(t.pnl_pct or 0)
        curve.append({
            "date": t.exit_date.isoformat() if t.exit_date else None,
            "cumulative_pct": round(cum, 2),
        })

    return {
        "totals": {
            "trades": len(trades),
            "open": len(open_t),
            "closed": len(closed_t),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(win_rate, 1),
            "total_pnl_pct": round(total_pnl, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
        },
        "open_positions": open_positions,
        "closed_recent": closed_recent,
        "equity_curve": curve,
    }
