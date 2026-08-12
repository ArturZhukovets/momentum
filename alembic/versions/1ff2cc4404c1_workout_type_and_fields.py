"""workout_type_and_fields

Revision ID: 1ff2cc4404c1
Revises: 85008e4d00a0
Create Date: 2026-08-10 00:01:03.722552

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ff2cc4404c1"
down_revision: str | Sequence[str] | None = "85008e4d00a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename kind→workout_type, add typed fields, drop photo + kind CHECK, backfill."""
    # Baseline ships an unnamed CHECK; a prior downgrade of this revision leaves
    # ``ck_workouts_kind``. Named ones must be dropped before the rename or the
    # rebuilt table keeps ``CHECK (kind IN ...)`` against a gone column.
    named_checks = [
        ck["name"]
        for ck in sa.inspect(op.get_bind()).get_check_constraints("workouts")
        if ck["name"]
    ]

    with op.batch_alter_table("workouts", schema=None) as batch_op:
        for name in named_checks:
            batch_op.drop_constraint(name, type_="check")
        batch_op.alter_column(
            "kind",
            new_column_name="workout_type",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.add_column(sa.Column("duration_min", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("distance_km", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("effort", sa.Text(), nullable=True))
        batch_op.drop_column("photo_file_id")

    op.execute(
        sa.text(
            """
            UPDATE workouts
            SET workout_type = CASE workout_type
                WHEN 'strength' THEN 'gym'
                WHEN 'cardio' THEN 'running'
                ELSE workout_type
            END
            """
        )
    )


def downgrade() -> None:
    """Restore kind/photo and the cardio|strength CHECK; map types back."""
    op.execute(
        sa.text(
            """
            UPDATE workouts
            SET workout_type = CASE workout_type
                WHEN 'gym' THEN 'strength'
                WHEN 'home_workout' THEN 'strength'
                WHEN 'running' THEN 'cardio'
                WHEN 'swimming' THEN 'cardio'
                WHEN 'elliptical' THEN 'cardio'
                ELSE workout_type
            END
            """
        )
    )

    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.alter_column(
            "workout_type",
            new_column_name="kind",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.add_column(sa.Column("photo_file_id", sa.Text(), nullable=True))
        batch_op.drop_column("effort")
        batch_op.drop_column("distance_km")
        batch_op.drop_column("duration_min")
        batch_op.create_check_constraint(
            "ck_workouts_kind",
            "kind IN ('cardio','strength')",
        )
