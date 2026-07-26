from __future__ import annotations

import asyncio
import contextlib

from momentum.app import main

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
