# Arcade cabinet & hardware notes

This directory holds independent pygame games (`quantum-pong/`,
`quantum-towers/`, `error-invaders/`, `ion-surfer/`, `overquqed/`,
`superconductor/`, `qurves/`, `gate-drop/`, `planck-time/`, `brawl-ket/`, `qircuit/`, more later) built for the same
physical target: a Batocera-based arcade cabinet ("IconicArcade"), a Raspberry
Pi 4 with a 21" 1920x1080 screen and two 6-button joystick pads. (`launcher/`
runs them all from one menu on an ordinary PC instead.) This file
collects hardware facts and hard-won quirks that apply **across games**, so a
future session doesn't have to rediscover them from scratch. Per-game
specifics (gameplay, architecture, tests) belong in each game's own
`README.md`.

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
- **From WSL on a laptop with a direct LAN cable** (2026-10-06): there is no
  DHCP on the cable, so both ends take a link-local 169.254.x.x address, and
  WSL can't resolve `batocera.local` itself. Windows can:
  `ping.exe -4 batocera.local` prints the address, and WSL's own `ssh` reaches
  it. That laptop's key is not on the cabinet, so it logs in with Batocera's
  default root password. The cabinet's clock is wrong without NTP (1980), so
  file timestamps from it mean nothing.

### Display: pick an internal resolution that divides 1080

The panel is 1920x1080 (confirmed by the user). Games render at a fixed
internal size and let SDL's `SCALED` fullscreen upscale it, so a size whose
height divides 1080 scales by a whole number and pixel art stays crisp:
480x270 (x4), 640x360 (x3, used by Planck Time for two GBA-sized screens side by side) and 480x360 (x3, 4:3, used by Overquqed) do; 960x720 (x1.5) and
640x480 (x2.25) don't, and nearest-neighbour then doubles some pixel rows but
not others. Overquqed also sets `SDL_RENDER_SCALE_QUALITY=nearest` before
pygame starts, so the upscale is never blurred.

## Line endings: LF (Linux) everywhere

Every text file in this repo should use **LF** line endings: the target is a
Linux box, and the repo is also edited from WSL. Write new files with LF, and
don't let an editor or a Windows checkout turn existing ones into CRLF.

- It matters most for shell scripts: with CRLF the shebang reads `bash\r` and
  the script doesn't run at all on the cabinet or in WSL
  (`/usr/bin/env: 'bash\r': No such file or directory`). `.gitattributes`
  forces `*.sh` to LF for that reason.
- Much of `quantum-pong/` (and part of `quantum-towers/`) is still committed
  with CRLF from an earlier Windows checkout. When you touch those files, don't
  mix the two styles within one file. Converting them to LF is the goal, but
  do it as its own commit (`* text=auto eol=lf` in `.gitattributes` plus
  `git add --renormalize .`, see the note there), not buried inside a feature
  change, so the diff stays reviewable.
- Check a file with `file <path>` (it says "with CRLF line terminators") or
  list the whole repo with `git ls-files --eol`.

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

### Game names and per-game icons (gamelist.xml)

Without a `gamelist.xml`, EmulationStation shows a ROM's bare filename as its
name — which is why the games first appeared in the menu as `quantum_pong`,
underscores and all. Display names, descriptions and icons all come from
`/userdata/roms/pygame/gamelist.xml`, whose format is standard ES:

```xml
<game>
  <path>./quantum_towers.pygame</path>   <!-- relative to the system's rom dir -->
  <name>Qlimbers</name>
  <desc>…</desc>
  <image>./images/quantum_towers-wide.png</image>
</game>
```

The repo's copy lives in `batocera/gamelist.xml`. The images are the game
logos in `batocera/logos/` (see "Game logos" below); `batocera/icons/` holds
the older, title-less set they replaced. `batocera/deploy_ui.sh` puts both on
the cabinet: it copies every image the gamelist names to
`/userdata/roms/pygame/images/` and has `install_ui.py` *merge* the XML into
the cabinet's own, with ES stopped (see the first point below).

**The game list's tiles are about 2:1, so `<image>` is the wide tile,
`<rom>-wide.png` (1024x512), not the square logo.** The theme's "Icons" view
draws `{game:image}` with `minSize` set to the whole tile, which scales an
image to *cover* the tile. A square logo therefore lost its top and bottom,
title included. The square `<rom>-logo.png` stays for everything else: the PC
launcher's carousel, social posts, slides.

Two things to be careful about:

