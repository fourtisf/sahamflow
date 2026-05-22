from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    high: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    low: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    close: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[int | None] = mapped_column(BigInteger)
    foreign_buy: Mapped[int | None] = mapped_column(BigInteger)
    foreign_sell: Mapped[int | None] = mapped_column(BigInteger)
    foreign_net: Mapped[int | None] = mapped_column(BigInteger)
