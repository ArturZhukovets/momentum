"""Rendering of workout cards, reports, and admin cards (HTML parse mode).

All literal copy comes from the ``texts`` package — these modules only
assemble it. Submodules are per-resource (``workout``, ``reports``,
``suggestions``, ``users``, ``measurements``) — import the one you need, e.g.
``from momentum.formatters import workout as fmt_workout``.
"""

from __future__ import annotations
