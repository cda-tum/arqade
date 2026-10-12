# Qircuit

Slot-car racing in 3D on the wires of a quantum circuit, for 1 to 4 players
and up to 8 racers with computer opponents, for the ARQADE cabinet
(Batocera, `pygame` system). The track is four wires, like a Carrera
track's slots. You choose your speed and your wire, and every power-up is a
gate on a wire. The racers are characters from the other arqade games, each
with its own strengths, and each track sits in one game's world.

The camera is a fixed isometric view that follows the leader, as in
BlazeRush. The leader scores: every second in front counts, and the first
to 30, 60 or 90 seconds in the lead wins. Whoever falls off the screen is
put back in at the back of the pack, already moving.

**Status:** prototype, played locally only. It covers:
- three tracks in three scenes;
- nine racers with a racer select;
- 1 to 4 players plus bots at three levels;
- the lead as the score, and resets for whoever falls off the screen;
- boost pads, jumps, and gates that come and go;
- sound effects;
- `--input-test` and a deploy script.

There is no logo or `batocera/gamelist.xml` entry yet. The PC launcher finds
the game anyway, using the description in its `pyproject.toml`. On the
cabinet it is an experimental game: deployed but hidden from the public game
list (see "On the cabinet" below). It has not yet run there, and OpenGL there
is unchecked.

## How to play

- **Title:** the stick moves between the rows (up/down) and changes the one
  picked (left/right). Start (on any row) or A goes on. Four bots race the
  chosen track behind the menu.
  - PLAYERS: 1 to 4 people.
  - BOTS: up to however many fit in 8 racers. One person alone always gets
    at least one bot.
  - LEVEL: EASY, TOUGH or BRUTAL, for all the bots.
  - TRACK.
  - LEAD: the seconds in front that win, 30, 60 or 90.
  - QUIT: A here leaves the game, back to the cabinet's menu (or the PC
    launcher's). Start still starts, and B does nothing on the title.

  The default is one player against 3 EASY bots, first to 60 s in front.
- **Racer select:** like Mario Kart's. Everyone moves their own cursor over
  the roster with their own stick or buttons, and sees their racer turning
  in 3D, with its ratings.
  - With one or two people, each locks in with A on their own pad (B
    unlocks). The match starts once everyone has.
  - With three or four, the button players have no A to spare (it steers
    them), so Start starts with whatever everyone is on.
  - Start always starts at once. B with nobody locked in goes back to the
    title.

  The bots each get a racer nobody else is on.
- **HOW TO PLAY:** a card before the countdown, every time a match starts
  from the title (not on a rematch). It shows the goal, the controls with
  the cabinet's printed buttons (and who drives with which pad), and a
  looping demo on the chosen track: your own racer tucks in behind a bot,
  pulls out onto the next wire, passes and takes the lead (`tutorial.py`).
  Any button goes on to the countdown, but only after 0.3 s, so the press
  that started the match can't skip it unseen. The stick doesn't.
- **The race:** see "Leading and resets" below. It runs until someone has
  been in front long enough.
- **Match result:** A plays again with the same racers (no HOW TO PLAY card),
  B goes to the title.
- **Pause:** Start, from either pad, during the countdown or the race. The menu
  offers RESUME or QUIT TO TITLE; Start or B resumes. Start + Select quits,
  as in every game.

### Controls (all relative to your racer)

| | Stick | Buttons |
|---|---|---|
| Gas | up | X |
| Brake | down | B |
| Change to the wire on your racer's left / right | left / right | Y / A |

With neither gas nor brake, the racer slowly coasts down. Left and right
always mean the racer's own left and right, whichever way it heads on the
screen.

Who drives with what depends on the number of people:

| People | Left pad | Right pad |
|---|---|---|
| 1 | P1 (stick or buttons) | P1 too |
| 2 | P1 (blue): stick or buttons | P2 (red): stick or buttons |
| 3 | P1 on the stick, P3 (green) on the buttons | P2: stick or buttons |
| 4 | P1 on the stick, P3 on the buttons | P2 on the stick, P4 (purple) on the buttons |

That's the same split as in Qurves. A person's racer rides on a ring in
their colour, so it stands out among the bots.

Keyboard (dev only; the cabinet passes `--no-keyboard`):
- P1: W A S D. P3: T F G H. P2: I J K L. P4: the arrow keys.
- Enter starts (and locks P1 in), Backspace goes back, P pauses, Esc quits.

