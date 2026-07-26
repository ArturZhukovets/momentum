"""Single shared aiosqlite connection + migrate-on-start.

Three settings are applied before the connection is used:

* ``PRAGMA journal_mode=WAL`` — readers and the writer stop blocking each
  other, which matters when the scheduler's report broadcast overlaps with a
  user logging a workout.
* ``PRAGMA foreign_keys=ON`` — SQLite ignores REFERENCES unless this is
  enabled *per connection*; without it ON DELETE CASCADE silently does nothing.
* ``row_factory = aiosqlite.Row`` — rows become subscriptable by column name.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from momentum.config import settings

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_conn: aiosqlite.Connection | None = None


def conn() -> aiosqlite.Connection:
    """The shared connection. Raises if the DB was never initialised."""
    if _conn is None:
        raise RuntimeError("Database is not initialised — call init_db() first")
    return _conn


async def init_db() -> aiosqlite.Connection:
    global _conn

    db_file = settings.db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)

    _conn = await aiosqlite.connect(db_file)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")

    await _conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    await _conn.commit()

    log.info("Database ready at %s", db_file)
    return _conn


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
