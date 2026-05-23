"""Portfolio risk engine — gerbang sebelum trade & monitor heat berjalan.

Smart-money discipline: tolak trade yang membuat:
- portfolio heat melebihi limit
- konsentrasi sektor melebihi limit
- korelasi tinggi dengan posisi existing (overlap risk, bukan diversifikasi)

Tanpa ini, sinyal apa pun bisa jadi blunder. Risk engine harus berkata TIDAK.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock, Trade
from app.services.data_sync import load_ohlcv_df

DEFAULT_ACCOUNT = 500_000_000  # IDR
HEAT_LIMIT_PCT = 6.0
SECTOR_CONCENTRATION_LIMIT_PCT = 40.0
CORRELATION_LIMIT = 0.75
DEFAULT_SL_PCT = 0.06  # used when trade row has no explicit SL


def _open_positions(db: Session) -> list[Trade]:
    return (
        db.execute(select(Trade).where(Trade.exit_date.is_(None))).scalars().all()
    )


def _position_value(p: Trade) -> float:
    if not (p.entry_price and p.shares):
        return 0.0
    return float(p.entry_price) * int(p.shares)


def _position_risk(p: Trade) -> float:
    """Risk per position in IDR (approx: entry * SL_pct * shares)."""
    return _position_value(p) * DEFAULT_SL_PCT


def _correlation(db: Session, ticker_a: str, ticker_b: str, days: int = 60) -> float | None:
    a = load_ohlcv_df(db, ticker_a, days=days)
    b = load_ohlcv_df(db, ticker_b, days=days)
    if a.empty or b.empty:
        return None
    ra = a["close"].pct_change().dropna()
    rb = b["close"].pct_change().dropna()
    joined = pd.concat([ra, rb], axis=1, join="inner").dropna()
    if len(joined) < 20:
        return None
    return round(float(joined.corr().iloc[0, 1]), 2)


def portfolio_state(db: Session, account_size: float = DEFAULT_ACCOUNT) -> dict:
    positions = _open_positions(db)
    by_sector: dict[str, float] = defaultdict(float)
    total_value = 0.0
    total_risk = 0.0
    pos_payload = []
    for p in positions:
        v = _position_value(p)
        r = _position_risk(p)
        total_value += v
        total_risk += r
        stock = db.get(Stock, (p.ticker or "").upper())
        sector = stock.sector if stock else None
        if sector:
            by_sector[sector] += v
        pos_payload.append({
            "ticker": p.ticker,
            "value_idr": int(v),
            "risk_idr": int(r),
            "sector": sector,
        })

    concentration = {
        s: round(v / total_value * 100, 1) for s, v in by_sector.items()
    } if total_value else {}

    # Pairwise correlation among open positions (max)
    tickers = [p.ticker for p in positions if p.ticker]
    max_corr = None
    max_corr_pair = None
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            c = _correlation(db, tickers[i], tickers[j])
            if c is None:
                continue
            if max_corr is None or abs(c) > abs(max_corr):
                max_corr = c
                max_corr_pair = (tickers[i], tickers[j])

    return {
        "account_size_idr": int(account_size),
        "open_positions": len(positions),
        "total_value_idr": int(total_value),
        "total_risk_idr": int(total_risk),
        "portfolio_heat_pct": round(total_risk / account_size * 100, 2),
        "heat_limit_pct": HEAT_LIMIT_PCT,
        "sector_concentration_pct": concentration,
        "sector_limit_pct": SECTOR_CONCENTRATION_LIMIT_PCT,
        "max_correlation": max_corr,
        "max_correlation_pair": max_corr_pair,
        "correlation_limit": CORRELATION_LIMIT,
        "positions": pos_payload,
    }


def check_proposed_trade(
    db: Session,
    ticker: str,
    entry_price: float,
    shares: int,
    account_size: float = DEFAULT_ACCOUNT,
) -> dict:
    """Pre-trade gate. Return {allow, reasons, projection}."""
    ticker = ticker.upper()
    state = portfolio_state(db, account_size)

    new_value = entry_price * shares
    new_risk = new_value * DEFAULT_SL_PCT
    new_heat_pct = (state["total_risk_idr"] + new_risk) / account_size * 100

    stock = db.get(Stock, ticker)
    sector = stock.sector if stock else None
    new_sector_value = state["sector_concentration_pct"].get(sector, 0) / 100 * state["total_value_idr"] if state["total_value_idr"] else 0
    new_sector_value += new_value
    projected_total = state["total_value_idr"] + new_value
    new_sector_pct = (new_sector_value / projected_total * 100) if projected_total else 0

    # Correlation with existing open positions
    worst_corr = None
    worst_pair = None
    for p in state["positions"]:
        if p["ticker"] == ticker:
            continue
        c = _correlation(db, ticker, p["ticker"])
        if c is None:
            continue
        if worst_corr is None or abs(c) > abs(worst_corr):
            worst_corr = c
            worst_pair = p["ticker"]

    reasons: list[str] = []
    if new_heat_pct > HEAT_LIMIT_PCT:
        reasons.append(
            f"Portfolio heat akan jadi {new_heat_pct:.2f}% (limit {HEAT_LIMIT_PCT}%) — REFUSE."
        )
    if sector and new_sector_pct > SECTOR_CONCENTRATION_LIMIT_PCT:
        reasons.append(
            f"Konsentrasi sektor {sector} akan jadi {new_sector_pct:.1f}% (limit {SECTOR_CONCENTRATION_LIMIT_PCT}%) — REFUSE."
        )
    if worst_corr is not None and abs(worst_corr) > CORRELATION_LIMIT:
        reasons.append(
            f"Korelasi {ticker}-{worst_pair} = {worst_corr} (>{CORRELATION_LIMIT}). Bukan diversifikasi, double-down — REFUSE."
        )

    return {
        "allow": len(reasons) == 0,
        "reasons": reasons,
        "ticker": ticker,
        "projected_heat_pct": round(new_heat_pct, 2),
        "projected_sector_pct": round(new_sector_pct, 1) if sector else None,
        "worst_correlation": {"value": worst_corr, "with": worst_pair} if worst_corr is not None else None,
    }