- **ES owns this file too.** It writes play statistics (`<playcount>`,
  `<lastplayed>`, `<gametime>`) back into it as games are played, so back it
  up and preserve those fields rather than clobbering the whole file — you'd
  otherwise wipe the play history. `install_ui.py` only sets `<name>`,
  `<desc>`, `<image>` and `<marquee>` (and adds missing games), and keeps the
  previous file as `gamelist.xml.arqade-bak`.
- The display name is *only* this `<name>` field. Renaming a game for the
  menu (e.g. Quantum Towers → **Qlimbers**) needs no change to the ROM
  filename, the Python package, or the deploy script.

### Splash screens (boot, menu, and game-launch)

There are three separate splashes, and they come from different places:

| Splash | Shown by | Source |
|---|---|---|
| Boot (at power-on) | `/etc/init.d/S28splash` | a file in `/userdata/splash/` |
| ES start-up (logo + progress bar) | sway wallpaper behind ES | `/etc/sway/config` → `/usr/share/emulationstation/resources/logo.png` |
| Game start/exit (brief flash) | sway wallpaper, in the gap | same `logo.png` |
| Menu start/reload | EmulationStation | theme's `splash.xml` (see below) |
| Game launch ("loading…") | EmulationStation | theme's `gamesplash.xml` |

**The sway wallpaper is the sneaky one.** `/etc/sway/config` has
`output * bg /usr/share/emulationstation/resources/logo.png fill`. That
Batocera logo is what's visible *behind* ES's start-up progress bar and in
the gap while a game launches and exits — so patching every themed splash
still leaves the OS branding flashing up twice. `/` is a writable overlay,
so `install.py` swaps that file (keeping `logo.png.batocera-orig` beside it)
and reloads it live via `swaymsg output '*' bg … fill` — no reboot needed.

**…but writes to `/` do not survive a reboot.** The overlay's upper layer is
a tmpfs (`mount | grep overlay` → `upperdir=/overlay_root/overlay`, and
`/overlay` is `tmpfs`), so the swapped `logo.png` is RAM-only and the
Batocera logo silently comes back on the next boot. This bit us once: the
wallpaper was verified by screenshot, then reverted unnoticed at the next
power cycle. `install.py` therefore also writes `/boot/boot-custom.sh`, which
`/etc/init.d/S00bootcustom` runs on every boot — before sway and ES start —
to copy the logo back. Batocera's own `batocera-save-overlay` is the
alternative, but it carves a 100 MB ext4 image out of `/boot` to snapshot the
whole of `/`.

**`S00bootcustom` runs before `/userdata` exists.** It is the *first* init
script; `/userdata` is not mounted until `S11share` (see the `S…` ordering in
`/etc/init.d/`). A hook that reads from `/userdata` therefore finds nothing
and silently does nothing — which is exactly how the wallpaper fix failed on
its first attempt, and it was missed because the hook was tested *by hand
after boot*, when `/userdata` was mounted. **Testing a boot hook anywhere but
an actual reboot proves nothing.** The image now lives at
`/boot/arqade-logo.png`, alongside the script, and the hook writes a line to
`/tmp/arqade-boot.log` so the next failure is visible instead of silent:

```bash
ssh root@batocera.local "cat /tmp/arqade-boot.log; md5sum /usr/share/emulationstation/resources/logo.png /boot/arqade-logo.png"
```

Anything `/boot/boot-custom.sh` touches must already be on `/boot`.

Anything that must persist belongs under `/userdata` or `/boot`; treat
`/usr`, `/etc` and `/tmp` as scratch.

The theme in use is `mqt` (`ThemeSet` in
`/userdata/system/configs/emulationstation/es_settings.cfg`), and the two
XML files are patched by `quantum-pong/batocera/arqade-theme/install.py` to
point at `./art/mqt_splash.png`.

Not yet checked on the cabinet: batocera-emulationstation's source
(`es-core/src/Splash.cpp`, unchanged since 2020) loads the start-up splash
from `<theme>/splash.xml` and the launch splash from `<theme>/gamesplash.xml`.
Nothing reads `_splash.xml`, the file `install.py` patches, so that patch is
probably a no-op. The start-up splash shows our logo anyway: its default image
is `:/logo.png`, and that is the `/usr/share/emulationstation/resources/logo.png`
the boot hook swaps.

**None of these splashes can animate.** ES draws both of its splashes as
single frames and never updates their components, so a `<video>` or animated
GIF there shows one frame. The spinning logo plays where video does work:
the boot splash and the screensaver (see "Attract reels" below). Every still
(`splash/arqade_splash.png`, `art/mqt_splash.png`) is the spin's first frame,
the logo face on, so all the loading screens show one picture.
`batocera/attract/build_splash.py` makes the boot video and the stills from
`logos/animation/arqade_loading_v3_1080p.webm`.

