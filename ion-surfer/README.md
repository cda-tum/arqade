# Ion Surfer

A 1–2 player ion-trap arcade game for the IconicArcade Raspberry Pi 4 cabinet (Batocera,
`pygame` system), packaged the same way as Quantum Pong and Quantum Towers. You shape the
trap potential with the electrodes on the floor to keep your ion on screen while the
camera scrolls ever faster.

**Status:** full game (solo, 2-player versus, 2-player co-op, seeded levels, records),
a quantum sandbox mode (**SANDBOX**, 1–4 ions),
`--input-test`, and a Batocera deploy script. It also runs in the browser (pygbag), from
the same code.

## Gameplay

Each player controls a cursor over the electrode strip. Left/right selects an
electrode, and up/down raises or lowers its voltage. That reshapes the potential curve
your ion rolls on. Photons give bonus points. Watch out for the hazards:

- Defects and energy caps deform the potential.
- Blocks are solid obstacles.
- Lasers push the ion up or down.
- Stray ions repel yours (Coulomb force).
- Loss holes swallow the ion.

Your score is the distance transported plus bonuses.

- **Versus:** each player has their own curve and ion.
- **Co-op:** both players shape one shared curve for one team ion.

Levels are generated from a seed. You can enter a seed in the menu to replay a level.

### Main menu and the HOW TO PLAY card

The main menu is 1 PLAYER, 2 PLAYERS: VERSUS, 2 PLAYERS: CO-OP, SANDBOX, SEED and
QUIT. The stick moves the selection and A picks a row. **QUIT** exits the game at once,
back to the cabinet's game list (the same clean exit as Start + Select). **Start**
always starts a match and never quits: the selected mode, or 1 PLAYER from the SEED or
QUIT row. B does nothing on the main menu.

Every match picked in the main menu (the sandbox too) starts behind a full-screen
**HOW TO PLAY** card (`tutorial.py`): the goal in three lines, the controls with the
cabinet's printed labels (the stick and the `L X R / Y B A` cluster, used buttons lit;
in the sandbox both pads, P1 blue and P2 red, since their L and R differ), and a demo
that loops every 6 s. The demo is a second, private `Game` running the real physics,
its cursor driven by a short script and drawn with the real draw code: the ion is
pushed off, rolls right and picks up photons; in co-op red pushes and blue clears the
way; in the sandbox the packet is kicked, sloshes and is cooled back down. It has its
own random state, so the match's footage doesn't depend on how long the card was up.

Any button on either pad dismisses it, once it has been up 0.3 s (so the press that
picked the mode, or its bounce, can't skip it unseen); the stick doesn't. Buttons still
held at that moment are used up until released (`Controls.consume_buttons`), so the
dismissing A doesn't also move a cursor. Start + Select still quits from the card.
RESTART in the pause menu and SAME SEED / NEW SEED after a match skip it, as does the
`--sandbox` dev shortcut; QUIT TO TITLE and a new match shows it again.

### Sound

`sound.py` builds a small set of effects in code at start-up (no audio files, no
numpy), in surf-guitar style: plucked strings (Karplus-Strong) in E minor pentatonic
with a spring-reverb-like echo. Menu moves and confirms, pause, the cursor stepping to
another electrode, photons, hard landings, a lost ion, the match start (dismissing the
card), and a tremolo-picked fanfare for a versus win or a new record (a falling riff
otherwise). The sandbox has its own: the laser kick, adding and removing an ion,
cooling, passive cooling on/off and the ANHARMONIC warning coming on. Holding a voltage
is silent on purpose: it would drone through the whole match. Without a working mixer
every effect is a silent no-op.

**Landing on the wave** is as loud as the landing is hard. `integrate()` passes the
ion's speed into the curve (the normal component of its velocity relative to the
surface, so a curve shoved up under it counts too) to `Sounds.impact()`, and
`impact_gain()` maps it to a volume: silent below 200 px/s (rolling), a faint 6 % of
full just above, rising as strength^1.5 to full at 1100 px/s, and capped there. A
15 px drop lands at about 200 px/s, a 60 px drop at 400, a throw from the top of the
screen at over 1000. Harder landings also pick a brighter, higher sound
(`bounce_soft` / `bounce` / `bounce_hard`). The volume is set on the Sound itself, so
the attract capture logs it. Two landing sounds are at least 150 ms apart, unless the
second is 1.6 times louder: a ball rattling along a bumpy curve doesn't machine-gun,
and a real crash right after a bump still sounds.

