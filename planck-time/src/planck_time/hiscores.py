"""The single-player high-score table: the top HISCORE_SLOTS (name, score,
level), kept as JSON outside the package folder so a redeploy doesn't wipe it.

A missing or broken file just means an empty table, and a failed save is
ignored: a cabinet must never crash over its scoreboard. Pass path=None for a
table that only lives in memory (the tests).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from planck_time import config


@dataclass
class Entry:
    name: str
    score: int
    level: int


class Hiscores:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.entries: list[Entry] = self._load()

    def _load(self) -> list[Entry]:
        if self.path is None:
            return []
        try:
            raw = json.loads(self.path.read_text())
            entries = [Entry(str(e["name"]), int(e["score"]), int(e["level"])) for e in raw]
        except (OSError, ValueError, TypeError, KeyError):
            return []
        return sorted(entries, key=lambda e: -e.score)[: config.HISCORE_SLOTS]

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.write_text(json.dumps([asdict(e) for e in self.entries]))
        except OSError:
            pass

    def qualifies(self, score: int) -> bool:
        if score <= 0:
            return False
        return len(self.entries) < config.HISCORE_SLOTS or score > self.entries[-1].score

    def add(self, name: str, score: int, level: int) -> int:
        """Insert an entry (below any equal score) and save. Returns its rank,
        or -1 if it didn't make the table."""
        rank = next((i for i, e in enumerate(self.entries) if score > e.score), len(self.entries))
        if rank >= config.HISCORE_SLOTS:
            return -1
        self.entries.insert(rank, Entry(name, score, level))
        del self.entries[config.HISCORE_SLOTS:]
        self._save()
        return rank
