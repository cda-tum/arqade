#!/usr/bin/env bash
set -euo pipefail

# Deploy Qircuit to a Batocera cabinet over SSH/SCP.
#
# Batocera's pygame system just runs `python <file>.pygame` with that file's
# own directory as cwd (see ../AGENTS.md). This script keeps the real game
# code out of the ROMs folder: the package goes to /userdata/games/<game>/,
# and a tiny loader points sys.path at it and runs it.
#
# Qircuit isn't public yet, so its loader is *parked* beside the package, at
# /userdata/games/<game>/<game>.pygame, where EmulationStation never looks.
# It only shows in the game list in experimental mode: hold Start + Select on
# both pads at once in the menu (see "Experimental games" in ../AGENTS.md).
# To make it public, put the loader in /userdata/roms/pygame/ instead, as the
# other games' deploy scripts do, and give it a batocera/gamelist.xml entry.
#
# Usage: ./deploy_batocera.sh [user@host]
#   Defaults to root@batocera.local. Pass root@10.42.0.100 (or whatever the
#   cabinet's actual address is) if mDNS/.local resolution isn't working.

GAME_NAME="qircuit"
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMES_DIR="/userdata/games/${GAME_NAME}"
LOADER="${GAMES_DIR}/${GAME_NAME}.pygame"
ROM_FILE="/userdata/roms/pygame/${GAME_NAME}.pygame"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

cp -r "$SCRIPT_DIR/src/qircuit" "$STAGE_DIR/qircuit"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cat > "$STAGE_DIR/${GAME_NAME}.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for Qircuit.
The real game lives at ${GAMES_DIR}, kept separate from the ROMs folder.
"""
import sys

sys.path.insert(0, "${GAMES_DIR}")
from qircuit.main import main

if __name__ == "__main__":
    main(["--fullscreen", "--no-keyboard"])
EOF
chmod +x "$STAGE_DIR/${GAME_NAME}.pygame"

echo "Deploying to ${HOST} ..."
ssh "$HOST" "mkdir -p '${GAMES_DIR}' && rm -rf '${GAMES_DIR}/qircuit'"
scp -r "$STAGE_DIR/qircuit" "$HOST:${GAMES_DIR}/qircuit"
scp "$STAGE_DIR/${GAME_NAME}.pygame" "$HOST:${LOADER}"
# A real file in the ROMs folder would make the game public; the link that
# experimental mode makes is fine (it points at the loader just replaced).
ssh "$HOST" "chmod +x '${LOADER}' && { [ -L '${ROM_FILE}' ] || rm -f '${ROM_FILE}'; }"

echo
echo "Deployed, hidden from the game list."
echo "  Code:   ${GAMES_DIR}/qircuit/"
echo "  Loader: ${LOADER} (parked)"
echo "To play it on the cabinet: Start + Select on both pads at once, in the menu."