**Ambience.** In a running arcade match (not the sandbox, menus or the pause screen)
the laser beams hum and stray ions ping, quietly, from where they are. A beam pushing
up shimmers high (two sines beating at 2 Hz), one pushing down a fifth lower; a stray
gives a soft sonar ping every 1.3 s, every 0.55 s right next to an ion. Each is panned
to its screen x (equal-power, the screen edges at 80 % pan), fades over 80 px as it
scrolls on or off, and is 30 % as loud far from the nearest ion as right beside it.
The hums are 2 s seamless loops, swell in over 0.8 s and out over 0.5 s, breathe once
per loop, and only play while audible. They run on three reserved mixer channels (12
in all, so effects never land on a panned channel and still have 9); their peaks stay
under every effect's. The attract capture leaves them out of its WAV, like music: it
only logs `Sound.play()`, and they play through `Channel.play()`.

Measured from the rendered sounds (peak, loudest 50 ms RMS, dBFS):

| Sound | Peak | RMS |
|---|---|---|
| old landing, any strength | -11.1 | -18.9 |
| landing at 250 / 450 px/s | -32.7 / -23.9 | -39.1 / -30.4 |
| landing at 600 / 800 px/s | -18.8 / -14.3 | -26.6 / -21.5 |
| landing at 1100+ px/s (cap) | -9.5 | -16.7 |
| other effects | -7.5 to -21.2 | -13.5 to -27.4 |
| beam hum, far / beside an ion, centre | -39.5 / -29.0 | -43.2 / -32.7 |
| stray ping, far / beside an ion, centre | -38.5 / -28.0 | -47.3 / -36.9 |

## Sandbox

The sandbox is the **SANDBOX** entry in the game's own main menu, alongside the three
arcade modes. Locally you can skip straight to it with
`uv run python -m ion_surfer.main --sandbox`, which is a dev shortcut only -- on the
cabinet it is reached through the menu like any other mode.

It is a fixed screen without scrolling. Both players shape one shared potential,
like in co-op: blue's cursor starts on the left, red's on the right, matching the
joysticks. Instead of the classical ball, the ion's motion is simulated quantum
mechanically:

- **1 ion:** the full wave packet is simulated on a 400-point grid by solving the 1D
  Schrödinger equation in the real potential, with no harmonic approximation. The
  scheme is unitary and 4th order in both time and space (see `quantum.py`), so even
  a packet kicked four times keeps its shape. The packet is drawn on the potential,
  with the colour showing its phase (colour stripes = momentum).
- **2–4 ions (Coulomb crystal):** the game finds the crystal's equilibrium and its
  normal modes (COM, stretch, egyptian, ...). Each mode gets its own simulated wave
  packet. It feels the exact potential along that mode's direction, including trap
  anharmonicity and the Coulomb repulsion, which the ions can't pass through. Only
  the coupling between modes is left out. When you reshape the potential, the
  equilibrium and the modes move but the ions don't: the packets are carried over
  into the new modes, so the ions stay where they physically are. A mode where one
  ion dominates, for example when the ions sit in separate wells, is labelled
  `ION k`. Every ion is drawn as its position distribution.

The cockpit along the top shows this for every mode:

- **MOTIONAL STATE:** Fock populations P(n) in the mode's harmonic basis. The pink bar
  is everything above the last level.
- **PHASE SPACE:** the Gaussian blob (covariance ellipse), which shows displacement,
  squeezing and the phase it rotates through, plus its recent trail.
