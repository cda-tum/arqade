"""Allows `python -m qarrera` in addition to `python -m qarrera.main`."""

import asyncio

from qarrera.main import main

asyncio.run(main())
