"""report comments cache

Adds `report_comments`: the coach comment last written for one report period,
keyed by `(user_id, kind, period_start)` and reused while `facts_hash` still
matches. A new table only — no existing table is touched. The FK is a table-level
`FOREIGN KEY ... ON DELETE CASCADE`, so a later batch rebuild keeps the cascade.

Revision ID: 349425801160
Revises: c907f1cfba16
Create Date: 2026-09-26 17:11:36.054479

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "349425801160"
down_revision: str | Sequence[str] | None = "c907f1cfba16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "report_comments",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("facts_hash", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('week','month')"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "kind", "period_start"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("report_comments")
