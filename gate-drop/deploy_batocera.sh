#!/usr/bin/env bash
set -euo pipefail

# Deploy Gate Drop to a Batocera cabinet over SSH/SCP.
#
# Batocera's pygame system just runs `python <file>.pygame` with that file's
# own directory as cwd (see ../AGENTS.md). This script keeps the real game
# code out of the ROMs folder: the package goes to /userdata/games/<game>/,
# and a tiny loader at /userdata/roms/pygame/<game>.pygame points sys.path
# at it and runs it.
#
# Usage: ./deploy_batocera.sh [user@host]
#   Defaults to root@batocera.local. Pass root@10.42.0.100 (or whatever the
#   cabinet's actual address is) if mDNS/.local resolution isn't working.

GAME_NAME="gate_drop"
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMES_DIR="/userdata/games/${GAME_NAME}"
ROM_FILE="/userdata/roms/pygame/${GAME_NAME}.pygame"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

cp -r "$SCRIPT_DIR/src/gate_drop" "$STAGE_DIR/gate_drop"
# Code shared by all games goes next to the game's own package.
cp -r "$SCRIPT_DIR/../common/src/arqade_common" "$STAGE_DIR/arqade_common"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
rm -f "$STAGE_DIR/gate_drop/py.typed" "$STAGE_DIR/arqade_common/py.typed"

cat > "$STAGE_DIR/${GAME_NAME}.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for Gate Drop.
The real game lives at ${GAMES_DIR}, kept separate from the ROMs folder.
"""
import asyncio
import sys

sys.path.insert(0, "${GAMES_DIR}")
from gate_drop.main import main

if __name__ == "__main__":
    asyncio.run(main(["--fullscreen", "--no-keyboard"]))
EOF
chmod +x "$STAGE_DIR/${GAME_NAME}.pygame"

echo "Deploying to ${HOST} ..."
ssh "$HOST" "mkdir -p '${GAMES_DIR}' && rm -rf '${GAMES_DIR}/gate_drop' '${GAMES_DIR}/arqade_common'"
scp -r "$STAGE_DIR/gate_drop" "$HOST:${GAMES_DIR}/gate_drop"
scp -r "$STAGE_DIR/arqade_common" "$HOST:${GAMES_DIR}/arqade_common"
scp "$STAGE_DIR/${GAME_NAME}.pygame" "$HOST:${ROM_FILE}"
ssh "$HOST" "chmod +x '${ROM_FILE}'"

echo
echo "Deployed."
echo "  Code:   ${GAMES_DIR}/gate_drop/ and ${GAMES_DIR}/arqade_common/"
echo "  Loader: ${ROM_FILE}"
echo "A first deploy needs the gamelist.xml entry and an EmulationStation restart (see ../AGENTS.md)."
