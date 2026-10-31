"""Which release notes to show — pure: version strings in, version strings out."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version


def current_version() -> str | None:
    """The installed `momentum` version, i.e. the one in `pyproject.toml`."""
    try:
        return version("momentum")
    except PackageNotFoundError:
        return None


def _key(v: str) -> tuple[int, ...]:
    return tuple(int(part) for part in v.split(".") if part.isdigit())


def newest_first(versions: Iterable[str]) -> list[str]:
    return sorted(versions, key=_key, reverse=True)


def default_version(available: Iterable[str], running: str | None) -> str | None:
    """The running version if it has notes, else the newest one that does.

    So a release shipped without its notes still opens on something, and notes
    written ahead of a deploy stay hidden until that version actually runs.
    """
    ordered = newest_first(available)
    if running is not None and running in ordered:
        return running
    if running is not None:
        ordered = [v for v in ordered if _key(v) <= _key(running)]
    return ordered[0] if ordered else None


def visible_versions(available: Iterable[str], running: str | None) -> list[str]:
    """Every version with notes, newest first, none newer than the running one."""
    ordered = newest_first(available)
    if running is None:
        return ordered
    return [v for v in ordered if _key(v) <= _key(running)]
