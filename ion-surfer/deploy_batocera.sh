#!/usr/bin/env bash
set -euo pipefail

# Deploy Ion Surfer to a Batocera cabinet over SSH/SCP.
#
# Batocera's pygame system just runs `python <file>.pygame` with that file's
# own directory as cwd (confirmed against the actual batocera-linux source --
# see quantum-pong/README.md's Batocera section for details/citations). This
# script keeps the real game code out of the ROMs folder: the package goes to
# /userdata/games/<game>/, and a tiny loader script at
# /userdata/roms/pygame/<game>.pygame points sys.path at it and runs it.
#
# Ion Surfer ships two ROMs from the one package: the arcade game
# (ion_surfer.pygame) and the quantum sandbox on its own
# (ion_surfer_sandbox.pygame, same code started with --sandbox).
#
# Usage: ./deploy_batocera.sh [user@host]
#   Defaults to root@batocera.local. Pass root@10.42.0.100 (or whatever the
#   cabinet's actual address is) if mDNS/.local resolution isn't working.

GAME_NAME="ion_surfer"
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMES_DIR="/userdata/games/${GAME_NAME}"
ROM_FILE="/userdata/roms/pygame/${GAME_NAME}.pygame"
SANDBOX_ROM_FILE="/userdata/roms/pygame/${GAME_NAME}_sandbox.pygame"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

# Stage a clean copy of the package (strip dev-only cruft) plus the loader.
cp -r "$SCRIPT_DIR/src/ion_surfer" "$STAGE_DIR/ion_surfer"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
rm -f "$STAGE_DIR/ion_surfer/py.typed"

cat > "$STAGE_DIR/${GAME_NAME}.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for Ion Surfer.
The real game lives at ${GAMES_DIR}, kept separate from the ROMs folder.
"""
import sys

sys.path.insert(0, "${GAMES_DIR}")
from ion_surfer.main import main

if __name__ == "__main__":
    main(["--fullscreen", "--no-keyboard"])
EOF
chmod +x "$STAGE_DIR/${GAME_NAME}.pygame"

cat > "$STAGE_DIR/${GAME_NAME}_sandbox.pygame" <<EOF
#!/usr/bin/env python
"""Batocera entry point for the Ion Surfer quantum sandbox.
The real game lives at ${GAMES_DIR}, kept separate from the ROMs folder.
"""
import sys

sys.path.insert(0, "${GAMES_DIR}")
from ion_surfer.main import main

if __name__ == "__main__":
    main(["--fullscreen", "--no-keyboard", "--sandbox"])
EOF
chmod +x "$STAGE_DIR/${GAME_NAME}_sandbox.pygame"

echo "Deploying to ${HOST} ..."
ssh "$HOST" "mkdir -p '${GAMES_DIR}' && rm -rf '${GAMES_DIR}/ion_surfer'"
scp -r "$STAGE_DIR/ion_surfer" "$HOST:${GAMES_DIR}/ion_surfer"
scp "$STAGE_DIR/${GAME_NAME}.pygame" "$HOST:${ROM_FILE}"
scp "$STAGE_DIR/${GAME_NAME}_sandbox.pygame" "$HOST:${SANDBOX_ROM_FILE}"
ssh "$HOST" "chmod +x '${ROM_FILE}' '${SANDBOX_ROM_FILE}'"

echo
echo "Deployed."
echo "  Code:   ${GAMES_DIR}/ion_surfer/"
echo "  Loader: ${ROM_FILE}"
echo "  Loader: ${SANDBOX_ROM_FILE}"
echo "Restart EmulationStation (or rescan the pygame system) on the cabinet to see it."
