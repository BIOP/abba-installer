#!/usr/bin/env bash
# The same as "Install for me.cmd", for macOS and Linux: install uv if it is
# missing, then open the ABBA window, where "Install everything" downloads Java,
# ABBA, Fiji, DeepSlice, Elastix and BrainGlobe with a progress bar.
#
#     bash install-for-me.sh
#
# Run it again to open the window, or to update.
set -euo pipefail
cd "$(dirname "$0")"

uv=$(command -v uv || true)
if [ -z "$uv" ] && [ -x "$HOME/.local/bin/uv" ]; then
    uv="$HOME/.local/bin/uv"
fi

if [ -z "$uv" ]; then
    echo "uv is not installed yet; installing it."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv="$HOME/.local/bin/uv"
fi

echo "Opening the ABBA window (the first time: about a minute)."
exec "$uv" run --frozen --no-dev python -m abba_installer.gui
