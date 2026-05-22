"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("sector", sa.String(100)),
        sa.Column("market_cap", sa.BigInteger),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "ohlcv_daily",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("open", sa.Numeric(15, 2)),
        sa.Column("high", sa.Numeric(15, 2)),
        sa.Column("low", sa.Numeric(15, 2)),
        sa.Column("close", sa.Numeric(15, 2)),
        sa.Column("volume", sa.BigInteger),
        sa.Column("value", sa.BigInteger),
        sa.Column("foreign_buy", sa.BigInteger),
        sa.Column("foreign_sell", sa.BigInteger),
        sa.Column("foreign_net", sa.BigInteger),
    )
    op.create_index("idx_ohlcv_date", "ohlcv_daily", ["date"])

    op.create_table(
        "regime_history",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("regime", sa.String(50)),
        sa.Column("confidence", sa.Numeric(5, 2)),
        sa.Column("breadth_ratio", sa.Numeric(5, 2)),
        sa.Column("foreign_flow_5d", sa.BigInteger),
        sa.Column("sbn_yield", sa.Numeric(5, 2)),
        sa.Column("usd_idr", sa.Numeric(10, 2)),
        sa.Column("raw_score", sa.Numeric(5, 3)),
        sa.Column("metadata", postgresql.JSONB),
    )

    op.create_table(
        "signal_cache",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("composite_score", sa.Numeric(5, 3)),
        sa.Column("indicators", postgresql.JSONB),
        sa.Column("foreign_signal", sa.String(50)),
        sa.Column("bandar_phase", sa.String(50)),
        sa.Column("bandar_score", sa.Integer),
        sa.Column("ai_predict", sa.Integer),
        sa.Column("narrative", sa.Text),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "fundamentals",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("per", sa.Numeric),
        sa.Column("pbv", sa.Numeric),
        sa.Column("roe", sa.Numeric),
        sa.Column("der", sa.Numeric),
        sa.Column("revenue_yoy", sa.Numeric),
        sa.Column("net_margin", sa.Numeric),
        sa.Column("quality_score", sa.Numeric),
        sa.Column("earnings_date", sa.Date),
        sa.Column("red_flags", postgresql.JSONB),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ticker", sa.String(10)),
        sa.Column("entry_price", sa.Numeric),
        sa.Column("exit_price", sa.Numeric),
        sa.Column("shares", sa.Integer),
        sa.Column("entry_date", sa.DateTime),
        sa.Column("exit_date", sa.DateTime),
        sa.Column("pnl_pct", sa.Numeric),
        sa.Column("source", sa.String(20)),
        sa.Column("notes", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("fundamentals")
    op.drop_table("signal_cache")
    op.drop_table("regime_history")
    op.drop_index("idx_ohlcv_date", table_name="ohlcv_daily")
    op.drop_table("ohlcv_daily")
    op.drop_table("stocks")
