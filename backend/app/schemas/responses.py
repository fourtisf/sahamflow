from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RegimeResponse(BaseModel):
    date: date
    regime: str | None = None
    confidence: float | None = None
    raw_score: float | None = None
    breadth_ratio: float | None = None
    foreign_flow_5d: int | None = None
    factors: dict[str, Any] | None = None


class ScreenerRow(BaseModel):
    ticker: str
    composite_score: float | None = None
    signal: str | None = None
    bandar_phase: str | None = None
    bandar_score: int | None = None
    foreign_signal: str | None = None
    indicators: dict[str, Any] | None = None


class StockAnalysis(BaseModel):
    ticker: str
    last_close: float | None = None
    composite_score: float | None = None
    signal: str | None = None
    indicators: dict[str, Any] | None = None
    bandar: dict[str, Any] | None = None
    foreign_flow: dict[str, Any] | None = None
    narrative: str | None = None


class TradeIn(BaseModel):
    ticker: str
    entry_price: float
    exit_price: float | None = None
    shares: int
    entry_date: datetime | None = None
    exit_date: datetime | None = None
    source: str = Field(default="diskresi", pattern="^(sahamflow|diskresi)$")
    notes: str | None = None


class TradeOut(BaseModel):
    id: UUID
    ticker: str | None
    entry_price: float | None
    exit_price: float | None
    shares: int | None
    pnl_pct: float | None
    source: str | None
    notes: str | None

    model_config = {"from_attributes": True}
