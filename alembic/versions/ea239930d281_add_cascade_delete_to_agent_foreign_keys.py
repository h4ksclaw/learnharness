"""add cascade delete to all foreign keys

Revision ID: ea239930d281
Revises: 4a16109d2f85
Create Date: 2026-07-12 12:36:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea239930d281"
down_revision: str | Sequence[str] | None = "4a16109d2f85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _cascade(op, table, column, ref_table, ref_column="id"):
    """Drop and recreate a FK with ON DELETE CASCADE."""
    constraint = f"{table}_{column}_fkey"
    op.drop_constraint(constraint, table, type_="foreignkey")
    op.create_foreign_key(
        constraint,
        table,
        ref_table,
        [column],
        [ref_column],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    """Add ON DELETE CASCADE to all FK constraints."""
    # agents → everything that references agents.id
    _cascade(op, "learners", "agent_id", "agents")
    _cascade(op, "concepts", "agent_id", "agents")
    _cascade(op, "interactions", "agent_id", "agents")
    _cascade(op, "interactions", "learner_id", "learners")
    _cascade(op, "outbound_messages", "agent_id", "agents")
    _cascade(op, "outbound_messages", "learner_id", "learners")

    # concepts → everything that references concepts.id
    _cascade(op, "concept_edges", "source_id", "concepts")
    _cascade(op, "concept_edges", "target_id", "concepts")
    _cascade(op, "mastery", "concept_id", "concepts")
    _cascade(op, "review_items", "concept_id", "concepts")
    _cascade(op, "error_patterns", "concept_id", "concepts")

    # learners → everything that references learners.id
    _cascade(op, "mastery", "learner_id", "learners")
    _cascade(op, "review_items", "learner_id", "learners")
    _cascade(op, "error_patterns", "learner_id", "learners")


def downgrade() -> None:
    """Restore FK constraints without CASCADE."""
    constraints = [
        ("error_patterns", "learner_id", "learners"),
        ("review_items", "learner_id", "learners"),
        ("mastery", "learner_id", "learners"),
        ("error_patterns", "concept_id", "concepts"),
        ("review_items", "concept_id", "concepts"),
        ("mastery", "concept_id", "concepts"),
        ("concept_edges", "target_id", "concepts"),
        ("concept_edges", "source_id", "concepts"),
        ("outbound_messages", "learner_id", "learners"),
        ("outbound_messages", "agent_id", "agents"),
        ("interactions", "learner_id", "learners"),
        ("interactions", "agent_id", "agents"),
        ("concepts", "agent_id", "agents"),
        ("learners", "agent_id", "agents"),
    ]
    for table, column, ref_table in constraints:
        constraint = f"{table}_{column}_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, ref_table, [column], ["id"])
