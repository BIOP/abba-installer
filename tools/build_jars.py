"""Builds the jar archive of a release, and its manifest.

    uv run python tools/build_jars.py [--from REPOSITORY]

Resolves ABBA and Fiji into an empty Maven repository cache, as a first install
does without the archive (`abba prepare`, about 15 minutes), or takes a cache
resolved that way (--from). Writes:

    src/abba_installer/jars.txt         the manifest, committed with the release
    dist/ABBA-<version>-jars.zip        attached to the ABBA release on GitHub

The archive holds exactly the files of the manifest, in the layout of the
repository cache. Jars are stored as they are (already compressed), POMs
deflated.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from abba_installer import launcher  # noqa: E402


def resolve_from_scratch(scratch: Path) -> Path:
    """`abba prepare` into an empty repository cache and an empty jgo cache (an
    existing jgo environment would let jgo skip the resolution), with the
    archive off. Short paths: see launcher.WINDOWS_MAX_PATH."""
    repo = scratch / "m2"
    env = dict(os.environ, M2_REPO=str(repo), JGO_CACHE_DIR=str(scratch / "jgo"),
               ABBA_JARS_URL="none")
    print(f"Resolving ABBA and Fiji into {repo} (about 15 minutes)...", flush=True)
    subprocess.run(["uv", "run", "abba", "prepare"], cwd=ROOT, env=env, check=True)
    return repo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from", dest="repo", type=Path,
                        help="a repository cache already resolved from scratch")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="abba-jars-") as scratch:
        repo = args.repo or resolve_from_scratch(Path(scratch))
        files = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*")
                       if path.is_file() and path.suffix in (".jar", ".pom"))
        launcher.JARS_MANIFEST.write_text("\n".join(files) + "\n", encoding="utf-8")
        archive = ROOT / "dist" / launcher.JARS_ARCHIVE
        archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive, "w") as zipped:
            for name in files:
                compression = zipfile.ZIP_STORED if name.endswith(".jar") else zipfile.ZIP_DEFLATED
                zipped.write(repo / name, name, compress_type=compression)
    print(f"{len(files)} files")
    print(f"  manifest: {launcher.JARS_MANIFEST}")
    print(f"  archive:  {archive} ({archive.stat().st_size >> 20} MB)")


if __name__ == "__main__":
    main()
