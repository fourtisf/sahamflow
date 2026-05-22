from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RegimeHistory(Base):
    __tablename__ = "regime_history"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    regime: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    breadth_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    foreign_flow_5d: Mapped[int | None] = mapped_column(BigInteger)
    sbn_yield: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    usd_idr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    raw_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    extra: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
