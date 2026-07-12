"""expand error_type and category columns to text

Revision ID: b09b2c3eebf2
Revises: ea239930d281
Create Date: 2026-07-12 15:35:00.000000

LLM-generated correction rules and concept categories can exceed
varchar(100), causing StringDataRightTruncationError on chat.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b09b2c3eebf2"
down_revision: str | Sequence[str] | None = "ea239930d281"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "error_patterns",
        "error_type",
        type_=sa.Text(),
        existing_type=sa.String(100),
    )
    op.alter_column(
        "concepts",
        "category",
        type_=sa.Text(),
        existing_type=sa.String(100),
    )


def downgrade() -> None:
    op.alter_column(
        "concepts",
        "category",
        type_=sa.String(100),
        existing_type=sa.Text(),
    )
    op.alter_column(
        "error_patterns",
        "error_type",
        type_=sa.String(100),
        existing_type=sa.Text(),
    )
