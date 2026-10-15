<img src="src/abba_installer/assets/icon-256.png" width="64" align="right" alt="ABBA">

# ABBA installer

Installs [ABBA](https://abba-documentation.readthedocs.io) (Aligning Big Brains & Atlases) in its own Fiji,
without installing Fiji, Java or Python first, for you or for every user of a computer.

It runs a **pinned** environment: the same ABBA, Fiji and Java on every computer. Your own Fiji, if you have one,
is neither used nor modified.

| ABBA | Fiji | Java |
|---|---|---|
| 0.25.0 | 2.18.0 | Zulu 21 |

> Already have Fiji? Then you don't need this: enable the `Unige-Biochem` update site, as the
> [installation page](https://abba-documentation.readthedocs.io/en/latest/installation/installation.html)
> describes. This installer is for a computer without Fiji, for a version that must not move, and for
> installing ABBA once for every user of a shared computer.

## Install

Download `ABBA-<version>.zip` from the [ABBA releases](https://github.com/BIOP/ijp-imagetoatlas/releases) and
extract it. Then:

| | **For you** | **For every user** (Windows) |
|---|---|---|
| Run | **`Install for me.cmd`** (macOS, Linux: `bash install-for-me.sh`) | **`Install for all users.cmd`** (asks for administrator rights) |
| Installs into | the extracted folder | `C:\Program Files\ABBA` |
| Java, ABBA, Fiji, DeepSlice, Elastix, BrainGlobe | **Install everything** in the window, or on first use | all downloaded during the installation |
| Then | the **ABBA** shortcut: next to the installer, in your Start Menu, on your Desktop | the **ABBA** shortcut in every user's Start Menu and Desktop |

Both show the same window, with a progress bar. Everything takes about 6 GB; the first installation takes 20 to
30 minutes on a typical connection, most of it fetching the 1900 files of ABBA and Fiji.

<img src="docs/window.png" width="640" alt="The ABBA window">

### For you

`Install for me.cmd` installs [uv](https://docs.astral.sh/uv/) if it is missing (it builds the launcher's Python
environment, and is the only thing installed outside the folder), writes the **ABBA** shortcuts, and opens the
window:

- **Install everything** downloads Java, ABBA, Fiji, DeepSlice, Elastix and BrainGlobe now: do it before a
  workshop or before going offline. *Choose…* leaves out what you don't need (DeepSlice alone is about 3 GB).
- Or **Start ABBA** straight away: what it needs is downloaded when first used (Java, ABBA and Fiji on the
  first start; DeepSlice, Elastix and BrainGlobe when you first use them).

Once installed, the window opens on **Start ABBA**. Closing the window leaves Fiji open. Run the installer
again to update.

### For every user (Windows)

`Install for all users.cmd` installs into `C:\Program Files\ABBA` (or the folder given as its argument). It
downloads everything during the installation, so that users have nothing to fetch, and the window shows the
progress. Users can read that folder but not write to it; their window only offers **Start ABBA**.

Atlases are downloaded when a user first opens one, into `C:\ProgramData\ABBA`, which every user can write: an
atlas downloaded by one user is there for all. To keep them elsewhere (a larger disk), set `ABBA_SHARED_DATA`
before installing.

For unattended deployment, `/quiet` installs without the window and without pausing, printing the progress
instead; the exit code says whether it worked:

```bat
set ABBA_SHARED_DATA=D:\ABBA
"Install for all users.cmd" /quiet
```

To update, run the new version's installer. To uninstall, delete the installation folder, the two shortcuts
and, with the atlases, `C:\ProgramData\ABBA`.

## Command line

The window's actions, for a terminal or a script, from the extracted folder:

```bash
uv run abba start                    # start Fiji with ABBA; Ctrl+C stops following its output, not Fiji
uv run abba start --memory 16G       # Java's maximum heap (default: from the computer's memory)
uv run abba prepare --all            # install everything; or --deepslice --elastix --brainglobe
uv run abba info                     # versions, and where everything is
```

Extra jars, next to ABBA's: `abba start --with GROUP:ARTIFACT:VERSION` (a Maven artifact, resolved from Maven
Central and the SciJava repository) or `--add-jar file.jar`. Both repeatable; to keep them, put them in the
settings file (`abba info` shows where) as `"extra_dependencies"` and `"extra_jars"`. They add jars: they do
not change the versions ABBA is built with.

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

## macOS

- DeepSlice and Elastix need an Apple-silicon Mac: no TensorFlow nor itk-elastix is published for Intel Macs.
  ABBA itself runs on both; the window offers only what the Mac can run.
- Unlike `abba_python` (pyimagej), the launcher starts Fiji as a separate program, as Fiji normally runs, so
  ABBA's window should work. `install-for-me.sh` has not been tested on macOS and Linux yet: reports are welcome.

## How it works

`jgo` resolves one Maven endpoint, `ch.epfl.biop:ImageToAtlasRegister` then `sc.fiji:fiji` (ABBA first, so that
the versions it pins win), into a class path, and runs `net.imagej.Main` on a Zulu 21 fetched by `cjdk`. The
launcher fetches the JDK itself: on its own, jgo would run any Java already installed. **Install everything**
runs `prepare.groovy` headless on the same class path, which asks ABBA to build its Appose environments.

The progress bar counts the files jgo fetches against the number a first installation needs
(`EXPECTED_DOWNLOADS`); the Python environments report no progress, so their part of the bar advances with time.

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
2. `bash tools/count_downloads.sh` (about 15 minutes) and set `EXPECTED_DOWNLOADS` in `launcher.py` to what it
   prints: the progress bar counts the files jgo fetches against it.
3. Try it: `uv run abba prepare --all`, then `uv run abba start` and a registration.
4. Commit, then `bash tools/make_zip.sh`, and attach `ABBA-<version>.zip` to the ABBA release on GitHub.

The icon is drawn by `uv run --no-project --with pillow python tools/make_icon.py`.

## License

The launcher is MIT licensed ([LICENSE.txt](LICENSE.txt)). What it downloads at run time comes with its own
licenses: ABBA (BSD-3), Fiji and its components, DeepSlice (GPL-3), itk-elastix (Apache-2.0), the BrainGlobe
atlas API (BSD-3), and each atlas its own terms.

Developed by Nicolas Chiaruttini. ABBA: [ijp-imagetoatlas](https://github.com/BIOP/ijp-imagetoatlas). For an AI
assistant driving ABBA, see [abba-mcp](https://github.com/unige-biochem/abba-mcp); to drive it from Python,
[abba_python](https://github.com/BIOP/abba_python).
