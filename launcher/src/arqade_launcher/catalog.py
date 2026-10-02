"""Which games exist, and how the menu shows them.

Games are discovered, not listed: any folder in the repo with a
`pyproject.toml` and a `src/<package>/main.py` (package = folder name with
dashes as underscores) is a game, so a new one shows up without touching the
launcher. Its menu name, description and order come from
`batocera/gamelist.xml` -- the same text the cabinet's menu shows -- with the
pyproject's description as the fallback for games not listed there yet.
"""

from __future__ import annotations

import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Game:
    package: str  # e.g. "quantum_towers"
    project_dir: Path  # e.g. <repo>/quantum-towers
    name: str  # e.g. "Qlimbers"
    description: str
    art: Path | None  # square logo, or None for a generated placeholder

    @property
    def src_dir(self) -> Path:
        return self.project_dir / "src"


def _read_gamelist(path: Path) -> dict[str, tuple[int, str, str]]:
    """package -> (menu position, name, description)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    listed = {}
    for position, game in enumerate(root.iter("game")):
        rom = Path((game.findtext("path") or "").strip()).stem
        if rom:
            listed[rom] = (position, (game.findtext("name") or "").strip(),
                           (game.findtext("desc") or "").strip())
    return listed


def _pyproject_description(project_dir: Path) -> str:
    try:
        data = tomllib.loads((project_dir / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(data.get("project", {}).get("description", ""))


def _find_art(root: Path, package: str) -> Path | None:
    for candidate in (root / "batocera" / "logos" / f"{package}-logo.png",
                      root / "batocera" / "icons" / f"{package}-image.png"):
        if candidate.is_file():
            return candidate
    return None


def discover(root: Path = REPO_ROOT) -> list[Game]:
    listed = _read_gamelist(root / "batocera" / "gamelist.xml")
    games = []
    for project_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        package = project_dir.name.replace("-", "_")
        if not ((project_dir / "pyproject.toml").is_file()
                and (project_dir / "src" / package / "main.py").is_file()):
            continue
        _, name, description = listed.get(package, (None, "", ""))
        games.append(Game(
            package=package,
            project_dir=project_dir,
            name=name or package.replace("_", " ").title(),
            description=description or _pyproject_description(project_dir),
            art=_find_art(root, package),
        ))
    # gamelist.xml order first (the cabinet's menu order), then the rest by name.
    unlisted = len(listed)
    games.sort(key=lambda g: (listed.get(g.package, (unlisted,))[0], g.name.lower()))
    return games
