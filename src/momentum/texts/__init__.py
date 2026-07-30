"""Every user-facing string lives under this package — nothing is hardcoded in
handlers. Code, identifiers, comments and DB values stay in English; only the
string *contents* are Russian.

Submodules are per-resource (``common``, ``workout``, ``history``, ``reports``,
``suggestions``, ``admin``) — import the one you need, e.g.
``from momentum.texts import workout as texts_workout``.
"""

from __future__ import annotations
