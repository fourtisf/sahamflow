import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str | None] = mapped_column(String(10))
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric)
    shares: Mapped[int | None] = mapped_column(Integer)
    entry_date: Mapped[datetime | None] = mapped_column(DateTime)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime)
    pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric)
    source: Mapped[str | None] = mapped_column(String(20))  # 'sahamflow' | 'diskresi'
    notes: Mapped[str | None] = mapped_column(Text)
