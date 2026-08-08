"""Dumps every row of the bot's tables as plain ``INSERT`` statements.

Data only — no ``CREATE TABLE``. The schema belongs to Alembic, so a dump taken
here can be replayed into a database that Alembic has just built from scratch.
That is the whole point: it lets the schema be rebuilt cleanly without the data
having to survive an in-place table rewrite.

Usage::

    uv run python scripts/dump_data.py                  # -> stdout
    uv run python scripts/dump_data.py -o backup.sql
    uv run python scripts/dump_data.py --db path/to.db

``alembic_version`` and ``sqlite_sequence`` are deliberately skipped: the first
is owned by the migration that builds the new database, and the second is
maintained by SQLite itself as the AUTOINCREMENT rows are re-inserted.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Parents before children — the dump is replayed with foreign keys enforced.
TABLES = (
    "users",
    "user_profiles",
    "user_goals",
    "workouts",
    "workout_body_parts",
    "body_measurements",
    "improvement_requests",
)


def _literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def dump(db_file: Path) -> str:
    if not db_file.is_file():
        raise SystemExit(f"No database at {db_file}")

    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    present = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }

    lines = [
        "-- momentum data dump (no schema; replay into an Alembic-built database)",
        f"-- source: {db_file}",
        "PRAGMA foreign_keys=OFF;",
        "BEGIN;",
    ]
    total = 0
    for table in TABLES:
        if table not in present:
            print(f"warning: table {table} missing from source, skipped", file=sys.stderr)
            continue
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — fixed list above
        lines.append(f"-- {table}: {len(rows)} row(s)")
        total += len(rows)
        for row in rows:
            keys = row.keys()  # sqlite3.Row membership tests values, so keep the list explicit
            columns = ", ".join(keys)
            values = ", ".join(_literal(row[key]) for key in keys)
            lines.append(f"INSERT INTO {table} ({columns}) VALUES ({values});")
    conn.close()

    lines += ["COMMIT;", "PRAGMA foreign_keys=ON;", ""]
    print(f"dumped {total} row(s) from {len(TABLES)} table(s)", file=sys.stderr)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="defaults to settings.db_file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="defaults to stdout")
    args = parser.parse_args()

    db_file = args.db
    if db_file is None:
        from momentum.config import settings

        db_file = settings.db_file

    sql = dump(db_file)
    if args.output:
        args.output.write_text(sql, encoding="utf-8")
        print(f"written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(sql)


if __name__ == "__main__":
    main()