- **SCOPE:** displacement ⟨x⟩ and width over the last 6 s. Breathing shows up as the
  width oscillating at twice the mode frequency.
- **READOUT:** frequency, ⟨n⟩ (computed exactly from the moments), |α|, phase and
  squeezing in dB.

All of the cockpit is relative to a parabola fitted to the bottom of the well: the
well the single ion is in, or the crystal's equilibrium for a mode. A parabola keeps
a Gaussian packet Gaussian. Any other shape bends it, and then the ellipse no longer
shows the whole state. The cockpit measures this as the packet's uncertainty area,
which is exactly 1 (in vacuum units) for any Gaussian. When, for a second, any
mode's area stays above 1.3, or a crystal mode's packet sits in a different well
along its mode than the equilibrium, the phase-space panel gets a red edge and says
**ANHARMONIC**. The motion itself is still simulated correctly then; only the
harmonic picture of it fails. For a crystal, this is also where leaving out the mode
coupling starts to matter.

The start trap is exactly harmonic across the whole screen, so kicks alone don't set
the warning off until the packet reaches the screen's walls (about 8 kicks). A narrow
well, a barrier under the packet, or a kicked crystal's stretch mode do.

How to produce the effects:
- **Displacement:** a laser kick, or moving the well suddenly.
- **Squeezing and breathing:** tightening or loosening the well suddenly. A slow change
  is adiabatic and stays in the ground state.
- **Cooling:** red holds L to damp everything back to the ground state quickly. Red R
  toggles passive cooling, a slow steady drain; it is off by default.
- **COM vs stretch:** P1's kick pushes the leftmost ion right and P2's pushes the
  rightmost ion left. So one kick excites COM and stretch together, while both players
  kicking at the same moment gives an almost pure stretch.

