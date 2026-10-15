#!/usr/bin/env bash
# How many files jgo fetches into an empty cache for the pinned endpoint:
# launcher.EXPECTED_DOWNLOADS, which the progress bar counts against. Run it at
# each release that changes a version. It resolves everything from scratch, as a
# user's first start does: about 15 minutes.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
M2_REPO="$tmp/m2" JGO_CACHE_DIR="$tmp/jgo" uv run abba prepare > /dev/null
echo "EXPECTED_DOWNLOADS = $(find "$tmp/m2" \( -name '*.pom' -o -name '*.jar' \) | wc -l)"
