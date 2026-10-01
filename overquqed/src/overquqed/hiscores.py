"""Per-level top-5 hiscores with 3-letter team initials, plus best stars.

Stored as JSON outside the package folder (config.HISCORE_FILE), so a
redeploy keeps them. Pure logic apart from the file I/O, which never raises:
a missing or corrupt file just means an empty table.
"""

from __future__ import annotations

import json
from pathlib import Path

TOP_N = 5


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, indent=1))
    except OSError:
        pass


def table(data: dict, level_key: str) -> list[dict]:
    rows = data.get(level_key, {}).get("scores", [])
    return [r for r in rows if isinstance(r, dict) and "score" in r][:TOP_N]


def best_stars(data: dict, level_key: str) -> int:
    return int(data.get(level_key, {}).get("stars", 0))


def qualifies(data: dict, level_key: str, score: int) -> bool:
    rows = table(data, level_key)
    return score > 0 and (len(rows) < TOP_N or score > rows[-1]["score"])


def insert(data: dict, level_key: str, name: str, score: int, stars: int) -> int:
    """Add an entry (if it makes the table) and record stars. Returns the
    0-based rank, or -1 if it didn't make the top 5."""
    entry = data.setdefault(level_key, {})
    entry["stars"] = max(int(entry.get("stars", 0)), stars)
    rows = table(data, level_key)
    if not qualifies(data, level_key, score):
        return -1
    new = {"name": name[:3].upper(), "score": int(score)}
    rows.append(new)
    rows.sort(key=lambda r: -r["score"])  # stable: earlier equal scores stay above
    entry["scores"] = rows[:TOP_N]
    return next(i for i, r in enumerate(entry["scores"]) if r is new)
