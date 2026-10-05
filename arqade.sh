#!/usr/bin/env bash
# Start the Munich Quantum Arcade menu on this PC: every game in this repo
# behind one fullscreen menu. Options go to the launcher, for example
#   ./arqade.sh --windowed      ./arqade.sh --kiosk      ./arqade.sh --help
# The first run sets up launcher/.venv (Python 3.11 + pygame), via uv.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v uv >/dev/null 2>&1; then
    echo "arqade: needs uv, see https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi
exec uv run --quiet --project "$here/launcher" arqade "$@"