Performance, measured on the dev machine only (not on the cabinet yet): one ion adds
about 1 ms per frame on top of the normal world drawing, and four ions about 2 ms.
Holding a voltage costs a little more, because the mode potentials are then
re-sampled every frame. If the Pi 4 struggles with four ions, lower `MAX_IONS` in
`sandbox.py`.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd ion-surfer
uv sync
```

## Run

```bash
uv run python -m ion_surfer.main                    # windowed, keyboard/joystick
uv run python -m ion_surfer.main --fullscreen        # fullscreen at desktop res
uv run python -m ion_surfer.main --fps               # force the FPS overlay on
uv run python -m ion_surfer.main --window-size 1800x960
```

In the browser (pygbag's test server on http://localhost:8000), from the repo root:

```bash
uv run --project tools tools/build_web.py --serve ion-surfer
```

Press **F3** in-game to toggle the FPS overlay at runtime. The game renders at 1200×640
and is scaled and letterboxed onto the real screen.

### Input test mode

```bash
uv run python -m ion_surfer.main --input-test
```

This mode shows live joystick axes, buttons and hats. Esc quits. Button and axis numbers
live in `../common/src/arqade_common/input.py`, shared by all games.

### Controls

| | P1 (blue): pad / keys | P2 (red): pad / keys |
|---|---|---|
| Select electrode | Stick or d-pad left/right, or Y/A / A D or C B | the same / ← → or J L |
| Voltage | Stick or d-pad up/down, or X/B / W S or G V | the same / ↑ ↓ or I K |
| Start (menus) / pause (in play) | Start / Space | Start / Enter |
| Menu: confirm | **A** / B | **A** / L |
| Menu: back | **B** / V | **B** / K |
| Sandbox: laser kick | Select / L-Shift | Select / R-Shift |
| Sandbox: L | remove ion (key F) | cool while held (key U) |
| Sandbox: R | add ion (key H) | passive cooling on/off (key O) |

The keys are the layout shared by all the games (`../common`): each player's half of the
keyboard is a pad, its 2x3 buttons on F G H / C V B and U I O / J K L. On-screen hints name
the keys or the pad buttons, whichever each player last used. In the SEED entry, letter
keys type, so Space or Enter finishes it.

- **Start** pauses during play, on either controller, in every mode including the
  sandbox. The pause menu has RESUME, RESTART and QUIT TO
  TITLE (QUIT with `--sandbox`, which has no title screen): the stick moves the
  selection, A picks, Start or B resumes. Select does not pause; it is reserved for
  the quit combo (and fires the laser kick in the sandbox).
- **Quit:** hold Start and Select together on either controller (Space + L-Shift or
  Enter + R-Shift on the keyboard), paused or not, also on the HOW TO PLAY card, or pick
  QUIT in the main menu with A. There is no quit key: Esc leaves fullscreen in a browser,
  and the PC launcher's Esc ends the game on its own. In the browser, quitting goes back
  to the menu and tells the page around the game (`arqade:quit`).
- The cabinet loader runs the game with `--no-keyboard`: Batocera also turns P1's pad into keystrokes (arrow keys, numpad, letters, Enter/Space — see `../AGENTS.md`), which would otherwise let P1's stick or buttons drive P2 or fire two actions at once. Pads use the cabinet's button numbers by default; `--pad-layout xbox` reads an Xbox-style pad on a PC instead, and browser gamepads use the browser's standard layout.

Records (solo and co-op) are saved to `~/.ion_surfer_scores.json`. On Batocera that is
`/userdata/system/`, so a redeploy doesn't reset them.

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This works the same way as the quantum games. The package goes to
`/userdata/games/ion_surfer/`, and one small loader, `ion_surfer.pygame`, goes to
`/userdata/roms/pygame/` and runs the game fullscreen. Its name and icon come from
`../batocera/gamelist.xml` and `../batocera/icons/ion_surfer-image.png` (see "Game
names and per-game icons" in `../AGENTS.md`).

## Tests

```bash
uv run pytest
```

The tests cover the pure input functions, `Pad`'s hold/press/auto-repeat logic, the
config (every key name exists, and start/select aren't action buttons),
`display.py`'s scaling math, the pause menu (`tests/test_game.py`, which drives
`Game` with the cabinet's raw joystick events), the main menu's QUIT and Start rows and
the HOW TO PLAY card (`tests/test_tutorial.py`: menu -> card -> play for every mode,
the 0.3 s guard, stick vs buttons, the used-up dismissing press, the quit combo, which
starts skip the card, the demo looping and leaving the global random state alone),
the sound builders and their silent fallback, the landing volume curve (silent, then
faint, monotonic, capped) and its rate limit, panning, and the ambience swelling, pinging
and surviving the attract capture's sound log (`tests/test_sound.py`; the landing speed
and the ambient sources from a real match are in `tests/test_game.py`), and the sandbox
physics:
- `quantum.py`: norm conservation, a stationary ground state, coherent-state
  oscillation, squeezed-state breathing with even-only Fock populations, kicks and
  cooling.
- `crystal.py`: the Coulomb spacing, COM at ω and stretch at √3·ω, three-ion mode
  ratios, kicks that excite only COM vs COM and stretch, and following a moving trap.

Apart from the menus and the card, the game loop and rendering (`game.py`, `sandbox.py`) are
integration glue. They are verified by running the game.

## Tuning

`src/ion_surfer/config.py` holds the input mapping. Physics and scroll-speed constants
are in the TUNING block at the top of `src/ion_surfer/game.py`, and the sandbox
constants are in the TUNING block of `src/ion_surfer/sandbox.py`: ħ/m (sets the packet
width), potential coupling (sets the trap frequency), Coulomb strength (sets the ion
spacing), kick strength, cooling rate and `MAX_IONS`.

## Fonts

The game bundles Bungee (titles/HUD) and Rubik Medium (body text) at
`src/ion_surfer/assets/fonts/`. Both are OFL-licensed, see `OFL-Bungee.txt` and
`OFL-Rubik.txt` there. Rubik Medium is a static instance of Google Fonts' variable
`Rubik[wght].ttf`, set to weight 500. If a font is missing, the game falls back to
pygame's default font.
