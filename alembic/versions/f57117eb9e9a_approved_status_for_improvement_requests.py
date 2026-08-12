"""approved status for improvement requests

Adds the `approved` value to the improvement_requests status check constraint: a
suggestion now waits in `new` until the admin approves it. Autogenerate cannot diff an
unnamed CHECK, so the table is rebuilt by hand from `copy_from` — the new definition —
rather than from SQLite reflection, which would lose the ON DELETE CASCADE.

Revision ID: f57117eb9e9a
Revises: 1ff2cc4404c1
Create Date: 2026-08-12 20:54:45.277444

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f57117eb9e9a"
down_revision: str | Sequence[str] | None = "1ff2cc4404c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table(status_check: str) -> sa.Table:
    return sa.Table(
        "improvement_requests",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_full_name", sa.Text(), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'new'"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(status_check),
        sa.CheckConstraint("length(trim(request_text)) > 0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_improvement_requests_status_created", "status", "created_at"),
        sqlite_autoincrement=True,
    )


NEW_CHECK = "status IN ('new','approved','done','rejected')"
OLD_CHECK = "status IN ('new','done','rejected')"


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table(
        "improvement_requests",
        schema=None,
        copy_from=_table(NEW_CHECK),
        recreate="always",
    ):
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Rows the new status introduced would violate the old constraint.
    op.execute("UPDATE improvement_requests SET status = 'new' WHERE status = 'approved'")
    with op.batch_alter_table(
        "improvement_requests",
        schema=None,
        copy_from=_table(OLD_CHECK),
        recreate="always",
    ):
        pass
