"""goal rate instead of target date

Replaces the never-asked `user_goals.target_date` with `target_rate_kg_per_month`.
The table is rebuilt from `copy_from` — a hand-written definition of the current
table — rather than from SQLite reflection, which would drop the unnamed CHECKs and
could lose the `WHERE is_active = 1` of `ux_user_goals_active`. The FK stays a
table-level `FOREIGN KEY ... ON DELETE CASCADE`.

Downgrade drops the chosen rates: nothing maps a pace back onto a date.

Revision ID: 4e6acbff6425
Revises: f57117eb9e9a
Create Date: 2026-09-26 15:36:13.026793

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e6acbff6425"
down_revision: str | Sequence[str] | None = "f57117eb9e9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RATE_CHECK_NAME = "ck_user_goals_target_rate_positive"
RATE_CHECK = "target_rate_kg_per_month IS NULL OR target_rate_kg_per_month > 0"


def _user_goals(goal_column: sa.Column, *extra: sa.schema.SchemaItem) -> sa.Table:
    """`user_goals` with `goal_column` after `target_weight_kg`, plus `extra` constraints."""
    return sa.Table(
        "user_goals",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goal_type", sa.Text(), nullable=False),
        sa.Column("start_weight_kg", sa.Float(), nullable=True),
        sa.Column("target_weight_kg", sa.Float(), nullable=True),
        goal_column,
        sa.Column("note", sa.Text(), server_default=sa.text("('')"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("goal_type IN ('lose','gain','maintain','muscle')"),
        sa.CheckConstraint("start_weight_kg IS NULL OR start_weight_kg > 0"),
        sa.CheckConstraint("target_weight_kg IS NULL OR target_weight_kg > 0"),
        *extra,
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index(
            "ux_user_goals_active", "user_id", unique=True, sqlite_where=sa.text("is_active = 1")
        ),
        sqlite_autoincrement=True,
    )


def upgrade() -> None:
    """Drop target_date, add target_rate_kg_per_month with its positive CHECK."""
    with op.batch_alter_table(
        "user_goals",
        schema=None,
        copy_from=_user_goals(sa.Column("target_date", sa.Date(), nullable=True)),
        recreate="always",
    ) as batch_op:
        batch_op.drop_column("target_date")
        batch_op.add_column(
            sa.Column("target_rate_kg_per_month", sa.Float(), nullable=True),
            insert_after="target_weight_kg",
        )
        batch_op.create_check_constraint(RATE_CHECK_NAME, RATE_CHECK)


def downgrade() -> None:
    """Restore an empty target_date in its old place; the rates are lost."""
    with op.batch_alter_table(
        "user_goals",
        schema=None,
        copy_from=_user_goals(
            sa.Column("target_rate_kg_per_month", sa.Float(), nullable=True),
            sa.CheckConstraint(RATE_CHECK, name=RATE_CHECK_NAME),
        ),
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(RATE_CHECK_NAME, type_="check")
        batch_op.drop_column("target_rate_kg_per_month")
        batch_op.add_column(
            sa.Column("target_date", sa.Date(), nullable=True),
            insert_after="target_weight_kg",
        )
