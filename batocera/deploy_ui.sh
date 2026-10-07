#!/usr/bin/env bash
set -euo pipefail

# Deploy the cabinet's front end over SSH: the game icons in the menu, the
# attract reels (EmulationStation's screensaver after 15 s idle) and the
# loading-screen art (boot video, splash stills). The games themselves deploy
# with their own deploy_batocera.sh.
#
# Usage: ./deploy_ui.sh [--dry-run] [user@host]
#   Defaults to root@batocera.local (fallback: root@10.42.0.100, see AGENTS.md).
#   --dry-run copies everything to the cabinet's staging folders and reports
#   what the install would change, but changes nothing live and leaves
#   EmulationStation running.
#
# The real run restarts EmulationStation once: install_ui.py stops it while it
# edits gamelist.xml and es_settings.cfg (ES rewrites both from memory when it
# exits). The new boot video shows from the next reboot on.

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    shift
fi
HOST="${1:-root@batocera.local}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
THEME_DIR="$REPO/quantum-pong/batocera/arqade-theme"
REELS="$SCRIPT_DIR/attract/reels"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

UI="$STAGE_DIR/arqade-ui"
mkdir -p "$UI/images"
cp "$SCRIPT_DIR/install_ui.py" "$SCRIPT_DIR/kiosk.py" "$SCRIPT_DIR/gamelist.xml" "$UI/"
if ! compgen -G "$REELS/arqade_reel_*.mp4" > /dev/null; then
    echo "no reels in $REELS -- build them with batocera/attract/build_reel.py" >&2
    exit 1
fi
mkdir -p "$UI/reels"
cp "$REELS"/arqade_reel_*.mp4 "$UI/reels/"
# A logo and a marquee for every game in the gamelist, or nothing at all.
for rom in $(sed -n 's#.*<path>\./\(.*\)\.pygame</path>.*#\1#p' "$SCRIPT_DIR/gamelist.xml"); do
    for art in "$SCRIPT_DIR/logos/${rom}-logo.png" "$SCRIPT_DIR/logos/${rom}-marquee.png"; do
        if [[ ! -f "$art" ]]; then
            echo "missing $art -- render it with batocera/logos/generate_logos.py" >&2
            exit 1
        fi
        cp "$art" "$UI/images/"
    done
done

echo "Copying to ${HOST} ..."
ssh "$HOST" "rm -rf /userdata/arqade-ui"
scp -r "$UI" "$HOST:/userdata/arqade-ui"
# tar rather than scp -r: scp would nest the folder inside an existing one.
# -m: the cabinet often has no clock (no NTP on a direct cable), and keeping
# the files' "future" timestamps only makes tar complain.
tar -C "$THEME_DIR" -cf - . | ssh "$HOST" "mkdir -p /userdata/arqade-theme && tar -m -C /userdata/arqade-theme -xf -"

if [[ -n "$DRY_RUN" ]]; then
    echo "(dry run: skipping the theme installer, which has no dry run)"
else
    ssh "$HOST" "python3 /userdata/arqade-theme/install.py"
fi
ssh "$HOST" "python3 /userdata/arqade-ui/install_ui.py $DRY_RUN"

echo
if [[ -n "$DRY_RUN" ]]; then
    echo "Dry run done: nothing live was changed."
else
    echo "Deployed. Leave the menu alone for 15 s to see the reels; reboot to see the boot video."
fi
