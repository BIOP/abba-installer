<img src="src/abba_installer/assets/icon-256.png" width="64" align="right" alt="ABBA">

# ABBA installer

Installs [ABBA](https://abba-documentation.readthedocs.io) (Aligning Big Brains & Atlases) in its own Fiji,
without installing Fiji, Java or Python first, for you or for every user of a computer.

It runs a **pinned** environment: the same ABBA, Fiji and Java on every computer. Your own Fiji, if you have one,
is neither used nor modified.

| ABBA | Fiji | Java |
|---|---|---|
| 0.25.0 | 2.18.0 | Zulu 21 |

**To install ABBA, follow the [installation page](https://abba-documentation.readthedocs.io/en/stable/installation/installation.html#install-installer)**
of the documentation: download `ABBA-<version>.zip` from the [ABBA releases](https://github.com/BIOP/ijp-imagetoatlas/releases),
extract it, and run `Install for me.cmd`, or `Install for all users.cmd` for every user of a Windows computer.
That page also describes the other ways to get ABBA: in your own Fiji, with an AI assistant, or from Python.

<img src="docs/window.png" width="640" alt="The ABBA window">

## Extra jars

`uv run abba start --with GROUP:ARTIFACT:VERSION` (a Maven artifact, resolved from Maven Central and the SciJava
repository) or `--add-jar file.jar` adds jars next to ABBA's. Both repeatable; to keep them, put them in the
settings file (`uv run abba info` shows where) as `"extra_dependencies"` and `"extra_jars"`. They add jars: they
do not change the versions ABBA is built with.

## Where things go

| What | For you | For every user |
|---|---|---|
| Launcher and its Python | the extracted folder (`.venv`) | the installation folder |
| Java, ABBA and Fiji's jars | jgo's and cjdk's caches in your profile | the installation folder (`java`) |
| DeepSlice, Elastix, BrainGlobe | `~/.local/share/appose` | the installation folder (`appose`) |
| Atlases | `~/cached_atlas`, `~/.brainglobe` | `C:\ProgramData\ABBA` |
| Fiji's log, settings | `%LOCALAPPDATA%\abba-installer`, `%APPDATA%\abba-installer` (`~/.local/share`, `~/.config` elsewhere) | the same, per user |

For you, the Python environments and the atlases are where a Fiji with ABBA on the same computer keeps them:
they are downloaded once for both.

## How it works

`jgo` resolves one Maven endpoint, `ch.epfl.biop:ImageToAtlasRegister` then `sc.fiji:fiji` (ABBA first, so that
the versions it pins win), into a class path, and runs `net.imagej.Main` on a Zulu 21 fetched by `cjdk`. The
launcher fetches the JDK itself: on its own, jgo would run any Java already installed. **Install everything**
runs `prepare.groovy` headless on the same class path, which asks ABBA to build its Appose environments.

ABBA and Fiji are some 1900 files (jars and POMs). jgo fetches them one at a time, which takes 15 to 25 minutes,
mostly spent waiting between files. So when most of them are missing, the launcher first downloads them all in
one archive from the release (`ABBA-<version>-jars.zip`, 0.5 GB, or a copy next to the installer) and unpacks
it into jgo's repository cache: jgo then finds them there. Before unpacking, it checks that jgo really uses that
cache: it asks jgo for one small artifact and looks where it lands. The cache is always passed to jgo
(`--repo-cache`), never assumed. Files already there are never overwritten, and any problem (no network,
another cache, a path too long for Windows) leaves jgo to fetch the files one by one, as without the archive.
`jars.txt` lists the archive's files: what is missing is what the launcher downloads.

The progress bar counts the archive's bytes, then the files jgo still fetches; the Python environments report no
progress, so their part of the bar advances with time.

| File | Role |
|---|---|
| `src/abba_installer/launcher.py` | versions, the jgo command line, starting Fiji, installing, progress |
| `src/abba_installer/gui.py`, `cli.py` | the window and the command line |
| `src/abba_installer/prepare.groovy` | builds the Python environments through ABBA's own code |
| `Install for me.cmd`, `install-for-me.sh` | install uv if missing, write the shortcuts, open the window |
| `Install for all users.cmd` | the installation for every user |

## Releasing (maintainers)

The launcher's version is the ABBA version it runs, with `.post1`, `.post2`... for a fix of the launcher alone.

1. Set `ABBA_VERSION` (and `FIJI_VERSION` if needed) in `launcher.py`, the version in `__init__.py` and
   `pyproject.toml`, and the table at the top of this README; `uv lock`; `uv run pytest`.
2. `uv run python tools/build_jars.py` (about 15 minutes: it resolves everything from scratch). It writes the
   manifest `src/abba_installer/jars.txt` and the archive `dist/ABBA-<version>-jars.zip`.
3. Try it: `uv run abba prepare --all`, then `uv run abba start` and a registration.
4. Commit, then `bash tools/make_zip.sh`, and attach both `ABBA-<version>.zip` and `ABBA-<version>-jars.zip` to
   the ABBA release on GitHub, whose tag is the ABBA version: the launcher downloads the archive from there.

The icon is drawn by `uv run --no-project --with pillow python tools/make_icon.py`.

## License

The launcher is MIT licensed ([LICENSE.txt](LICENSE.txt)). What it downloads at run time comes with its own
licenses: ABBA (BSD-3), Fiji and its components, DeepSlice (GPL-3), itk-elastix (Apache-2.0), the BrainGlobe
atlas API (BSD-3), and each atlas its own terms.

Developed by Nicolas Chiaruttini. ABBA: [ijp-imagetoatlas](https://github.com/BIOP/ijp-imagetoatlas). For an AI
assistant driving ABBA, see [abba-mcp](https://github.com/unige-biochem/abba-mcp); to drive it from Python,
[abba_python](https://github.com/BIOP/abba_python).
