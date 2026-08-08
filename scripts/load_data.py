"""Replays a dump from ``dump_data.py`` into a freshly built database.

The target must already have its schema — that is, ``alembic upgrade head`` has
run — and must still be empty. Refusing a non-empty target is deliberate: the
dump carries explicit primary keys, so replaying it twice would either collide
or duplicate history.

Usage::

    uv run python scripts/load_data.py backup.sql
    uv run python scripts/load_data.py backup.sql --db path/to.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # run as a file, not a package
from dump_data import TABLES  # noqa: E402


def load(db_file: Path, dump_file: Path) -> None:
    if not db_file.is_file():
        raise SystemExit(f"No database at {db_file} — run `alembic upgrade head` first")
    if not dump_file.is_file():
        raise SystemExit(f"No dump at {dump_file}")

    conn = sqlite3.connect(db_file)
    present = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = [t for t in (*TABLES, "alembic_version") if t not in present]
    if missing:
        raise SystemExit(f"{db_file} is missing table(s): {', '.join(missing)}")

    non_empty = [t for t in TABLES if conn.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone()]  # noqa: S608
    if non_empty:
        raise SystemExit(f"{db_file} already holds rows in: {', '.join(non_empty)} — refusing")

    conn.executescript(dump_file.read_text(encoding="utf-8"))
    conn.commit()

    counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}  # noqa: S608
    bad = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    if bad:
        raise SystemExit(f"foreign key check failed after load: {bad}")

    for table, count in counts.items():
        print(f"  {table}: {count}", file=sys.stderr)
    print(f"loaded {sum(counts.values())} row(s), foreign keys clean", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path, help="the .sql file from dump_data.py")
    parser.add_argument("--db", type=Path, default=None, help="defaults to settings.db_file")
    args = parser.parse_args()

    db_file = args.db
    if db_file is None:
        from momentum.config import settings

        db_file = settings.db_file

    load(db_file, args.dump)


if __name__ == "__main__":
    main()