## Leading and resets

The camera looks down on the track at a fixed angle, from the south-west,
like an isometric game. It never turns: it only slides after the leader, so
the leader drives across the screen with the pack trailing behind it.

- **The leader scores.** Every second in front counts, and the first to the
  target (30, 60 or 90 s, all added up) wins. A gold arrow marks the leader,
  and the HUD shows everyone's seconds. The last five seconds before a win
  tick.
- **The lead changes hands** once a challenger is 6 units clear, so two
  racers side by side don't swap it every frame.
- **Fall off the screen** (0.4 s past an edge, or under the HUD band at the
  top) and you are put back in at the back of the pack:
  - 30 units behind the last racer still on the screen, but well inside it;
  - on the emptiest wire there;
  - already doing nearly the leader's speed, or less if a corner is coming;
  - blinking for 1.5 s, while you pass through other racers, bugs and Zeno
    traps.

  A flashing arrow in your colour warns you when your racer nears an edge.
  The leader is never reset.

Leading is not safe: a spin-out or an error bug drops the leader back into
the pack in a moment.

## The racers

One racer from each arqade game that has a character to give, built as a
voxel model from that game's own look (`voxels.py`). Every racer has five
ratings from 1 to 5 that add up to 15, so none is better at everything.

| Racer | Game | Looks like | SPD | ACC | GRIP | WGT | HND |
|---|---|---|---|---|---|---|---|
| CHANDELIER | Superconductor | a loco whose nose is the gold dilution-fridge chandelier, on its side | 5 | 1 | 3 | 4 | 2 |
| ION | Ion Surfer | the dark ion riding a green-blue swell, spray and droplets | 3 | 4 | 3 | 1 | 4 |
| PAULI JELLY | Pauli Invaders | the invader as a jellyfish, its sprite's legs as trailing tentacles | 2 | 4 | 4 | 2 | 3 |
| COLOR CODE | Pauli Invaders | P1's 3-colour colour-code triangle, flat and hovering | 3 | 3 | 3 | 3 | 3 |
| LIGHT CYCLE | Qurves | a dark bike with a glowing blue stripe and the start of its trail | 5 | 2 | 2 | 2 | 4 |
| PADDLES | Quantum Pong | two white paddles as a sled's runners, the ball up front | 3 | 2 | 4 | 3 | 3 |
| CHEF | Overquqed | P1's teal chef on a steel trolley with a Bloch Bowl | 2 | 5 | 3 | 3 | 2 |
| TOWER | Qlimbers | the stone tower on wheels, gold band, the cyan climber on its side | 3 | 3 | 3 | 5 | 1 |
| PHOTON | Qlinko | the gold photon with its wave packet rippling out behind | 4 | 4 | 2 | 1 | 4 |

- **SPEED** is top speed and **ACCEL** how fast it gets there.
- **GRIP** is how fast it can take a corner before it drifts (and spins).
- **WEIGHT** counts in bumps and pushes. The heavier racer loses less speed,
  shoves a lighter one aside, and pushes the racer in front along when it
  runs into it. A much lighter racer just bounces off a heavy one.
- **HANDLING** is how quickly it changes wires.

`racers.py` turns ratings into physics (the `STAT_*` steps in `config.py`).
Alone, every racer covers two laps within about 3% of the others on every
track (`tests/test_racers.py`). Weight and handling pay off in traffic, not
alone.

`tools/balance.py` runs the full check: each racer's solo pace, and its share
of the lead over many 90 s, 8-racer BRUTAL races with everything on. The last
run (6 races per track) gave:
- solo paces within ±1.3% of the mean;
- shares of the lead from 6% to 20%, where an even field gives 12.5%.

A second sample of 36 races put the racers in a quite different order, with
standard errors of 2 to 4%. So the spread is mostly chance, and no racer
stands out yet.

## Racing

### Corners

Every corner has a speed limit per wire. Inner wires are shorter but tighter,
so their limit is lower.
- Over the limit, your racer **drifts**: it turns into the corner and slides
  out, scrubbing a little speed.
- Further over, it **flashes red** (with a beep) and its spin meter fills.
  Brake now.
- A full meter **spins it out**: it keeps 15% of its speed and is stuck for
  0.7 s while the pack streams past, and it may well drop off the screen.

### Other racers

- **Slipstream:** close behind a racer on the same wire, it builds over a
  third of a second to 15% more top speed and 60% more acceleration (shown
  by speed streaks).
