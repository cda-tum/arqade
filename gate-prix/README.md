# Gate Prix

A pseudo-3D kart racer for the ARQADE cabinet (Batocera, `pygame` system),
seen from behind the car, OutRun-style, inside a dilution fridge. Gate
arches stand on the track. Steer through the glowing one, the target
circuit's next gate, to build that circuit gate by gate. Every right gate
is a boost, and the boost grows with the streak. When you cross the line
into the final lap, the CIRCUIT CHECK compares your 16 gates with the
target, and the fewer wrong ones, the bigger the boost to the line. The
final lap has no gates; it is a sprint through the noise storm your wrong
gates left you.

- 6 cars, 3 laps of about 40 s: 1 PLAYER against 5 CPU racers, or
  2 PLAYERS in split screen (P1 blue on the left, P2 red on the right)
  against 4.
- Items from the boxes: SPLIT, QEC, MEASURE, TUNNEL and DECOHERENCE.
- Controls: the car accelerates by itself, the stick steers, pulling it back
  brakes (and drifts, with a direction), A uses the item, Start pauses.

## Sound and music

Every sound effect is synthesised at start-up (`audio.py`). There is no
engine sound: the hum that followed the car's speed was tiring on the
cabinet (2026-10-19). A person's car is heard only while it boosts, as a soft
nitro hiss that gets louder with the boost and fades out when it ends. Every
right gate still rings, with a whoosh.

The title and the HOW TO PLAY card play "vapormall" by Bolt Action, looping
(`src/gate_prix/assets/music/`, from Batocera's own menu music). It fades in
on the title and out when the countdown starts. Its licence allows
non-commercial use with credit, so the title screen credits it, and so does
this README: music by [Bolt Action](https://www.youtube.com/channel/UCduGZR4WsJJ_NGdRhLA07qA),
"vapormall" (`assets/music/LICENSE.md` has the terms).

The design and the look it was built to are in
`../docs/superpowers/specs/2026-10-12-gate-prix-design.md` and
`2026-10-12-gate-prix-look.py`. The rules have moved on since (for example,
gates stand on laps 1 and 2 only), so `src/gate_prix/config.py` is the
reference.

## Where this code came from

The game was built and deployed to the cabinet in another session, and this
repo only had its design until 2026-10-19. The package here was copied back
off the cabinet that day (`/userdata/games/gate_prix/gate_prix/`), so it is
exactly what ran there. Whatever the deploy left out is missing: the
original tests, tools and README. `pyproject.toml`, this README and
`deploy_batocera.sh` were written new.

## Running it

```bash
uv run python -m gate_prix                 # windowed dev run
uv run python -m gate_prix --input-test    # live pad state
uv run python -m gate_prix --selftest 400  # a scripted session through the real loop
uv run python -m gate_prix --selftest 400 --shots /tmp/gp   # ...saving every screen
./deploy_batocera.sh                       # or ./deploy_batocera.sh root@<address>
```

`--selftest` plays the title, a 1P race, a 2P race, the idle return and QUIT
as a visitor would, checking the match all the way, and exits 0 if every
check held.

## On the cabinet

`./deploy_batocera.sh` puts the loader in `/userdata/roms/pygame/`, like the
other games. That makes the game public: it is in `../batocera/gamelist.xml`,
with its logo from `../batocera/logos/logo_gate_prix.py`. Before 2026-10-19
it was experimental, its loader parked beside the package, and the deploy
removes that parked loader. The first time, EmulationStation needs a restart
to list the new ROM, and `../batocera/deploy_ui.sh` installs its name and
logo.
