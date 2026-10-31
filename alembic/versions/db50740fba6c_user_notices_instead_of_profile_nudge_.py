"""user notices instead of a profile nudge column

``user_notices`` is one row per notice already sent, keyed by ``(user_id, notice)``.
Anyone who already got the profile nudge (``users.profile_nudge_at``) is copied
across as ``notice = 'profile_nudge'`` — the ``PROFILE_NUDGE`` key in
``db/notices.py`` — with the same timestamp, so the report does not ask them
again. The column then goes away with ``DROP COLUMN``, not a batch rebuild of
``users``: a nullable column with no default needs no table copy, and a rebuild
would re-derive ``users`` from reflection.

The FK is a table-level ``FOREIGN KEY ... ON DELETE CASCADE``, so a later batch
rebuild keeps the cascade. SQLite's reflector does not read ``ON DELETE`` off an
inline ``REFERENCES``.

Downgrade writes ``profile_nudge`` rows back into ``profile_nudge_at`` and drops
the table. Any other notice key is lost on the way down and is not restored.

Revision ID: db50740fba6c
Revises: 349425801160
Create Date: 2026-09-26 18:13:41.265460

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db50740fba6c"
down_revision: str | Sequence[str] | None = "349425801160"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of ``db.notices.PROFILE_NUDGE``. A migration must not import it:
# renaming the constant later must not rewrite history.
_PROFILE_NUDGE = "profile_nudge"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_notices",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notice", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "notice"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO user_notices (user_id, notice, sent_at)
            SELECT user_id, :notice, profile_nudge_at
            FROM users
            WHERE profile_nudge_at IS NOT NULL
            """
        ).bindparams(notice=_PROFILE_NUDGE)
    )
    op.drop_column("users", "profile_nudge_at")


def downgrade() -> None:
    """Downgrade schema.

    Only ``profile_nudge`` is written back. Every other notice key disappears
    with the table.
    """
    op.add_column("users", sa.Column("profile_nudge_at", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET profile_nudge_at = (
                SELECT sent_at FROM user_notices
                WHERE user_notices.user_id = users.user_id
                  AND user_notices.notice = :notice
            )
            WHERE user_id IN (
                SELECT user_id FROM user_notices WHERE notice = :notice
            )
            """
        ).bindparams(notice=_PROFILE_NUDGE)
    )
    op.drop_table("user_notices")