- **It lasts, like DRS.** Once full, it stays for a second after you pull
  out, long enough to pass. Tuck in, then switch at the last moment.
- **Running into a racer from behind** slows you to just below its speed
  (5%, so blocking doesn't cost the follower much). You can't pass on the
  same wire.
- **Changing wires into a racer** is a push. Both wiggle and lose speed. The
  other one is shoved a wire further over if there is one, it is free, and
  the other racer isn't much heavier than you. Otherwise you stay where you
  were. See WEIGHT above.

### Boost pads, jumps and hills

- **Boost pads** (orange chevrons on some wires) put you 35% over your top
  speed, easing back down over a second or two. Mind the next corner.
- **Kickers** (a short ramp with a striped lip) throw a fast racer into the
  air, further the faster it goes. In the air it can't change wires or
  drift, and it flies over gates, items, error bugs and Zeno traps.
- The figure 8's second pass climbs over the first on a **bridge**. The
  other tracks have a hill.

### Gates

Gates don't stay put. Each track keeps a number of quantum gates out at
random places. Each stays 9 to 16 s, blinks, goes, and a new one appears
somewhere else. Nothing appears on a boost pad or a kicker, or right in
front of a racer.

| Gate | Looks like | On your racer |
|---|---|---|
| **SWAP** | × on two wires | moves you to the other wire. A racer right beside you there comes over to yours: you trade places |
| **CNOT** | ● on the control wire, ⊕ on the target | from the ● wire, it **copies** your racer onto the ⊕ wire. Nothing from the ⊕ side |

**Copies are an extra life.** A copied racer takes the same input as the
original. A copy that falls off the screen is simply gone, and you are only
put back in when neither is left on it. You have at most one copy at a
time. After 10 s, your copies collapse onto the one in the lead.

### Items

Item gates (in a pulsing box) are taken by the first racer through them on
their wire. A new one appears somewhere else 3 s later.

- **ERR** puts an X or Z error bug in front of your racer. It hovers there
  for a second, following you from wire to wire, with dots down the wire it
  will take. Then it shoots off along that wire. Change wires while it
  hovers to aim it.
- **ZENO** forms a Zeno trap behind your racer. It blinks for 1.2 s, then
  drops on the wire.

**Error bugs** are Gate Drop's Pauli errors, running along the wires like
shells along a slot.
- A bug leaves at its racer's speed plus a little (X +55, Z +45, and at
  least 120 from a crawling racer). So it catches the racers ahead on its
  wire and stays ahead of its own.
- A bug never hits the racer that launched it, and fades after 5 s.
- **X** (red) is a bit flip: it knocks the racer it hits onto a neighbouring
  wire, at 70% speed.
- **Z** (blue) is a phase flip: it costs you your timing, half your speed.

**The Zeno trap** is named after the quantum Zeno effect: a quantum system
that is measured often enough never gets to change. Each measurement snaps
it back to where it was, like a watched pot that never boils. (Zeno of Elea
is the Greek whose paradox says a flying arrow never moves.) A racer that
drives into the trap is measured so often it can barely move on: it loses
40% of its speed and glows cyan for a moment.

## Tracks and scenes

| Track | Scene | What makes it |
|---|---|---|
| **FIGURE 8** | Pauli Invaders: the track floats in near-black space over a starfield far below, jellyfish invaders hovering in formation in the loops | Two loops. The second pass of the crossing climbs over the first on a bridge. Every wire is the inner one in one loop and the outer one in the other, so all four are exactly as long. |
| **SPLIT** | Superconductor: laid over the game's chip, its lattice of Xmon qubits and couplers on the dark substrate, Xmons standing proud here and there | Tight corners and a hill. The wires part 2 + 2 for a long stretch, and both pairs jump a kicker there. |
| **HAIRPIN** | Ion Surfer: floating over a blue sea whose foam lines drift past, in the warm haze of its sunset poster | A long straight with a boost pad and a kicker for a long flight, a hill, and a hairpin so tight its inside wire wants a crawl. |

A track is defined in `tracks.py`. It lists:
- its slot-car pieces (straights and arcs);
- its hills, kickers and boost pads;
- how many gates and items it keeps coming and going;
- its scene.

The figure 8 is built piece by piece. The others use `track.rounded()`: a
polygon whose corners each get their own radius, which always closes, so a
new track is a list of corners. The chase camera shows only a few hundred
units of track at a time, so the layouts are drawn 2.5 times the size of one
screen.

