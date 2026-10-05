"""The solo time-trial table: the fastest TIMES_SLOTS clears (name, seconds),
fastest first, kept as JSON outside the package folder so a redeploy doesn't
wipe it. Adapted from Gate Drop's hiscores.py.

A missing or broken file just means an empty table, and a failed save is
ignored: a cabinet must never crash over its scoreboard. Pass path=None for a
table that only lives in memory (the tests).
"""

from __future__ import annotations

import json
import math
import os
import tempfile
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
        # A hand-edited or corrupted file must not put a NaN, infinite or
        # non-positive time on the board (NaN would also break the sort).
        entries = [e for e in entries if math.isfinite(e.seconds) and e.seconds > 0]
        return sorted(entries, key=lambda e: e.seconds)[: config.TIMES_SLOTS]

    def _save(self) -> None:
        if self.path is None:
            return
        # Write a temp file beside the table, then swap it in: a power cut
        # mid-save leaves the old table, never a half-written one.
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False
            ) as tmp:
                tmp_name = tmp.name
                tmp.write(json.dumps([asdict(e) for e in self.entries]))
                tmp.flush()
                os.fsync(tmp.fileno())
            os.chmod(tmp_name, 0o644)  # NamedTemporaryFile creates it 0600
            os.replace(tmp_name, self.path)
        except OSError:
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
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
