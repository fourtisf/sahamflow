"""add stop_loss / take_profit / signal_source to trades

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("stop_loss", sa.Numeric))
    op.add_column("trades", sa.Column("take_profit", sa.Numeric))
    op.add_column("trades", sa.Column("setup", sa.String(80)))
    op.add_column("trades", sa.Column("invalidated_at", sa.DateTime))


def downgrade() -> None:
    op.drop_column("trades", "invalidated_at")
    op.drop_column("trades", "setup")
    op.drop_column("trades", "take_profit")
    op.drop_column("trades", "stop_loss")