`install.py` also patches `views/system.xml` (the main menu / system
carousel): it blanks the three metadata labels top left — they come from
`<manufacturer>`/`<fullname>`/`<release>` in `es_systems_mqt.cfg`, but
emptying the *theme's* bindings avoids touching that file, which has taken
the menu to a black screen before — and adds the bottom-right control hints.
Those hints are theme `<text>` elements, deliberately **not** painted into
`art/bg.png`: the theme draws that image through
`<color>${backgroundColor}</color>` (`200000`, near-black), which would tint
any baked-in text to invisibility.

It patches `views/icons.xml` too: the game list is the theme's default
"Icons" view, whose `<autoLayout>0 2</autoLayout>` (two rows, columns from
the cell proportion) shows only 4 x 2 = 8 games on the 16:9 panel. It is set
to `4 3`, so 12 fit on one screen.

Every patch rebuilds from a `.bak` of the original, so `install.py` is safe
to re-run; to see a theme change you must restart ES (or reboot).

**Artwork must be 8-bit PNG.** The original ARQADE splash art was saved as
*16-bit/color* PNG. Nothing in this stack can read that: `fbv` (used for the
boot splash) fails, and EmulationStation fails to load it for the menu and
game-launch splashes — all three silently fall back to Batocera's own logo,
with no error in any log. If a splash "doesn't take", check bit depth first:

```bash
python3 -c "import struct;d=open('FILE.png','rb').read(33);print('bitdepth',d[24])"
```

**The boot splash prefers video.** `S28splash` searches `/userdata/splash/`
for a video (`*.mp4`) first, then an image (`*.png/jpg/jpeg`), and otherwise
plays Batocera's built-in `/usr/share/batocera/splash/splash.mp4` — the
stock logo. The image branch additionally requires `/dev/fb0` *and* `fbv`,
so shipping a `.mp4` is the dependable route (that's the path Batocera's own
default uses, via mpv on DRM). Match the stock video's ~10s length: the
splash is killed when ES takes over, so a short clip just leaves a black
screen for the rest of the boot.

**Watch file permissions.** `install.py` copies with `shutil.copy2`, which
preserves the source's mode — a 600 source file lands as 600 on the cabinet.
It now chmods everything to 644 explicitly.

Debugging notes: `/userdata/system/logs/display.log` and `mpv.log` are only
written by the *video* branch, so a stale copy from an older boot will make
it look like a video played when it didn't — check their timestamps (a date
of 1970/1980 means it predates NTP setting the clock). Verify what the boot
script would actually pick with the script's own matcher:

```bash
find /userdata/splash -maxdepth 1 -regex '.*\.\(mp4\|MP4\)' -type f
find /userdata/splash -maxdepth 1 -regex '.*\.\(jpg\|jpeg\|png\)' -type f
```

### Attract reels (ES screensaver, `batocera/attract/`)

After 15 s without input, on the main menu or in the game list, ES plays the
reels in `batocera/attract/reels/` as its screensaver: the logo turning three
times, then about 20 s of fast gameplay cuts on a CRT tube, with a PRESS ANY
BUTTON badge. Then another reel at random. Any button brings back the screen
you were on. The footage is recorded headless from the games' own code,
driven by per-game bots, and `batocera/attract/README.md` explains how to
re-cut it. `deploy_ui.sh` copies the reels to `/userdata/screensaver/` and runs
`kiosk.py --screensaver`, which sets these ES settings with ES stopped. All of
them were checked against batocera-emulationstation's source (v39 and master):

- **The custom video folder** (`SlideshowScreenSaverCustomVideoSource`,
  `…VideoDir`), not `<video>` tags in the gamelist. "random video" picks from
  every system's games, *hidden systems included*, and Batocera's bundled
  freeware ROMs have videos of their own. From the folder ES picks uniformly
  at random, every time.
- **`ScreenSaverControls=false`.** It defaults to true, and then stick-right
  and Select skip to the next video instead of waking the screensaver.
- **`StopMusicOnScreenSaver=false`.** It defaults to true, which stops the
  menu music for as long as the screensaver runs. Off, the song plays on
  under the reels. The reels have no audio track, so ES doesn't turn the
  music down for them either.
- **Any joystick button wakes it, mapped or not.** Buttons go to the
  screensaver before any mapping lookup, so the kiosk lockdown's unmapped
  Start still works, and the waking press is swallowed. The stick has to
  cross ~70% deflection.
- **Waking never navigates**, and the idle timer runs in every view. Nothing
  extra is needed for "screensaver on both menus, back where you were".
- **`ScreenSaverSwapVideoTimeout` is an hour.** A shorter timeout cuts a
  reel off mid-play. At the end of a file ES shows ~0.5 s of black and fades
  the next in, which is why every reel opens on the logo fading up from black.
