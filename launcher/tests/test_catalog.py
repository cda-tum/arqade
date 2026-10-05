import tomllib
from pathlib import Path

from arqade_launcher import catalog

LAUNCHER = Path(__file__).resolve().parents[1]


def make_game(root: Path, folder: str, description: str = "") -> None:
    package = folder.replace("-", "_")
    (root / folder / "src" / package).mkdir(parents=True)
    (root / folder / "src" / package / "main.py").write_text("def main(argv=None): pass\n")
    (root / folder / "pyproject.toml").write_text(
        f'[project]\nname = "{folder}"\ndescription = "{description}"\n')


def test_finds_every_game_in_the_repo():
    games = catalog.discover()
    packages = {g.package for g in games}
    expected = {p.name.replace("-", "_") for p in catalog.REPO_ROOT.iterdir()
                if (p / "src" / p.name.replace("-", "_") / "main.py").is_file()}
    assert packages == expected
    assert "quantum_towers" in packages
    assert all(g.src_dir.is_dir() for g in games)


def test_names_and_order_come_from_gamelist(tmp_path):
    make_game(tmp_path, "zeta-game", "from pyproject")
    make_game(tmp_path, "alpha-game")
    make_game(tmp_path, "beta")
    (tmp_path / "batocera").mkdir()
    (tmp_path / "batocera" / "gamelist.xml").write_text(
        "<gameList><game><path>./zeta_game.pygame</path><name>Zeta</name><desc>Listed.</desc></game>"
        "</gameList>")
    (tmp_path / "not-a-game").mkdir()
    games = catalog.discover(tmp_path)
    assert [g.name for g in games] == ["Zeta", "Alpha Game", "Beta"]
    assert games[0].description == "Listed."
    assert games[0].art is None


def test_unlisted_games_fall_back_to_the_pyproject_description(tmp_path):
    make_game(tmp_path, "new-game", "A new game")
    (game,) = catalog.discover(tmp_path)
    assert game.description == "A new game"


def test_art_prefers_the_logo_over_the_icon(tmp_path):
    make_game(tmp_path, "g")
    for folder, name in (("logos", "g-logo.png"), ("icons", "g-image.png")):
        (tmp_path / "batocera" / folder).mkdir(parents=True)
        (tmp_path / "batocera" / folder / name).write_bytes(b"")
    assert catalog.discover(tmp_path)[0].art.name == "g-logo.png"


def _deps(pyproject: Path) -> set[str]:
    data = tomllib.loads(pyproject.read_text())
    return set(data["project"].get("dependencies", []))


def test_launcher_environment_has_every_games_dependencies():
    # All games run in the launcher's interpreter, so it must carry them all.
    launcher = _deps(LAUNCHER / "pyproject.toml")
    for game in catalog.discover():
        missing = _deps(game.project_dir / "pyproject.toml") - launcher
        assert not missing, f"{game.package} needs {missing}; add it to launcher/pyproject.toml"
