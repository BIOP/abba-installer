#!/usr/bin/env bash
# The same as Start.cmd, for macOS and Linux: open the ABBA window, which
# starts Fiji with ABBA, installing uv first if it is missing.
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

exec "$uv" run python -m abba_installer.gui
