from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalCache(Base):
    __tablename__ = "signal_cache"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    composite_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    indicators: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    foreign_signal: Mapped[str | None] = mapped_column(String(50))
    bandar_phase: Mapped[str | None] = mapped_column(String(50))
    bandar_score: Mapped[int | None] = mapped_column(Integer)
    ai_predict: Mapped[int | None] = mapped_column(Integer)
    narrative: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
