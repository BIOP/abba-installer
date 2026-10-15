#!/usr/bin/env bash
# The release zip, attached to the ABBA release on GitHub: what users extract,
# then double-click Start.cmd or Install.cmd in. Made from the committed files
# (git archive), so nothing local - .venv, caches, shortcuts - slips in.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
git archive --format=zip --prefix="ABBA-$version/" -o "ABBA-$version.zip" HEAD
echo "ABBA-$version.zip"