A scene in `scenes.py` sets:
- the track slab's colours;
- the light and the fog;
- the ground plane and the picture tiled on it;
- the voxel props around the track.

## The look

Everything is drawn in 3D with OpenGL, through PyOpenGL. The context is
OpenGL ES 3.0 where the system offers one (what the Pi 4 has), and desktop
OpenGL 3.3 core otherwise. The shaders are written once and get the
matching `#version` line.

- **Frame:** each one is drawn into a 960x540 target, then scaled x2 with
  nearest-neighbour onto the cabinet's 1920x1080 (letterboxed on other
  screens).
- **Camera:** orthographic, so a racer is the same size anywhere on the
  screen. It looks along a fixed heading (north-east) from 50° above, 520
  units across (`CAM_*` in `config.py`).
- **Racers and props:** the voxel models become lit meshes of cubes, with
  only the faces that show (`mesh.py`).
- **Track:** one mesh, built once per track. It holds the slab, the glowing
  wires, kerbs, walls, pillars, start line, chevrons and kicker lips.
- **Flat things:** shadows, rings, error bugs, gate glyphs, items and smoke
  are flat quads with pictures from a pygame atlas (`art.py`).
- **HUD:** the HUD, menus and popups are drawn with pygame on a transparent
  layer (`hud.py`), uploaded as a texture each frame.
- **Racer select:** the racers turn in 3D, each in its own little viewport.

