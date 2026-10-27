"""Allows `python -m overquqed` in addition to `python -m overquqed.main`."""

import asyncio

from overquqed.main import main

asyncio.run(main())
