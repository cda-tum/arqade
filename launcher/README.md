# ARQADE launcher

Every game in this repo behind one menu, on an ordinary PC: a fullscreen
carousel of the games, a loading card with the spinning ARQADE logo and the
controls, an attract reel when nobody is playing, and a settings menu where
you set which keyboard keys act as the cabinet's two pads. It plays the role
EmulationStation plays on the Batocera cabinet, without Batocera.

```bash
./arqade.sh              # from the repo root (Windows: arqade.cmd)
./arqade.sh --windowed   # in a window, this session only
./arqade.sh --kiosk      # for public demos: no quitting or settings from the menu
./arqade.sh --list       # just list the games it found
```

The first run creates `launcher/.venv` (Python 3.11, pygame 2.5.2, numpy,
imageio-ffmpeg) with
[uv](https://docs.astral.sh/uv/). Without the script: `uv run --project launcher arqade`.

## In the menu

| Key | Does |
|---|---|
| Left / Right, or either pad's stick | choose a game |
| Enter, Space, or either pad's A or Start | play |
| Tab, or either pad's Select | settings |
| Esc / Backspace, or either pad's B | back; on the main menu, quit (asks first) |
| F11 | fullscreen / window |
| Ctrl+Q | quit straight away (also in kiosk mode) |
| mouse | wheel scrolls, click picks, click the centre game to play |

**After 15 s without input the menu plays the attract reels**, the same ones
the cabinet shows as its screensaver (`batocera/attract/reels/`), one at
random after another. Any key or click brings the menu back and does nothing
else. **Settings → Attract mode** turns it off.

**In a game, Esc always goes back to the menu**, whatever the game's own
controls. If a game crashes, the menu says so with the last error line; the
full traceback is in the terminal the launcher was started from.

## Keyboard as cabinet pads

All the games are written for the cabinet's two joystick pads. The launcher
makes the keyboard *be* those two pads, so one key mapping works the same in
every game, and the same way as on the cabinet: Start starts, A confirms,
B goes back, the stick is an analog axis. The defaults put two players on one
keyboard, using only keys that sit in the same place on QWERTY and QWERTZ:

| | Stick | L X R (top row) | Y B A (bottom row) | Start | Select |
|---|---|---|---|---|---|
| **P1** (left, blue) | W A S D | F G H | V B N | 1 | 2 |
| **P2** (right, red) | arrow keys | U I O | J K L | Enter | Right Shift |

Change them under **Settings → Player 1 keys / Player 2 keys**. The pad is
drawn live and lights up as you press keys, so you can test the mapping there.
*Assign all in turn* asks for all twelve keys one after another. A key does one
job only: give it to a second action and the first one is left unset. Esc can't
be bound.

**Settings → Game controls** switches this off: each game then reads the
keyboard its own way, as when it's run on its own during development, and real
gamepads pass straight through to the games.

Settings are saved to `~/.config/arqade/settings.json` (`%APPDATA%\arqade` on
Windows). Hand-editing is fine; anything unreadable falls back to the defaults.

## How it works

- **Games are discovered, not listed.** Any repo folder with a
  `pyproject.toml` and `src/<package>/main.py` is a game (package = folder name,
  dashes as underscores). Names, descriptions and order come from
  `batocera/gamelist.xml`, so they match the cabinet's menu. The tile art is
  `batocera/logos/<package>-logo.png`, then `batocera/icons/<package>-image.png`.
  A game with neither gets its name on a gradient.
- **Each game runs in its own process**, as on the cabinet: `runner.py` starts
  `python -m arqade_launcher.child <src> <package> <args>`, which imports the
  game and calls its `main()` with the same flags the cabinet's loader uses
  (`--fullscreen` or `--window-size`, plus `--no-keyboard` when the keyboard is
  driving the pads, and `--fps` when that's on). The menu closes its own window
  while the game runs.
- **The pads** (`child.py`): before the game is imported, `pygame.joystick`
  is swapped for two virtual joysticks driven by the keyboard, and
  `pygame.event.get` is wrapped. Key presses come out as the matching
  JOYBUTTON and JOYAXIS events, using the cabinet's raw button numbers. Polling
  `get_button()` and `get_axis()` sees the same state. Real joysticks are hidden
  while this is on. Esc ends the game from inside that same wrapper.
- **Video** (`video.py`): pygame cannot decode video, so the reels and the
  spinning logo (`logos/animation/arqade_loading_v3_1080p.webm`) are decoded
  by imageio-ffmpeg's bundled ffmpeg in a background thread. Without it, or
  without the files, the menu has no attract mode and the loading card shows
  the game's logo instead.
- **One environment for all games.** Every game runs in the launcher's Python,
  so `pyproject.toml` here lists every game's dependencies. A test fails when a
  game adds one the launcher doesn't have.

The menu draws at the screen's own resolution in units of a 960x540 layout,
letterboxed to 16:9, so it stays sharp from 1366x768 to 4K.

## Tests

```bash
cd launcher && uv run pytest
```

The tests run headless. They cover discovery, settings, the virtual pads, the
menu flow with a stand-in for the game process, the attract mode with a
stand-in for the video player, and one real subprocess launch of a stand-in
game. No test starts ffmpeg.
