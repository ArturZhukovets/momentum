"""profile nudge timestamp on users

Adds `users.profile_nudge_at`: when the one-time "fill in your profile" line went
out in a report, so it is never repeated. Plain `ALTER TABLE ... ADD/DROP COLUMN`
instead of batch mode: an additive nullable column with no default needs no table
rebuild, so nothing about `users` is re-derived from reflection. `DROP COLUMN`
needs SQLite 3.35+.

Revision ID: c907f1cfba16
Revises: 4e6acbff6425
Create Date: 2026-09-26 16:46:05.830938

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c907f1cfba16"
down_revision: str | Sequence[str] | None = "4e6acbff6425"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("profile_nudge_at", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "profile_nudge_at")
