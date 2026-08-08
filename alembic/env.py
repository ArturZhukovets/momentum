"""Alembic environment.

The URL comes from ``momentum.config.settings``, not from ``alembic.ini`` —
one source of truth for where the DB lives, so the CLI and the at-boot
``db.migrate.upgrade_to_head()`` can never disagree.

``render_as_batch=True`` matters: SQLite can't ALTER most things, and batch
mode is what lets a migration rename or retype a column at all.

Note that batch mode rebuilds a table from its *reflected* DDL, and SQLAlchemy's
SQLite reflector cannot read ``ON DELETE`` from the inline
``REFERENCES users(user_id) ON DELETE CASCADE`` column syntax — only from a
table-level ``FOREIGN KEY``. Every table here is created by a migration, so the
DDL is always the table-level spelling and the cascade survives. A database
built by some other means must be rebuilt (see docs/db-rebuild.md) before it is
migrated, or batch mode will quietly drop its cascades.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from alembic import context
from momentum.config import settings
from momentum.db.tables import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Sync driver on purpose: migrations run either from the CLI or from a worker
# thread inside the app, and neither needs async here.
DB_URL = f"sqlite:///{settings.db_file}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it against a database."""
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        {"sqlalchemy.url": DB_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        do_run_migrations(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