- **720p, not 1080p.** libVLC decodes in software on the Pi 4 and every frame
  is uploaded as an RGBA texture.
- **`StartupSystem=pygame`.** The default, `lastsystem`, reopens whatever ES
  showed when it exited, and if that was SNES while unlocked, the next locked
  boot starts on a hidden system. (`StartupOnGameList=true` would boot
  straight into the game list; B still goes back to the carousel. There is
  no setting that removes the carousel; `HideSystemView` does not exist.)
- **Trap:** ES's menu shows `ScreenSaverTime` in whole minutes, so 15 s
  reads as 0, and merely opening and closing Screensaver Settings saves that 0
  and switches the screensaver off. The kiosk lockdown hides that menu; if it
  happens anyway, re-run `kiosk.py --screensaver`.

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

### Kiosk lockdown (`batocera/kiosk.py`)

For public demos the cabinet runs locked: `python3 /userdata/kiosk.py --lock`
(and `--unlock`, `--status`). Browsing and launching the games works
exactly as before; nothing else does.

ES's own restricted UI modes are not enough on their own — Kiosk and Kid only
*hide* menu entries, so START still opens a menu offering Kodi, Information
and Quit. There is no "disable the menu" setting either (the binary has
`ForceKiosk`, `ForceKid` and `ShowHelpPrompts`, and nothing else useful). So
the lockdown works at the input layer instead: it strips `start`, `select`,
`x`, `y`, `pageup` and `pagedown` from every joystick block in
`es_input.cfg`, and ES then never sees the button at all. `ShowHelpPrompts`
turns off the bottom button bar. `UIMode=Kiosk` is still set on top, because
it is the only thing that closes "GAME OPTIONS (HOLD)" — a long press of the
*launch* button, which cannot be unmapped without breaking launching.

Locking also hides Batocera's own systems. `HiddenSystems` in
`es_settings.cfg` carries the list: locked, the carousel is only the four MQT
games; unlocked, SNES/NES/Mega Drive/C64 and the rest come back, each with
the freeware ROM Batocera ships. `LOCKED_HIDDEN_SYSTEMS` in `kiosk.py` is the
list to trim if one of them should be public too.

**Unlocking at the cabinet, with no laptop:** `batocera/unlock_daemon.py`
watches the pads underneath ES and runs `kiosk.py --toggle` when it sees
**L R L R X** (either pad, within 6 seconds). `deploy_ui.sh` installs it as
`/userdata/unlock_daemon.py` and restarts it; its `--install` writes
`/userdata/system/custom.sh`, which `S99userservices` runs on every boot.
It **toggles** -- an unlock-only code leaves no way back into kiosk
mode from the cabinet, which is the whole point of not needing a laptop. That sequence cannot fire by accident: the lockdown unmaps x, y,
pageup and pagedown from `es_input.cfg`, and L/R *were* pageup/pagedown, so
all three buttons are inert in ES — and inside a game they are live, which is
why the daemon ignores everything while a ROM is running.

It costs nothing: it blocks in `select()`, so the kernel does not schedule it
until a button is pressed, and it opens the devices without `EVIOCGRAB`, so
it only observes and can never take input from ES or a game. It rescans for
new event nodes every few seconds, because a pad unplugged and replugged
comes back as a different node.

**The keyboard mapping is left intact deliberately**, and SSH `--unlock` is
the documented way back in. The original `es_input.cfg` is kept beside it as
`es_input.cfg.arqade-orig`, and `--lock` always rebuilds from that copy, so
re-running never compounds.

Two things to know if you touch this:

- **ES rewrites `es_settings.cfg` from memory when it exits**, so stop ES
  *before* editing that file or the edit is thrown away on quit. `kiosk.py`
  does this in the right order.
- `pgrep -x emulationstation` **never matches.** Linux truncates a process's
  `comm` to 15 characters, so it is really `emulationstatio`. Match
  `/proc/*/comm` by prefix; `pgrep -f` is the opposite trap and matches the
  shell running your own script.

`batocera/vpad.py` is the diagnostic that makes any of this checkable from a
desk: it creates a uinput joystick with the cabinet encoders' exact
bus/vendor/product/version, so SDL derives the same GUID and ES applies the
same `es_input.cfg` entry to it. Real button presses, no cabinet required —
that is how the lockdown above was verified rather than assumed.

### Experimental games: a hidden dev mode (`batocera/experimental.py`)

A game that isn't ready for visitors (Qircuit, 2026-10-12) can still be
deployed and tried on the cabinet itself. Its deploy script **parks** the
loader at `/userdata/games/<rom>/<rom>.pygame` instead of in
`/userdata/roms/pygame/`, so ES never lists it. Then:

