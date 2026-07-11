"""remove llm_model from agents

Revision ID: 4a16109d2f85
Revises: 311d23cd8df3
Create Date: 2026-07-11 16:54:54.546329

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a16109d2f85"
down_revision: str | Sequence[str] | None = "311d23cd8df3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove llm_model column from agents."""
    op.drop_column("agents", "llm_model")


def downgrade() -> None:
    """Restore llm_model column to agents."""
    op.add_column("agents", sa.Column("llm_model", sa.String(100), nullable=True))
