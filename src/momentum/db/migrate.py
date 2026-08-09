"""Runs Alembic migrations at startup, before the engine is built.

A personal single-instance bot, so migrating at boot is safe and keeps the
Docker deploy a plain ``docker compose up`` — there is no second process that
could race this one. A fresh install gets the whole schema; an existing one
gets whatever revisions it is missing.

Alembic's ``command`` API is synchronous, so it runs in a worker thread rather
than blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic.config import Config

from alembic import command
from momentum.config import PROJECT_ROOT, settings

log = logging.getLogger(__name__)

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def _config() -> Config:
    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"alembic.ini not found at {ALEMBIC_INI}")
    return Config(ALEMBIC_INI)


def _migrate_sync() -> None:
    command.upgrade(_config(), "head")  # alembic/env.py takes the URL from settings.


async def upgrade_to_head() -> None:
    db_file: Path = settings.db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(_migrate_sync)
    log.info("Schema is at head")
