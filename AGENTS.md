# Arcade cabinet & hardware notes

This directory holds independent pygame games (`quantum-pong/`, `quantum-towers/`,
more later) built for the same physical target: a Batocera-based arcade cabinet
("IconicArcade"), a Raspberry Pi 4 with two 6-button joystick pads. This file
collects hardware facts and hard-won quirks that apply **across games**, so a
future session doesn't have to rediscover them from scratch. Per-game specifics
(gameplay, architecture, tests) belong in each game's own `README.md`.

## Runtime environment

- **Python 3.11.x, pygame 2.5.2 exactly** (`requires-python = ">=3.11,<3.12"`,
  `pygame==2.5.2` in `pyproject.toml`). This must match the cabinet's actual
  runtime, confirmed on it directly. Don't bump either without re-confirming on
  hardware.
- Batocera's "pygame" system runs a ROM by literally executing
  `python <file>.pygame` with that file's own directory as `cwd` — the
  `pygame` binary on Batocera is a symlink to the Python interpreter, not a
  separate launcher (confirmed by reading batocera-linux's own
  `pygameGenerator.py` / `batocera-pygame.mk` source). So a `.pygame` "ROM"
  can be a plain Python script.
- Root's persistent home on Batocera is `/userdata/system`, **not** `/root` —
  Batocera's rootfs is a read-only overlay. SSH keys go in
  `/userdata/system/.ssh/authorized_keys`.
- `ssh root@batocera.local` (fallback: `root@10.42.0.100`, or whatever the
  cabinet's actual address is if mDNS isn't resolving) reliably works once
  keys are set up. A benign `X11 forwarding request failed on channel 0`
  warning shows up on every connection — ignore it, the session still works.

## Deploy pattern

Each game ships its own `deploy_batocera.sh` (see `quantum-pong/` and
`quantum-towers/` for working examples) following the same shape:

- Real code goes to `/userdata/games/<game_name>/<game_name>/` — kept out of
  the ROMs folder entirely.
- A tiny loader script goes to `/userdata/roms/pygame/<game_name>.pygame`:
  it just does `sys.path.insert(0, ".../games/<game_name>")` then imports and
  calls that game's `main()`, typically with `--fullscreen`.
- Rewriting the loader's **content** does not require an EmulationStation
  rescan/restart — ES only re-reads the ROM list/directory structure at scan
  time, not each file's contents at launch time. So once a game's `.pygame`
  file is registered once, you can safely overwrite it (e.g. to temporarily
  point at `--input-test` mode for diagnostics, then back) and just relaunch
  it from the existing menu entry.
- Registering a **new** ROM for the first time (or after deleting one) does
  need an ES rescan/restart to show up in the menu.

### The black-screen incident (be careful with ES config)

Editing EmulationStation's own config (e.g. `es_systems_*.cfg`) and restarting
ES is a materially riskier action than the file-copy deploy above — doing that
once produced a black screen requiring a couple of power cycles to recover.
That specific incident traced back to an unrelated ES config change made in a
different session, not the deploy script itself, but the lesson stands:

- Prefer the file-copy deploy pattern above; it never touches ES config and
  has never caused an issue.
- If an ES config change or restart is genuinely needed, say so explicitly
  and keep the change as small as possible — this is a shared piece of
  hardware the user has to physically power-cycle if something goes wrong,
  not something to restart speculatively.

## Input mapping: raw button numbers are NOT the print/position order

This is the most important quirk, and the one most likely to bite a future
game on this same cabinet.

**Never assume a physical button's raw `joystick.get_button(n)` index equals
its position in the printed 2x3 button grid, or its index in an on-screen
legend.** They are two independent mappings and can differ completely. An
earlier version of Quantum Towers' `config.py` conflated them (used the same
integer for "which grid position is this" and "which raw button fires this"),
which produced exactly the confusing bug you'd expect: pressing one physical
button visibly triggered a *different* gate/box than the one printed on it.

The fix, worth carrying into any future game on this cabinet: keep two
explicit, separate mappings from the start --

1. `GATE_AT_POSITION` (or equivalent): which action is shown/printed at each
   physical grid position. This is about the cabinet's fixed physical layout
   and print order, not wiring — the same for both players' pads.
2. `INPUT_CONFIG[player]["buttons"]`: which RAW hardware button number each
   action is actually wired to. This is hardware/wiring-specific, confirmed
   via `--input-test`, and can differ from the position order entirely.

Never build one of these by inverting the other.

### Confirmed raw button numbers (this cabinet, both players, 2026-09-30)

Using each pad's actual 2x3 physical layout, printed row-major as
`L X R / Y B A` (confirmed the same day as the raw numbers below — an
earlier pass got the bottom row's print order wrong, assuming `B Y A`):

| Printed label | L | X | R | Y | B | A |
|---|---|---|---|---|---|---|
| Raw `joystick.get_button()` index | 4 | 0 | 5 | 3 | 2 | 1 |

Confirmed identical for both player 1's and player 2's pads. Re-verify with
`--input-test` if a game ever behaves as if buttons are scrambled again, or if
the cabinet's controller hardware changes — don't assume this table still
holds without checking.

### P1's encoder also emits keyboard keystrokes

Player 1's pad encoder sends a keyboard keystroke matching each button's own
**printed** letter (`l`/`x`/`r`/`b`/`y`/`a`) *in addition to* its joystick
signal. Player 2's encoder does not do this at all (joystick-only).

Practical consequence: any game's keyboard dev-fallback bindings for player 1
must avoid all six of those letters, or a real button press on the cabinet
will double-fire two different actions at once — one from the joystick raw
number, one from the keyboard binding it happens to collide with. This is
exactly what caused the first bug report to look like "pressing A does two
things at once": physical A fired raw button 1 *and* the keystroke `a`, and
`a` happened to be that game's dev fallback key for a different gate. Pick
P1 dev-fallback keys from letters outside `{l, x, r, b, y, a}`.

### Diagnosing input issues on this cabinet

Every game here should keep a `--input-test` mode (see either game's
`input_test.py`) that dumps live joystick button/axis/hat state and keyboard
state to the screen. To use it without a full redeploy: overwrite the
already-deployed `.pygame` loader's content to call `main(["--input-test",
"--fullscreen"])` instead of the normal entry point, have the user launch it
from the existing menu entry, press each physical button one at a time
(release before the next), and read back the raw numbers shown — then restore
the loader (redeploy normally) once done. No ES rescan needed for either step.

## Font quirks (bundled Press Start 2P)

Both games bundle the same Press Start 2P pixel font (OFL-licensed) for
cross-host consistency. Confirmed by rendering candidate glyphs and hashing
the resulting bitmaps:

- The Unicode ket bracket glyphs `⟨`/`⟩` (U+27E8/U+27E9) are **missing** from
  this font and silently render as an invisible box — hence the ASCII `|0>`
  convention instead of proper bra-ket notation.
- The Unicode minus sign `−` (U+2212) is also missing (renders identically to
  the same invisible box) — use the ASCII hyphen-minus `-` instead.
- Confirmed present and safe to use: ASCII `-`, `>`, `<`, plus `√`, `π`, `°`,
  `@`, and `i`.

If a future game wants a glyph not listed here, don't assume it's present —
verify the same way (render it, hash the bitmap, compare against a
known-missing one) before relying on it.