Costs on this laptop, with software OpenGL in WSL: a frame with 8 racers at
1440x810 takes about 18 ms. Nearly all of it is the GL work itself (the
track's mesh alone about 5 ms), which software rendering does on the CPU.
The Pi 4 has a real GPU but a much slower CPU, and that is not yet
measured.

## Bots

The computer drivers are in `ai.py`: one driver, three levels, each a
`Skill` (a handful of numbers).

- **EASY** takes corners well under the drift limit, never quite flat out,
  and brakes early. It thinks about its wire now and then, and not always
  well.
- **TOUGH** takes corners into a light drift with good braking, tucks into
  slipstreams and pulls out of them to pass, and lines up for boost pads.
- **BRUTAL** drives right up to the red and brakes at the last moment. It
  knows the whole race:
  - it takes the gates that help it (a CNOT copy, an error launcher with a
    rival ahead on that wire);
  - it aims a hovering bug at a rival;
  - it dodges bugs about to catch it, and Zeno traps.

Every few tenths of a second (EASY: about a second) a bot estimates what each
reachable wire costs over the next stretch, and changes to the cheapest. It
weighs:
- shorter inner wires against their lower corner speeds;
- slower racers in the way;
- slipstreams and boost pads.

The same AI drives the bots behind the title and the attract-reel bot
(`../batocera/attract/bots/qircuit.py`). That bot sits in P1's and P2's
seats at BRUTAL, picks racers in the select, and turns the AI's controls
into stick moves. This is the pattern for AI opponents in every game; see
"AI opponents" in `../AGENTS.md`.

The reel capture can't record Qircuit yet. `capture.py` uses SDL's dummy
video driver and reads the display surface, while Qircuit needs a GL
context (the offscreen driver) and a read of its frame before the flip.

Bots are labelled CPU1, CPU2, and so on. On the points chips and the
scoreboards they wear neutral colours (yellow, white, grey, tan, ...), never
a player's, and they ride on no ring.

## Sound

Short synthesized effects, as in Qurves (`sound.py`, no audio files):
- menu moves, and a confirm chirp going on to the racer select, into the
  HOW TO PLAY card and out of it;
- the countdown, locking in a racer, taking the lead, the last seconds
  before a win, and the win;
- drifting, the red warning beep and the spin-out;
- boost pads, take-off and landing;
- bumps and pushes;
- every gate and item: SWAP, the CNOT copy and losing it or its collapse,
  the error bug arming and launching, bit and phase flips, the Zeno trap;
- being put back in after falling off the screen.

What happens to a bot sounds too. Drifting, the warning, boosts, jumps,
resets and taking the lead sound only for people, or eight racers turn into
noise. There is no engine
hum on purpose: it would grate on a public cabinet.

## Tuning

- `config.py`:
  - the camera (`CAM_*`): its angle, how much it shows, how closely it
    follows;
  - leading and resets: how long off the screen counts, where and how fast
    a racer comes back, the lead margin and the targets;
  - the base car (`CAR`) and what each rating step is worth (`STAT_*`);
  - the corner thresholds (`DRIFT_LOAD`, `WARN_LOAD`, `SLIP_*`, `SPIN_*`);
  - slipstream, bumps, boosts, jumps, gates, items and timings;
  - the numbers of people and bots, and the bots' colours.
- `racers.py`: the roster's ratings. Re-run `tools/balance.py` after changing
  them.
- `ai.py`: the bots' levels (`SKILLS`).
- `scenes.py`: each scene's colours, light, fog and props.

## Code

| File | What |
|---|---|
| `track.py`, `tracks.py` | Geometry: pieces to a centre line, per-wire polylines, lengths, curvature, height; the three tracks. Pure, tested. |
| `race.py` | The racing: corners and spin-outs, contact, weight and the slipstream, boosts, jumps, gates that come and go, copies, items, error bugs, Zeno traps, resets. Pure, tested. |
| `camera.py` | The isometric camera: its matrices, and whether a point is on the screen. Pure, tested. |
| `tutorial.py` | The HOW TO PLAY card: its words, and its demo, a scripted little race on the chosen track. Pure, tested. |
| `match.py` | Title (with QUIT), racer select, the HOW TO PLAY card, countdown, the race (`Pack`: who leads, who fell off the screen), the lead's seconds, the match result, pause, idle timeout, the title's demo race. Pure, tested. |
| `racers.py`, `voxels.py` | The roster and its ratings; the racers and props as voxel models. Pure, tested. |
| `ai.py` | The computer drivers at three levels: opponents, the title demo, the reel bot. Pure, tested. |
| `mesh.py` | Voxel models and tracks into vertex data. Pure, tested. |
| `gfx.py` | OpenGL plumbing: the window and context, shaders, meshes, textures, the 960x540 target. |
| `art.py` | The atlas of flat pictures: bugs, gate glyphs, items, shadows, rings. |
| `scenes.py` | The three scenes. |
| `hud.py` | The 2D layer: HUD, popups, warnings, scoreboards, title, racer select, the HOW TO PLAY card, pause. |
| `render.py` | Everything drawn each frame, in 3D and on the layer. |
| `sound.py` | The synthesized sound effects. |
| `input.py` | Pads and the dev keyboard into a `FrameInput`. |
| `tools/snapshot.py` | Renders the title, the racer select, the HOW TO PLAY card, every track mid-race and a match result to PNGs, headless with real OpenGL. |
| `tools/balance.py` | The roster's balance check. |

## Running, testing, deploying

```bash
uv run python -m qircuit                 # windowed dev run
uv run python -m qircuit --fps           # with a frame-rate counter
uv run python -m qircuit --input-test    # live pad state, for checking button numbers
uv run pytest
uv run python tools/snapshot.py /tmp/qircuit
uv run python tools/balance.py 6         # 6 races per track
./deploy_batocera.sh                     # or ./deploy_batocera.sh root@10.42.0.100
```

`tests/test_render.py` draws every screen through SDL's offscreen driver
with real OpenGL, and skips itself where no GL context can be made.

### On the cabinet

Not tried yet. Things to check before the first deploy:

- **OpenGL ES under sway:** whether pygame there gets a GL ES 3.0 context
  at all. On Linux, `qircuit/__init__.py` makes SDL and PyOpenGL both use
  EGL, because they otherwise pick different platforms on a Wayland desktop
  and PyOpenGL then finds no context. On the cabinet, SDL's wayland and
  kmsdrm drivers use EGL anyway.
- **The dependencies:** whether Batocera's Python has numpy and PyOpenGL.
  PyOpenGL is pure Python and could ship with the game. numpy is compiled,
  so it is either already there or the vertex arrays move to the standard
  library's `array`.
- **Frame time on the Pi 4.**

`./deploy_batocera.sh` parks the loader at
`/userdata/games/qircuit/qircuit.pygame`, outside the ROMs folder, so the
game stays out of the public game list. To try it on the cabinet, hold Start
+ Select on both pads at once in the menu: it joins the list, until the same
combo again or the cabinet idles into the attract reels ("Experimental
games" in `../AGENTS.md`). Making it public later takes a `gamelist.xml`
entry, a logo, and the loader in `/userdata/roms/pygame/` like the other
games.
