"""The async engine + session factory.

Two PRAGMAs are re-applied on *every* pooled connection via a ``connect``
event hook, not once at startup — both are per-connection settings, so a
connection the pool opens later would otherwise come up without them:

* ``PRAGMA foreign_keys=ON`` — SQLite ignores REFERENCES unless this is
  enabled per connection; without it ON DELETE CASCADE silently does nothing.
* ``PRAGMA journal_mode=WAL`` — readers and the writer stop blocking each
  other, which matters when the scheduler's report broadcast overlaps with a
  user logging a workout.

Sessions are per db-function: each function in the sibling modules opens
``async with new_session() as s:`` and commits. Nothing needs a
transaction spanning several of them.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from momentum.config import settings

log = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def engine() -> AsyncEngine:
    """The shared engine. Raises if the DB was never initialised."""
    if _engine is None:
        raise RuntimeError("Database is not initialised — call init_db() first")
    return _engine


def new_session() -> AsyncSession:
    """A fresh session. Raises if the DB was never initialised."""
    if _session_factory is None:
        raise RuntimeError("Database is not initialised — call init_db() first")
    return _session_factory()


def _apply_pragmas(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


async def init_db() -> AsyncEngine:
    """Build the engine and session factory. Schema is Alembic's job — see db/migrate.py."""
    global _engine, _session_factory

    db_file = settings.db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    event.listen(_engine.sync_engine, "connect", _apply_pragmas)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    log.info("Database ready at %s", db_file)
    return _engine


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
