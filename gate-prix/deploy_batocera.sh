#!/usr/bin/env bash
set -euo pipefail

# Deploy GATE PRIX to a Batocera cabinet over SSH/SCP.
#
# Batocera's pygame system just runs `python <file>.pygame` with that file's
# own directory as cwd (see ../AGENTS.md). This script keeps the real game
# code out of the ROMs folder: the package goes to /userdata/games/<game>/,
# and a tiny loader that points sys.path at it and runs it.
#
# GATE PRIX is public (2026-10-19): the loader goes in /userdata/roms/pygame/,
# and the game has its batocera/gamelist.xml entry. A public deploy removes the
# loader an earlier deploy PARKED at /userdata/games/<game>/<game>.pygame, and
# the link experimental mode may have made of it. --parked deploys it the old
# way instead: EmulationStation never sees the loader, and the game appears
# only in the cabinet's experimental mode (hold Start + Select on both pads;
# /userdata/experimental.py).
#
# Usage: ./deploy_batocera.sh [--parked] [user@host]
#   Defaults to root@batocera.local. Pass root@10.42.0.100 (or whatever the
#   cabinet's actual address is) if mDNS/.local resolution isn't working.

GAME_NAME="gate_prix"
PUBLIC=1
if [ "${1:-}" = "--parked" ]; then PUBLIC=0; shift; fi
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMES_DIR="/userdata/games/${GAME_NAME}"
if [ "$PUBLIC" = 1 ]; then
    ROM_FILE="/userdata/roms/pygame/${GAME_NAME}.pygame"
else
    ROM_FILE="${GAMES_DIR}/${GAME_NAME}.pygame"
fi
PARKED="${GAMES_DIR}/${GAME_NAME}.pygame"
LINK="/userdata/roms/pygame/${GAME_NAME}.pygame"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

cp -r "$SCRIPT_DIR/src/gate_prix" "$STAGE_DIR/gate_prix"
# The idle exit (../batocera/arqade_idle.py) goes beside the package.
cp "$SCRIPT_DIR/../batocera/arqade_idle.py" "$STAGE_DIR/arqade_idle.py"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cat > "$STAGE_DIR/${GAME_NAME}.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for GATE PRIX.
The real game lives at ${GAMES_DIR}, kept separate from the ROMs folder.
"""
import sys

sys.path.insert(0, "${GAMES_DIR}")
from gate_prix.main import main
import arqade_idle

if __name__ == "__main__":
    arqade_idle.install()  # 20 s untouched: back to the game list
    main(["--fullscreen", "--no-keyboard"])
EOF
chmod +x "$STAGE_DIR/${GAME_NAME}.pygame"

echo "Deploying to ${HOST} ..."
if [ "$PUBLIC" = 1 ]; then  # the parked loader and its link go
    ssh "$HOST" "rm -f '${PARKED}'; if [ -L '${LINK}' ]; then rm -f '${LINK}'; fi"
else  # a real loader in the ROMs folder would keep it public
    ssh "$HOST" "if [ -f '${LINK}' ] && [ ! -L '${LINK}' ]; then rm -f '${LINK}'; fi"
fi
ssh "$HOST" "mkdir -p '${GAMES_DIR}' && rm -rf '${GAMES_DIR}/gate_prix'"
scp -r "$STAGE_DIR/gate_prix" "$HOST:${GAMES_DIR}/gate_prix"
scp "$STAGE_DIR/arqade_idle.py" "$HOST:${GAMES_DIR}/arqade_idle.py"
scp "$STAGE_DIR/${GAME_NAME}.pygame" "$HOST:${ROM_FILE}"
ssh "$HOST" "chmod +x '${ROM_FILE}'"

echo
echo "Deployed."
echo "  Code:   ${GAMES_DIR}/gate_prix/"
echo "  Loader: ${ROM_FILE}"
if [ "$PUBLIC" = 1 ]; then
    echo "A first public deploy needs the gamelist.xml entry and an EmulationStation restart (see ../AGENTS.md)."
else
    echo "Parked: it appears in experimental mode (Start + Select on both pads), no ES restart needed."
fi