- **Holding Start + Select on both pads at once**, in the menu, toggles
  experimental mode: every parked game joins the game list, or leaves it.
  The unlock daemon watches for it (only outside a game, and once per hold),
  and runs `experimental.py --toggle`. Nothing on screen names the mode, the
  games just appear. On an unlocked cabinet Start and Select still open ES's
  menus as well; locked, they are inert.
- **It always falls back to the public list.**
  - Idle: a `screensaver-start` ES event hook (written by
    `experimental.py --install` under
    `/userdata/system/configs/emulationstation/scripts/<event>/`) turns it
    off when the cabinet idles into the attract reels.
  - Restarts: `kiosk.py` drops the links before it starts ES again, and the
    unlock daemon runs `experimental.py --reset` whenever it starts (every
    boot): it waits until ES answers, then takes the parked games out of the
    list. A `start` event hook also drops the links as ES starts, but **ES
    doesn't wait for event scripts on Linux** (only for `quit`), so that hook
    races the ROM scan, and it can't be relied on alone.
- **How:** turning it on symlinks each parked loader into the ROMs folder and
  calls ES's local HTTP API (`127.0.0.1:1234`, always on): `POST
  /addgames/pygame` with a partial gamelist adds the games to the running
  list in place, named after the ROM (`qircuit` → `Qircuit`), with no reload
  splash. `POST /removegames/pygame` takes them out again and unlinks their
  files, which are only the links. **Don't point `removegames` at a real
  ROM: it deletes the file.**
- A dangling symlink is no way to hide a game: ES lists it anyway (its
  directory scan never checks the target), and launching it then fails.
- **To make a game public:** have its deploy script write the loader to the
  ROMs folder like the others, and give it a `batocera/gamelist.xml` entry
  and a logo. Not before: the gamelist entry would also put it in the
  attract reels, and the reels are public.
- `python3 /userdata/experimental.py --status` says what is parked, listed
  and hooked; `--on`/`--off` do it over SSH.

Checked on the cabinet (Batocera 39, 2026-10-13): `--on` and `--off` over SSH
add Qircuit to the running list and take it out again (`GET
/systems/pygame/games` shows it), and the parked loader stays. Not yet seen
there: the pad combo, the screensaver hook and a reboot. The event hooks were
checked against batocera-emulationstation's source (`Scripting.cpp`,
`SystemScreenSaver.cpp`, `main.cpp`).

**The cabinet's Python has no numpy, no PyOpenGL and no pip** (checked
2026-10-13). The other games need only pygame; a game that needs more has to
bring it along in its deploy: Qircuit's `deploy_batocera.sh` unpacks the
aarch64 / CPython 3.11 wheels of numpy and PyOpenGL into
`/userdata/games/qircuit/vendor/` and its loader adds that to `sys.path`.
With that it runs, on OpenGL ES under sway (2026-10-13).

## Local PC launcher (`launcher/`, `./arqade.sh`)

Off the cabinet, `./arqade.sh` puts every game behind one fullscreen menu on
an ordinary PC (details in `launcher/README.md`). It plays EmulationStation's
role and keeps Batocera's contract: each game runs in its own process via its
`<package>.main.main(argv)`. A new game needs nothing extra to show up there,
as long as it keeps to what the existing ones do:

- **Folder and package names match** (`gate-drop/src/gate_drop/main.py`).
  The launcher discovers games that way and takes the menu name and text from
  `batocera/gamelist.xml`.
- **`main(argv)` accepts the shared flags**: `--fullscreen`, `--window-size`,
  `--no-keyboard` and `--fps`.
- **A bot in `batocera/attract/bots/<rom>.py`** gets the game into the attract
  reels (the launcher plays the same reels after 15 s on its menu).
- **New dependencies also go into `launcher/pyproject.toml`.** All games run
  in the launcher's one interpreter, and a launcher test fails when one is
  missing.
- **Read input through `pygame.event.get()` and
  `pygame.joystick.Joystick(i)`.** The launcher turns the keyboard into two
  virtual cabinet pads (raw button numbers, analog stick axes) by wrapping
  exactly those, and makes Esc quit. A game that polls with
  `pygame.event.poll()` or `wait()` would not see the pads, and Esc would not
  quit it.

## Button convention (all games must follow this)

Players move between games and must not have to relearn the controls. Every
game on this cabinet uses the same three bindings **wherever the action
exists** — a game with no "back" simply has nothing to bind:

| Action | Button | Raw index |
|---|---|---|
| Confirm / select a menu item | **A** | 1 |
| Back / return to the previous screen | **B** | 2 |
| Start the game from its title or main menu | **Start** | 9 |
| Pause during play | **Start** | 9 |

Notes and deliberate limits:

- This is about **menus, title screens and game-over screens**. In-game, a
  button may mean something else entirely — Pauli Invaders fires with A and
  Qlimbers uses A for RESET — and that is fine. The convention is about how
  you get *into* and *out of* a game, which is what a new player struggles
  with.
- **Start must always work** to begin play from the title/main menu, even
  where A also does. It is the one button a visitor will try first.
- Start + Select together is the universal quit combo, in every game.
- **Start is raw 9 and Select is raw 8**, not the other way round. Every
  game had these swapped at first, which made the button printed SELECT
  confirm menus (the games read raw 8 as "start"). The quit combo needs
  both, so it kept working and hid the mistake. EmulationStation's own
  `es_input.cfg` for this pad has it right: `select id=8`, `start id=9`.
- EmulationStation does not follow this by default — it confirms with B and
  goes back with A. `batocera/kiosk.py --controls` sets ES's `InvertButtons`
  to fix that; the bottom-right hints in the theme (`install.py`) must be kept
  in agreement with it.

### Pausing (all games must follow this)

Every game can be paused, and a paused game is always one step from its own
title screen. That matters on a public cabinet: someone walks up to a game
left mid-round, or a round needs to stop without power-cycling anything.

- **Start pauses** during play, from either pad. Everything freezes: timers,
  falling pieces, the round clock. Select is not a pause button, because it is
  reserved for the Start + Select quit combo.
- **The pause menu offers at least RESUME and QUIT TO TITLE.** QUIT TO TITLE
  goes back to the game's own title or home screen, not out to
  EmulationStation; quitting to ES stays the Start + Select combo. A game may
  add items such as RESTART.
- **In the menu:** the stick moves the selection, A picks an item, and Start
  or B resumes.
- **Start + Select still quits at once**, paused or not, and the idle timeout
  back to the title keeps running while paused.

Where the games stand (2026-10-01): every game follows it except
Superconductor, whose pause screen goes to its menu with Select rather than
through a menu item. That one is deliberately left as it is.

- Gate Drop, Planck Time, Brawl-Ket, Qircuit, Qurves, Quantum Pong, Qlimbers and Pauli Invaders:
  RESUME and QUIT TO TITLE.
- Ion Surfer and Overquqed add RESTART. Ion Surfer's sandbox laser kick moved
  from Start to Select, so that Start can pause there too.
- A title screen reached from QUIT TO TITLE must wait for the buttons to be
  let go, or the A that picked the item starts a new match on its first frame
  (Quantum Pong and Qlimbers do this).

### QUIT on the title menu (all games must follow this)

Playtesters (2026-10-12) asked for one obvious way out of every game. So
every game's title or main menu has a `QUIT` row, the last row of its first
page, which exits the process. That returns to the game list on the cabinet
and to the launcher's menu on a PC. It uses the same exit path as
Start + Select.

- **A on QUIT quits at once**, with no confirmation step.
- **Start never quits.** Start begins play from the title whatever row is
  selected (see the button convention above), and B on the first page does
  nothing.
- The older quit routes stay: Start + Select, holding Select on the title,
  and Esc without `--no-keyboard`.
- Attract bots and title demos never pick QUIT.

### HOW TO PLAY card before every match (all games must follow this)

Also from the 2026-10-12 feedback: a visitor who walks up to a game should
learn its controls and its goal in a few seconds, or be able to mash past
them. Every game therefore shows a full-screen card after the match is set
up (players, mode, map, …) and right before play or the countdown starts:

- It is drawn in the **game's own look** (font, palette, sprites), not as a
  generic overlay. It has a `HOW TO PLAY` heading, a 1–3 line **goal** in
  plain words, an **animated demo** of the core mechanic drawn with the
  game's own code, the **controls** (printed labels STICK/A/B/X/Y/L/R/START,
  ideally as a small drawing of the `L X R / Y B A` cluster with the buttons
  the game uses lit up, P1 and P2 shown separately if they differ), and a
  blinking `PRESS ANY BUTTON TO START` at the bottom.
- **Any button on either pad dismisses it, and the stick doesn't.** Presses
  in the first ~0.3 s are ignored, so the A or Start that confirmed the menu
  can't skip it unseen. After that, mashing gets past it at once. The press
  that dismisses the card does nothing in the game.
- It shows on every match started from the title, but not on an in-match
  RESTART or on a rematch from the game-over screen.
- Start + Select still quits from it, and the game's idle timeout keeps
  running.
- The attract bot has to press a button to get past it.

Where the games stand (2026-10-12): all eleven games have the QUIT row and the
card. The card lives in `<package>/tutorial.py`, except in Overquqed, where
`tutorial.py` was already taken by the playable Training Day level and the
card is `howto.py`. Each demo runs the game's own rules and draw code on a
small scripted scene. Every game also has synthesized sound effects now (Ion
Surfer was the last to get them, in `ion_surfer/sound.py`).

## Player colours: left is blue, right is red (a taste)

The cabinet itself is coloured: the **left** pad's side (joystick 0, P1) is
**blue** and the **right** pad's side (joystick 1, P2) is **red**. A game's
player colours should agree with it, so a player can see at a glance which
bike, paddle or cursor is theirs without reading a label. This is a design
preference of the cabinet's owners rather than a hardware fact, but treat it
like the button convention: new games follow it from the start.

- P1 is blue (or a blue-leaning hue like cyan or teal), and P2 red (or a
  red-leaning hue like orange or pink). Ion Surfer and Qurves use plain blue
  and red.
- When a game has more players than pads, keep each pad's extra player on
  that pad's side of the screen and in a third and fourth colour. Qurves'
  4-player mode, for example, has P3 (left buttons) green and P4 (right
  buttons) purple.
- Games where the two sides aren't players (Superconductor's white and gold
  chips, Pong's white paddles) don't need to change, but blue and red is the
  natural choice there too.

## AI opponents: one AI per game, three levels (a precedent)

Qircuit is the first game with computer opponents, and it sets the pattern
for any game that gets them later.

- **Three levels, named the same everywhere: EASY, TOUGH, BRUTAL.**
  - EASY: a first-time visitor can beat it.
  - TOUGH: a decent player has to work for the win.
  - BRUTAL: as close to perfect as the game allows. It also knows everything
    the game state tells it: items, hazards, where every rival is.
- **A level is a handful of numbers, not separate code.** Qircuit's `ai.py`
  has one `Skill` dataclass and a `SKILLS` dict keyed by level (how hard it
  corners, how early it brakes, how often it thinks, whether it reads the
  gates). One driver class runs all three.
- **One AI per game, in the game's package (`<package>/ai.py`).** It is pure:
  it reads the game's own state and returns the same controls a person's
  input becomes (Qircuit: up or down on its cruise speed, a wire change),
  never more. So it plays by the same rules and is unit tested like the rules.
- **Everything that plays the game without a person uses that one AI:**
  - the in-game opponents;
  - any demo racing behind the title (Qircuit's title shows four bots);
  - the attract-reel bot, `batocera/attract/bots/<rom>.py`, which turns the
    AI's controls into virtual pad presses (`bots/qircuit.py` is short:
    menus, then stick moves).

  The older games' reel bots predate this and keep their own logic. A game
  that gets opponents later moves that logic into its `ai.py`, and its reel
  bot calls it.
- **The title picks people, bots and level.** PLAYERS (people), BOTS (how
  many) and LEVEL (one level for all the bots in a race) are rows of the
  title menu. One person gets bots by default, so a lone visitor always has
  a race. Bots take the places people leave free.
  - At most four people: the cabinet has two sticks and two button clusters.
  - Bots can push the field past four (Qircuit allows 8 cars in all) where
    the game has room for it.
- **Bots never wear a player's colour**, nor a hue leaning towards one. P1–P4
  are blue, red, green and purple, and orange, pink, cyan and teal lean
  towards them (see "Player colours"), so bots get neutral colours (yellow,
  white, grey, tan, ...) and are labelled CPU1, CPU2, and so on. People's
  cars or cursors are marked as well (Qircuit outlines them in white), so you
  find your own among many.
- **Bots don't make every sound.** What happens to them (a bump, a crash)
  sounds as it does for people. Continuous or personal cues (Qircuit's drift
  and red warning, being put back in, taking the lead) sound only for
  people, or eight cars turn into noise.
- **Test the ladder:** alone on the same track, BRUTAL is faster than TOUGH,
  TOUGH than EASY, and EASY clearly slower (`qircuit/tests/test_ai.py`).
  None of them should make the mistakes the game punishes, unless a level
  makes them on purpose.

## Game logos: app icons, each with its own look (a taste)

`batocera/logos/` renders every game's logo with `generate_logos.py`: a
1024x1024 `<rom>-logo.png`, a 1024x512 `<rom>-wide.png` for the cabinet's
game list (the same identity re-laid out, not a crop) and a transparent
`<rom>-marquee.png`. Each game
has its own `logo_<rom>.py`, which imports the game's package and draws with
the game's own sprite and draw functions. `kit.py` has the shared lettering
and light effects. A new game gets a module there too. These preferences were
worked out with the cabinet's owners over several rounds:

- **An app icon, not an arcade thumbnail.** One hero element and the title,
  with plenty of empty space. No taglines, HUD, particles or extra sprites.
  The hero must still be recognisable at 128 px and the title readable at
  256 px.
- **Each icon has its own design language.** Sharing a font is fine. One
  common layout or lettering treatment on every icon is not: the second round
  used the same glow wordmark on all of them, and they lost every distinctive
  trait. The current identities:
  - Pong: stark white on black.
  - Pauli Invaders: flat, hard-edged 8-bit.
  - Ion Surfer: retro surf poster.
  - Superconductor: metro-map routes and a station sign.
  - Overquqed: the one light, warm pixel kitchen.
  - Qlimbers: the title carved into the tower.
  - Qurves: neon tubes over a synthwave floor.
  - Gate Drop: an SNES puzzle-game box, a teal sunburst and bouncy
    candy-coloured letters.
  - Brawl-Ket: a comic-book impact panel (halftone, speed lines, a POW burst).
  - Planck Time: die-cut vinyl stickers on the title screen's purple checker:
    a handheld mid-MEASURE!, its fuse lit, and the rainbow wordmark with its
    stopwatch.

  A new game picks a look none of these already has.
- **Faithful to the game.** Use only elements and colours the game really
  has. Pong's first icon got pushback for a made-up H ring and blue/red ball
  trails the game never draws.
- **Show the core mechanic or conflict, not decoration.**
  - Qurves: one bike cut off by the other.
  - Superconductor: two routes clashing at the game's own red collision X,
    not a rail network.
  - Pong: the paddles matter more than the gate.
- **Motion reads left to right.** The Ion Surfer art is mirrored so the ion
  moves to the right and down the slope.
- The player colours above apply: P1 blue on the left, P2 red on the right.
  Pixel art is scaled up nearest-neighbour by whole numbers.

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

Where the keystrokes come from: Batocera runs **evmapy** for the pygame system
with `batocera-pygame/evmapy.keys` (installed as `/usr/share/evmapy/pygame.keys`).
It only has `actions_player1`, which is why only P1's pad does this. Besides the
six button letters (plus `m`/`s`/`n`/`t` for L2/R2/L3/R3), it maps the d-pad
directions to the **arrow keys**, the left analog stick to **numpad 4/6/8/2**,
start to **Enter**, select to **Space** and hotkey to **h**. So avoiding the six
letters isn't enough on its own. Pauli Invaders used the arrow keys for P2, so
P1's stick also moved P2.

The fix used by every game's loader: `deploy_batocera.sh` calls
`main(["--fullscreen", "--no-keyboard"])`. `--no-keyboard` makes each game's
`input.read_keys()` (and its keyboard event handling) ignore the keyboard
completely, so only the real joystick signals count. The keyboard fallback
still works for local dev runs without the flag. New games should follow the
same pattern.

### The joystick's directional movement is an analog axis, not a hat

Both players' sticks report direction as an **analog axis** (`joystick.get_axis(1)`,
SDL convention: negative = up, positive = down), not a digital hat switch. A
game that reads `joystick.get_hat(n)` for up/down will silently get nothing —
`get_numhats()` is 0 on this cabinet, so the hat branch never fires and no
error is raised either, just an input that quietly never registers.

Quantum Pong got this right from the start (paddle movement always read the
axis: `vertical_axis: 1`, deadzone `0.25`). Quantum Towers' "push up to
confirm" gesture initially assumed a hat switch instead and simply never
worked on the real cabinet — the fix was reusing Pong's exact axis index and
deadzone. Any future game that needs directional stick input on this cabinet
should read the axis from the start; a hat check doesn't hurt as a secondary
fallback (it's harmless when `get_numhats()` is 0) but isn't sufficient on
its own.

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
  `@`, and `i`. Also Greek capitals `Φ` and `Ψ` (and lower-case `α β γ φ ψ`),
  checked the same way for Overquqed's Bell-state labels.
- Also missing: the superscripts `⁺` `⁻` (U+207A/B) and the circuit symbols
  `●` `⊕` (U+25CF, U+2295).
- Proper kets are still possible: `overquqed/src/overquqed/ket.py` builds
  `|Φ⁺⟩` from the font's `|` and `Φ` plus a pixel-drawn `⟩` bracket and
  superscript, at the font's native 8 px, then integer-scales. Copy it if
  another game wants real bra-ket labels.

If a future game wants a glyph not listed here, don't assume it's present —
verify the same way (render it, hash the bitmap, compare against a
known-missing one) before relying on it.
