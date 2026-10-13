# Attract reels and loading art

When nobody has touched the cabinet for 15 s, on the main menu or in the game
list, the screen turns into a little TV playing the attract reels: the ARQADE
logo turns three times with a blinking PRESS ANY BUTTON, then about 20 s of
rapid-fire cuts of real gameplay, every game at least once, with a steady
PRESS ANY BUTTON badge in the corner. Then another reel, picked at random, with
different moments. Any button or stick brings back the screen you were on,
and that press does nothing else. On the cabinet this is EmulationStation's
screensaver; the PC launcher (`../../launcher/`) plays the same files as its
attract mode.

The footage is real gameplay, recorded headless from each game's own code
and driven by bots that read the game's state, so the reels can be re-cut
whenever a game changes.

```bash
# from the repo root, with the launcher's environment (pygame, numpy, imageio-ffmpeg)
launcher/.venv/bin/python batocera/attract/capture.py quantum_pong   # -> clips/quantum_pong.mp4
launcher/.venv/bin/python batocera/attract/build_reel.py             # -> reels/arqade_reel_<n>.mp4
launcher/.venv/bin/python batocera/attract/build_trailer.py          # -> trailer/arqade_trailer.mp4
uv run --project launcher --with resvg-py batocera/attract/build_splash.py   # -> the loading-screen art
batocera/deploy_ui.sh                                                # -> the cabinet
```

## The pieces

| File | Does |
|---|---|
| `capture.py` | Runs one game headless with two bot-driven virtual pads and simulated 60 fps time, and records it: `clips/<rom>.mp4` (1920x1080, exactly what the panel shows), `clips/<rom>.wav` (its sound effects, in sync) and `clips/<rom>-sheet.png` to check it. Deterministic for a given `--seed`, so `--sound-only` adds the sound to a clip that is already there. |
| `bots/<rom>.py` | One bot per game: how to get from the title into a match, and how to play it well enough to look good. Also `SECONDS`, `SKIP` and `HIGHLIGHTS` (the best 2 s moments, as start times). |
| `build_reel.py` | Cuts `REELS` reels from the clips: the logo for `LOGO_TURNS` turns, then `CUTS` cuts of `CUT_SECONDS`, all on a CRT tube, with each game's marquee and the PRESS ANY BUTTON badge on top. Writes `reels/arqade_reel_<n>.mp4` and `reels-sheet.png`. |
| `build_trailer.py` | A ~40 s 1080p trailer with sound, from the same clips and their sound effects. The music is a placeholder from Batocera's menu music (Bolt Action, "Some Potential", 132 BPM), and the edit is `TIMELINE`, in beats, so every cut sits on one and the drop lands on a card. Music, TUM and MQT logos and their licences are in `trailer_assets/`. |
| `build_splash.py` | The boot video and splash stills from the logo spin (`logos/animation/arqade_loading_v3_1080p.webm`), and the menu's system logos from the flat logo (`logos/Arqade_logo.svg`), into `quantum-pong/batocera/arqade-theme/`. |

`clips/` is not committed: `capture.py` rebuilds it, and only the finished
reels are shipped.

## Adding a game

1. Write `bots/<rom>.py` (see `capture.py`'s docstring and the existing
   bots). Read the game's state through `pads.loop` rather than playing
   blind; never press Start during play, because it pauses.
2. `capture.py <rom>`, look at the sheet, and iterate until the footage looks
   like a good match. Then list the 8 best moments in `HIGHLIGHTS`, varied
   and checked frame by frame. Without them the reels use the busiest
   stretches.
3. `build_reel.py`, look at `reels-sheet.png`, and deploy.

## Why it is built this way

These were checked against batocera-emulationstation's source (October 2026)
rather than assumed. Details are in `../kiosk.py` and in AGENTS.md.

- **Several short reels, not one long one.** ES plays a random `.mp4` from
  its screensaver folder, then another. Every reel is the logo plus one block
  of cuts, so each pick shows different moments. With four reels the same one
  comes back to back now and then; `--reels` makes more.
- **720p, not 1080p.** ES plays screensaver video through libVLC with
  software H.264 decoding on the Pi 4, then uploads every frame as an RGBA
  texture. A 1280x720 reel is about half the work of a 1080p one. ES scales it
  up to fill the panel. `--size 1920x1080` builds the other if the Pi turns
  out to manage.
- **A folder, not `<video>` tags in the gamelist.** ES's "random video"
  screensaver picks from every system's games, hidden systems included, and
  Batocera's bundled freeware ROMs come with videos. The custom video folder
  (`/userdata/screensaver`) plays only ours.
- **Every reel opens on the logo fading in from black.** Between files ES
  shows about half a second of black and fades the next one in. A reel that
  starts from black hides that seam.
- **It works from both menus, and waking never navigates.** ES's idle timer
  runs whatever the view, and cancelling the screensaver touches no view, so
  you land back on the carousel or in the game list, wherever you were.
- **The splash screens cannot animate.** ES draws its start-up and
  game-launch splashes as single frames and never updates their components,
  so a video or GIF there would show one frame. The spin plays where video
  does work: the boot splash (mpv) and these reels. Everywhere else shows its
  first frame, the logo face on.
