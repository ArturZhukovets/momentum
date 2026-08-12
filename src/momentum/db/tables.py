"""Declarative ORM models — the schema Alembic autogenerates from.

These are *not* what ``db/`` returns: every query maps rows into the frozen
dataclasses in :mod:`momentum.db.models` before handing them up, so nothing
above ``db/`` ever holds a live ORM instance.

Column types deliberately mirror what SQLite already stores:

* ``created_at`` / ``updated_at`` are ``Text``, not ``DateTime`` — they hold
  ``now_iso()`` output (``2026-08-07T10:00:00+02:00``), which SQLAlchemy's
  SQLite ``DateTime`` cannot parse.
* ``performed_on`` / ``birth_date`` / ``recorded_on`` are ``Date``: SQLAlchemy
  writes ``'YYYY-MM-DD'``, byte-identical to the existing rows.
* ``reports_on`` / ``is_active`` are ``Boolean`` over the existing INTEGER 0/1.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """Telegram identity only — written solely by ``common.UserMiddleware``."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    reports_on: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Workout(Base):
    __tablename__ = "workouts"
    __table_args__ = (
        Index("ix_workouts_user_date", "user_id", "performed_on"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    workout_type: Mapped[str] = mapped_column(Text, nullable=False)
    performed_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    distance_km: Mapped[float | None] = mapped_column(Float)
    effort: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class WorkoutBodyPart(Base):
    __tablename__ = "workout_body_parts"

    workout_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workouts.id", ondelete="CASCADE"), primary_key=True
    )
    body_part: Mapped[str] = mapped_column(Text, primary_key=True)


class ImprovementRequest(Base):
    __tablename__ = "improvement_requests"
    __table_args__ = (
        CheckConstraint("length(trim(request_text)) > 0"),
        CheckConstraint("status IN ('new','done','rejected')"),
        Index("ix_improvement_requests_status_created", "status", "created_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    user_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class UserProfile(Base):
    """Everything the bot *asks* the user — never in ``users``."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("sex IN ('male','female')"),
        CheckConstraint("height_cm IS NULL OR height_cm > 0"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    sex: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UserGoal(Base):
    __tablename__ = "user_goals"
    __table_args__ = (
        CheckConstraint("goal_type IN ('lose','gain','maintain','muscle')"),
        CheckConstraint("start_weight_kg IS NULL OR start_weight_kg > 0"),
        CheckConstraint("target_weight_kg IS NULL OR target_weight_kg > 0"),
        # One active goal per user; a second insert raises IntegrityError.
        Index("ux_user_goals_active", "user_id", unique=True, sqlite_where=text("is_active = 1")),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    goal_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_weight_kg: Mapped[float | None] = mapped_column(Float)
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    target_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class BodyMeasurement(Base):
    """Append-only history — several rows per day are fine."""

    __tablename__ = "body_measurements"
    __table_args__ = (
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0"),
        Index("ix_body_measurements_user_date", "user_id", "recorded_on"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    chest_cm: Mapped[float | None] = mapped_column(Float)
    hips_cm: Mapped[float | None] = mapped_column(Float)
    thigh_cm: Mapped[float | None] = mapped_column(Float)
    arm_cm: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
