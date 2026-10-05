"""The solo time-trial table: the fastest TIMES_SLOTS clears (name, seconds),
fastest first, kept as JSON outside the package folder so a redeploy doesn't
wipe it. Adapted from Gate Drop's hiscores.py.

A missing or broken file just means an empty table, and a failed save is
ignored: a cabinet must never crash over its scoreboard. Pass path=None for a
table that only lives in memory (the tests).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from quantum_towers import config
from quantum_towers.solo import format_time


@dataclass
class Entry:
    name: str
    seconds: float


class Times:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.entries: list[Entry] = self._load()

    def _load(self) -> list[Entry]:
        if self.path is None:
            return []
        try:
            raw = json.loads(self.path.read_text())
            entries = [Entry(str(e["name"]), float(e["seconds"])) for e in raw]
        except (OSError, ValueError, TypeError, KeyError):
            return []
        return sorted(entries, key=lambda e: e.seconds)[: config.TIMES_SLOTS]

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.write_text(json.dumps([asdict(e) for e in self.entries]))
        except OSError:
            pass

    def qualifies(self, seconds: float) -> bool:
        if seconds <= 0:
            return False
        return len(self.entries) < config.TIMES_SLOTS or seconds < self.entries[-1].seconds

    def add(self, name: str, seconds: float) -> int:
        """Insert an entry (below any equal time) and save. Returns its rank,
        or -1 if it didn't make the table."""
        rank = next((i for i, e in enumerate(self.entries) if seconds < e.seconds), len(self.entries))
        if rank >= config.TIMES_SLOTS:
            return -1
        self.entries.insert(rank, Entry(name, seconds))
        del self.entries[config.TIMES_SLOTS:]
        self._save()
        return rank

    @staticmethod
    def format_time(seconds: float) -> str:
        return format_time(seconds)
