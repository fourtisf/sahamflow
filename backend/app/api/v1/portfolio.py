from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services import portfolio_risk

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class TradeProposal(BaseModel):
    ticker: str
    entry_price: float
    shares: int
    account_size: float | None = None


@router.get("/risk")
def get_risk(
    account_size: float | None = Query(None),
    db: Session = Depends(get_db),
):
    return portfolio_risk.portfolio_state(db, account_size or settings.ACCOUNT_SIZE_IDR)


@router.post("/check")
def check_trade(payload: TradeProposal, db: Session = Depends(get_db)):
    """Pre-trade risk gate. allow=False means DO NOT take the trade."""
    return portfolio_risk.check_proposed_trade(
        db,
        payload.ticker,
        payload.entry_price,
        payload.shares,
        payload.account_size or settings.ACCOUNT_SIZE_IDR,
    )
