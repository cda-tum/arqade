#!/usr/bin/env bash
set -euo pipefail

# Deploy Gate Prix to a Batocera cabinet over SSH/SCP.
#
# Batocera's pygame system just runs `python <file>.pygame` with that file's
# own directory as cwd (see ../AGENTS.md). This script keeps the real game
# code out of the ROMs folder: the package goes to /userdata/games/<game>/,
# and a tiny loader at /userdata/roms/pygame/<game>.pygame points sys.path
# at it and runs it.
#
# Gate Prix was first deployed by hand as an experimental game, its loader
# parked at ${GAMES_DIR}/gate_prix.pygame. This script takes that loader away
# (and the link experimental mode may have left in the ROMs folder) and puts a
# real one in the ROMs folder, which makes the game public.
#
# Usage: ./deploy_batocera.sh [user@host]
#   Defaults to root@batocera.local. Pass root@10.42.0.100 (or whatever the
#   cabinet's actual address is) if mDNS/.local resolution isn't working.

GAME_NAME="gate_prix"
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMES_DIR="/userdata/games/${GAME_NAME}"
ROM_FILE="/userdata/roms/pygame/${GAME_NAME}.pygame"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

cp -r "$SCRIPT_DIR/src/gate_prix" "$STAGE_DIR/gate_prix"
# The idle exit (../batocera/arqade_idle.py) goes beside the package.
cp "$SCRIPT_DIR/../batocera/arqade_idle.py" "$STAGE_DIR/arqade_idle.py"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cat > "$STAGE_DIR/${GAME_NAME}.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for Gate Prix.
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
ssh "$HOST" "mkdir -p '${GAMES_DIR}' && rm -rf '${GAMES_DIR}/gate_prix' '${GAMES_DIR}/gate_prix.pygame'
    if [ -L '${ROM_FILE}' ]; then rm -f '${ROM_FILE}'; fi"
scp -r "$STAGE_DIR/gate_prix" "$HOST:${GAMES_DIR}/gate_prix"
scp "$STAGE_DIR/arqade_idle.py" "$HOST:${GAMES_DIR}/arqade_idle.py"
scp "$STAGE_DIR/${GAME_NAME}.pygame" "$HOST:${ROM_FILE}"
ssh "$HOST" "chmod +x '${ROM_FILE}'"

echo
echo "Deployed."
echo "  Code:   ${GAMES_DIR}/gate_prix/"
echo "  Loader: ${ROM_FILE}"
echo "A first deploy needs the gamelist.xml entry and an EmulationStation restart (see ../AGENTS.md)."
