"""nullable offline sequence number

Revision ID: c41e7b9d2a05
Revises: a93f06d2b714
Create Date: 2026-10-09 18:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "c41e7b9d2a05"
down_revision: str | Sequence[str] | None = "a93f06d2b714"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "offline_transactions",
        "sequence_number",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Rows parked for review after a sequence conflict have no sequence number;
    # they must be resolved (or removed) before this column can be NOT NULL again.
    op.alter_column(
        "offline_transactions",
        "sequence_number",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
