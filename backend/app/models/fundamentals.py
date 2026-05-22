from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Fundamentals(Base):
    __tablename__ = "fundamentals"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    per: Mapped[Decimal | None] = mapped_column(Numeric)
    pbv: Mapped[Decimal | None] = mapped_column(Numeric)
    roe: Mapped[Decimal | None] = mapped_column(Numeric)
    der: Mapped[Decimal | None] = mapped_column(Numeric)
    revenue_yoy: Mapped[Decimal | None] = mapped_column(Numeric)
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric)
    earnings_date: Mapped[date | None] = mapped_column(Date)
    red_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
