"""How ABBA is started: a pinned Fiji, resolved by jgo, on a pinned Java.

Nothing here is an ABBA or a Fiji installation. `jgo` resolves one Maven
endpoint - ABBA plus Fiji, both pinned below - into a class path, and starts
it on a JDK fetched through cjdk. So every machine runs the same ABBA, the same
Fiji and the same Java, whatever else is installed, and the user's own Fiji is
neither used nor modified.

DeepSlice, Elastix and the BrainGlobe atlas API are not handled here: ABBA
builds their Python environments itself, through Appose, the first time they
are used. `prepare()` only asks it to do so ahead of time.

Two layouts, told apart by a `java` folder next to the virtual environment:

- **per user** (`Start.cmd`, `start.sh`): everything goes to the user's own
  caches - jgo's, cjdk's, Appose's (`~/.local/share/appose`) and ABBA's atlas
  folders - which a Fiji with ABBA on the same machine shares.
- **every user** (`Install.cmd`): an administrator downloaded the JDK, the jars
  and the Python environments into the installation folder, which users can
  read but not write. Atlases, which are downloaded on demand, go to one folder
  every user can write (`%ProgramData%\\ABBA`).
"""

from __future__ import annotations

import functools
import math
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

#: What this launcher runs. ABBA goes first: in a jgo endpoint the first
#: artifact's managed versions win, and ABBA pins atlas, biop-tools and
#: bigdataviewer-playground versions that Fiji's own would otherwise replace.
ABBA_VERSION = "0.25.0"
FIJI_VERSION = "2.18.0"
ENDPOINT = [f"ch.epfl.biop:ImageToAtlasRegister:{ABBA_VERSION}",
            f"sc.fiji:fiji:{FIJI_VERSION}"]
SCIJAVA_REPO = "https://maven.scijava.org/content/groups/public"

#: What Fiji ships and ABBA is compiled for. Pinned, not left to jgo: on its own
#: jgo runs any Java already installed that is at least this version, and a
#: machine with a newer Java on its PATH would run ABBA on it.
JAVA_VERSION, JAVA_VENDOR = "21", "zulu"

FIJI_MAIN = "net.imagej.Main"
GROOVY_MAIN = "groovy.ui.GroovyMain"

HERE = Path(__file__).resolve().parent
PREPARE_SCRIPT = HERE / "prepare.groovy"
#: Without a configuration logback logs at DEBUG, and no jar of the endpoint
#: ships one. It goes on the class path inside a jar (`logback_jar()`): jgo
#: turns every --add-classpath entry into `<entry>/*`, which only matches jars.
LOGBACK_XML = HERE / "logback.xml"

#: --lenient: a dependency of the stack leaves a POM property unresolved.
#: --class-path-only: every jar on the class path, the way Fiji runs them.
JGO_FLAGS = ["--color", "plain", "--lenient", "--class-path-only",
             "--java-version", JAVA_VERSION, "--java-vendor", JAVA_VENDOR,
             "--timeout", "120", "-r", f"scijava:{SCIJAVA_REPO}"]

#: jgo 3.1 drops JVM arguments given after its `--`, so they travel in the
#: environment. The add-opens is not optional: without it the ImageJ 1.x
#: patcher fails under Java 21.
JAVA_TOOL_OPTIONS = ("--add-opens=java.base/java.lang=ALL-UNNAMED "
                     "-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8")

#: Lines every start prints that say nothing to a user: those containing these.
NOISE = ("Picked up JAVA_TOOL_OPTIONS", "JavaScriptScriptLanguage")


def noise(line: str) -> bool:
    return any(text in line for text in NOISE)

#: How prepare.groovy marks its lines for the user, Appose's while building, and
#: the start and end of each environment (`ABBA_PHASE deepslice start`).
PREPARE_MARK, PREPARE_LOG, PHASE_MARK = "ABBA_PREPARE ", "ABBA_PREPARE_LOG ", "ABBA_PHASE "
#: What the JVM prints first, JAVA_TOOL_OPTIONS being set: jgo has resolved
#: everything. Before it, every line is jgo's.
JVM_STARTED = "Picked up JAVA_TOOL_OPTIONS"
#: What jgo prints for every file it fetches.
DOWNLOADING = "Downloading "
#: How much of the rest to keep, shown when preparing fails.
TAIL_LINES = 60

#: The environments `prepare()` can build, with what the user is told they cost.
ENVIRONMENTS = {
    "deepslice": "DeepSlice (about 3 GB)",
    "elastix": "Elastix (about 1.3 GB)",
    "brainglobe": "BrainGlobe atlas API (about 0.6 GB)",
}
#: On disk, in GB, measured: for the size the window announces.
SIZES_GB = {"java": 0.3, "jars": 0.5, "deepslice": 2.9, "elastix": 1.3, "brainglobe": 0.6}


def supported_environments() -> list[str]:
    """The environments this computer can run: TensorFlow and itk-elastix
    publish nothing for Intel Macs."""
    if sys.platform == "darwin" and platform.machine() == "x86_64":
        return ["brainglobe"]
    return list(ENVIRONMENTS)


def install_size_gb(environments: list[str]) -> float:
    return sum(SIZES_GB[name] for name in ["java", "jars", *environments])

# --------------------------------------------------------------------------- #
#  Where things are
# --------------------------------------------------------------------------- #

#: The installation folder: the one holding the virtual environment.
APP = Path(sys.prefix).parent
#: Written by Install.cmd. When it exists, nothing goes to the user's caches.
SHARED = APP / "java"
SHARED_JDK = SHARED / "jdk"
SHARED_APPOSE = APP / "appose"


def shared() -> bool:
    return SHARED.is_dir()


#: Where Install.cmd recorded the shared atlas folder, for the users' sessions.
SHARED_DATA_RECORD = SHARED / "shared-data.txt"


def shared_data() -> Path:
    """Where every user of a shared installation keeps the atlases:
    %ProgramData%\\ABBA, unless the administrator set ABBA_SHARED_DATA when
    installing (recorded then, since users do not have that variable)."""
    if SHARED_DATA_RECORD.exists():
        return Path(SHARED_DATA_RECORD.read_text(encoding="utf-8").strip())
    configured = os.environ.get("ABBA_SHARED_DATA")
    if configured:
        return Path(configured)
    return Path(os.environ.get("ProgramData") or "C:/ProgramData") / "ABBA"


def user_dir() -> Path:
    """The user's own folder: Fiji's log, and the folder Fiji starts in."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "abba-installer"


def fiji_log() -> Path:
    return user_dir() / "fiji.log"


def repo_cache() -> Path:
    """jgo's Maven repository cache, where the jars go: the installation's
    for every user; for one user, Maven's own (M2_REPO, else ~/.m2/repository),
    which jgo and Maven share."""
    if shared():
        return SHARED / "m2"
    configured = os.environ.get("M2_REPO")
    return Path(configured) if configured else Path.home() / ".m2" / "repository"


def appose_envs_dir() -> Path:
    """Where ABBA's Python environments are: Appose's own default, unless shared."""
    if shared():
        return SHARED_APPOSE
    configured = os.environ.get("APPOSE_ENVS_DIR")
    return Path(configured) if configured else Path.home() / ".local" / "share" / "appose"


# --------------------------------------------------------------------------- #
#  Java and jgo
# --------------------------------------------------------------------------- #

def java_executable(home: Path) -> Path:
    return home / "bin" / ("java.exe" if os.name == "nt" else "java")


def java_home(say: Callable[[str], None] = print) -> Path:
    """The pinned JDK, downloaded on first use (into cjdk's cache, which jgo
    shares), or the copy a shared installation holds."""
    if shared():
        if not java_executable(SHARED_JDK).exists():
            raise RuntimeError(f"{SHARED_JDK} is missing: run Install.cmd again.")
        return SHARED_JDK
    import cjdk

    # cjdk cannot be asked whether the JDK is cached: a lookup that takes more
    # than a moment is a download, and only then is the user told.
    notice = threading.Timer(1.5, say, [f"Downloading Java {JAVA_VERSION} ({JAVA_VENDOR}), once..."])
    notice.start()
    try:
        return Path(cjdk.java_home(vendor=JAVA_VENDOR, version=JAVA_VERSION, progress=False))
    finally:
        notice.cancel()


def fetch_shared_jdk(say: Callable[[str], None]) -> None:
    """Copy the JDK into the shared folder, once.

    Not left in cjdk's cache: cjdk rewrites its index there, and users cannot
    write to the shared folder. A plain JDK at a fixed place is what
    `environment()` points jgo to instead.
    """
    if java_executable(SHARED_JDK).exists():
        return
    import cjdk

    say(f"Downloading Java {JAVA_VERSION} ({JAVA_VENDOR}) for every user...")
    home = cjdk.java_home(vendor=JAVA_VENDOR, version=JAVA_VERSION, progress=False)
    part = SHARED_JDK.with_name(SHARED_JDK.name + ".part")
    shutil.rmtree(part, ignore_errors=True)
    shutil.copytree(home, part)
    # A virus scanner reading the new files keeps the folder from being renamed
    # for a few seconds.
    for attempt in range(60):
        try:
            part.replace(SHARED_JDK)
            break
        except PermissionError:
            if attempt == 59:
                raise
            time.sleep(1)
    say(f"  {SHARED_JDK}")


def console_python() -> str:
    """The Python to run jgo with: never pythonw.exe, which the window runs on.

    The java.exe jgo starts is a console program: under pythonw it would get a
    visible console of its own. Under python.exe started with CREATE_NO_WINDOW
    it shares that hidden one.
    """
    executable = Path(sys.executable)
    console = executable.with_name("python.exe")
    if executable.name.lower() == "pythonw.exe" and console.exists():
        return str(console)
    return sys.executable


def environment(home: Path, headless: bool) -> dict[str, str]:
    options = JAVA_TOOL_OPTIONS + (" -Djava.awt.headless=true" if headless else "")
    # jgo is Python too: unbuffered, its "Downloading" lines arrive as they happen, which
    # the progress bar counts; UTF-8, its progress bars hold characters a code page has not.
    env = dict(os.environ, JAVA_TOOL_OPTIONS=options, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    # jgo looks at JAVA_HOME, then PATH; on Windows only PATH counts, because it
    # looks for bin/java, not bin/java.exe. Both are set.
    env["JAVA_HOME"] = str(home)
    env["PATH"] = os.pathsep.join([str(java_executable(home).parent), env.get("PATH", "")])
    if shared():
        env["APPOSE_ENVS_DIR"] = str(SHARED_APPOSE)
        env["BRAINGLOBE_CONFIG_DIR"] = str(shared_data() / "brainglobe-config")
    return env


def logback_jar() -> Path:
    """`logback.xml` in a jar of its own, in the user's folder; rewritten only
    when the configuration changed."""
    jar = user_dir() / "logback-config.jar"
    config = LOGBACK_XML.read_bytes()
    try:
        with zipfile.ZipFile(jar) as existing:
            if existing.read("logback.xml") == config:
                return jar
    except (OSError, KeyError, zipfile.BadZipFile):
        pass
    jar.parent.mkdir(parents=True, exist_ok=True)
    part = jar.with_name(jar.name + ".part")
    with zipfile.ZipFile(part, "w") as archive:
        archive.writestr("logback.xml", config)
    part.replace(jar)
    return jar


def jgo_argv(main_class: str, *, max_heap: str | None = None,
             extra_dependencies: list[str] = (), extra_jars: list[Path] = (),
             args: list[str] = ()) -> list[str]:
    """The jgo command line. Extra dependencies go after ABBA and Fiji, so that
    they add jars without changing the versions ABBA is built with."""
    # The repository cache is always given: it is where fetch_jars() unpacks the
    # jar archive, so it must be where jgo looks, not where it is assumed to look.
    caches = ["--repo-cache", str(repo_cache())]
    if shared():
        caches += ["--cache-dir", str(SHARED / "jgo")]
    heap = ["--max-heap", max_heap] if max_heap else []
    classpath = [arg for path in [logback_jar(), *extra_jars]
                 for arg in ("--add-classpath", str(path))]
    endpoint = "+".join([*ENDPOINT, *extra_dependencies])
    # The two `--` are jgo's: the first ends jgo's arguments, the second the JVM's.
    tail = ["--", "--", *args] if args else []
    return [console_python(), "-m", "jgo", *JGO_FLAGS, *caches, *heap, "run",
            "--main-class", main_class, *classpath, endpoint, *tail]


def _process_flags(detached: bool) -> dict:
    """No console window on Windows. Detached: a process group (or session) of
    its own, so that closing the window or the terminal leaves Fiji running."""
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        if detached:
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        return {"creationflags": flags}
    return {"start_new_session": True} if detached else {}


# --------------------------------------------------------------------------- #
#  Starting Fiji
# --------------------------------------------------------------------------- #

@dataclass
class Options:
    max_heap: str | None = None
    extra_dependencies: list[str] = field(default_factory=list)
    extra_jars: list[Path] = field(default_factory=list)


def work_dir() -> Path:
    """The folder Fiji starts in. ABBA reads its atlas folder from
    `plugins/BIOP/ABBA_Atlas_folder.txt` relative to it: a shared installation
    writes one there, pointing every user to the same atlases."""
    work = user_dir() / "work"
    marker = work / "plugins" / "BIOP" / "ABBA_Atlas_folder.txt"
    if shared():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(shared_data() / "atlases"), encoding="utf-8")
    else:
        work.mkdir(parents=True, exist_ok=True)
        marker.unlink(missing_ok=True)
    return work


def start_fiji(options: Options, say: Callable[[str], None] = print,
               progress: Progress | None = None) -> subprocess.Popen:
    """Start Fiji with ABBA, detached, its output going to `fiji_log()`.

    Detached and logging to a file rather than a pipe: the window or the
    terminal that started it can close, and Fiji goes on. Before it, the jar
    archive when most jars are missing (a first start without Install).
    """
    progress = progress or Progress()
    home = java_home(say)
    progress.finish("java")
    fetch_jars(home, say, progress)
    log_path = fiji_log()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    argv = jgo_argv(FIJI_MAIN, max_heap=options.max_heap,
                    extra_dependencies=options.extra_dependencies,
                    extra_jars=options.extra_jars)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"ABBA {ABBA_VERSION}, Fiji {FIJI_VERSION}, Java {home}\n"
                  f"{' '.join(argv)}\n\n")
        log.flush()
        return subprocess.Popen(argv, cwd=work_dir(), env=environment(home, headless=False),
                                stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, **_process_flags(detached=True))


# --------------------------------------------------------------------------- #
#  Progress
# --------------------------------------------------------------------------- #

#: Rough durations on a typical connection, in seconds. They weigh the phases
#: against each other, and stand in for the progress of the ones that report
#: none: Java's download, and building a Python environment. "jars" is jgo
#: putting the class path together with every file cached; each file it still
#: has to fetch adds SECONDS_PER_DOWNLOAD (`Progress.set_missing`).
DURATIONS = {"java": 60, "archive": 100, "jars": 70,
             "deepslice": 480, "elastix": 120, "brainglobe": 60}
#: What jgo takes per file it fetches, measured: latency, not bandwidth.
SECONDS_PER_DOWNLOAD = 0.47


class Progress:
    """An approximate progress over what a first start or an install does:
    fetch Java, the jar archive, resolve ABBA and Fiji (jgo), build the Python
    environments.

    The archive reports its own progress (`archive_step`); jgo's fetches are
    counted (`Downloading` lines against the files still missing); a phase
    without a count advances with time instead, along a curve that slows down
    rather than reaching its end before the phase does. With warm caches,
    phases just finish early. Read from another thread than the one feeding
    it: only plain values.
    """

    def __init__(self, environments: list[str] = ()) -> None:
        self.phases = ["java", "archive", "jars", *environments]
        self.durations = dict(DURATIONS)
        self.done: set[str] = set()
        self.started = {"java": time.monotonic()}
        self.downloads = 0
        self.archive_fraction = 0.0
        self.archive_label = ""
        self.set_missing(expected_downloads())

    def set_missing(self, missing: int) -> None:
        """How many files jgo still has to fetch: all of them, or what the jar
        archive did not bring."""
        self.missing = missing
        self.durations["jars"] = DURATIONS["jars"] + SECONDS_PER_DOWNLOAD * missing

    def archive_step(self, fraction: float, label: str, total_bytes: int = 0) -> None:
        self.archive_fraction, self.archive_label = fraction, label
        if total_bytes:  # weighs the download as it is: about 5 MB/s
            self.durations["archive"] = max(DURATIONS["archive"], total_bytes / 5e6)

    def feed(self, line: str) -> None:
        if line.startswith(DOWNLOADING):
            self.downloads += 1
        elif line.startswith(JVM_STARTED):
            for phase in ("java", "archive", "jars"):
                self.finish(phase)
        elif line.startswith(PHASE_MARK):
            phase, _, state = line[len(PHASE_MARK):].partition(" ")
            if state == "start":
                self.started[phase] = time.monotonic()
            else:
                self.finish(phase)

    def finish(self, phase: str) -> None:
        self.done.add(phase)
        following = self.current
        if following is not None:
            self.started.setdefault(following, time.monotonic())

    def finish_all(self) -> None:
        self.done.update(self.phases)

    @property
    def current(self) -> str | None:
        return next((phase for phase in self.phases if phase not in self.done), None)

    def phase_fraction(self, phase: str) -> float:
        if phase in self.done:
            return 1.0
        if phase == "archive":
            return min(self.archive_fraction, 0.99)
        if phase == "jars" and self.missing:
            return min(self.downloads / self.missing, 0.99)
        if phase not in self.started:
            return 0.0
        elapsed = time.monotonic() - self.started[phase]
        return 0.95 * (1 - math.exp(-elapsed / self.durations[phase]))

    def fraction(self) -> float:
        weights = {phase: self.durations[phase] for phase in self.phases}
        return (sum(weights[phase] * self.phase_fraction(phase) for phase in self.phases)
                / sum(weights.values()))

    def label(self) -> str:
        phase = self.current
        if phase is None:
            return "Done."
        if phase == "java":
            return f"Java {JAVA_VERSION}: checking, downloaded the first time"
        if phase == "archive":
            return self.archive_label or "ABBA and Fiji: checking what is already there"
        if phase == "jars":
            if self.downloads:
                return (f"ABBA and Fiji: {self.downloads} of about {self.missing} files "
                        "(the first time only)")
            return "ABBA and Fiji: putting them together"
        return f"{ENVIRONMENTS[phase].split(' (')[0]}: building its Python environment"


class FijiOutput:
    """Fiji's log, as a user should see it.

    Until the JVM starts, every line is jgo resolving: fed to `progress`, held
    back, and shown only if Fiji ends before it started, since that is when
    those lines explain why. From then on, everything but NOISE.
    """

    def __init__(self, progress: Progress) -> None:
        self.progress = progress
        self.jvm_started = False
        self.held: deque[str] = deque(maxlen=TAIL_LINES)

    def __call__(self, line: str) -> str | None:
        self.progress.feed(line)
        if not self.jvm_started:
            if line.startswith(JVM_STARTED):
                self.jvm_started = True
                self.held.clear()
            elif line.strip():
                self.held.append(line)
            return None
        return None if noise(line) else line

    def unexplained(self) -> list[str]:
        """What jgo said, when Fiji ended before starting."""
        return [] if self.jvm_started else list(self.held)


# --------------------------------------------------------------------------- #
#  The jars in one archive
# --------------------------------------------------------------------------- #

#: ABBA and Fiji's jars and POMs, as jgo fetches them into an empty cache, in
#: one zip on the GitHub release. jgo fetches them one at a time: some 1900
#: files, 15 to 25 minutes, mostly spent waiting between files. One download
#: of the same 0.5 GB takes minutes. Made by tools/build_jars.py.
JARS_ARCHIVE = f"ABBA-{ABBA_VERSION}-jars.zip"
JARS_URL = ("https://github.com/BIOP/ijp-imagetoatlas/releases/download/"
            f"{ABBA_VERSION}/{JARS_ARCHIVE}")
#: What the archive holds, one path per line relative to the repository cache:
#: what is missing, and how many files jgo fetches without it.
JARS_MANIFEST = HERE / "jars.txt"
#: With fewer files missing, jgo fetches them faster than the archive downloads.
ARCHIVE_THRESHOLD = 50
#: A tiny artifact of the manifest, without dependencies: jgo is asked for it
#: before the archive is unpacked, to check that it uses the repository cache
#: the archive is about to go into.
PROBE = "aopalliance:aopalliance:1.0"
PROBE_PATH = "aopalliance/aopalliance/1.0/aopalliance-1.0.jar"
#: Longer paths are invisible to Python on a Windows without long paths: jgo
#: would not see the files the archive put there.
WINDOWS_MAX_PATH = 259


@functools.cache
def manifest() -> tuple[str, ...]:
    return tuple(line for line in JARS_MANIFEST.read_text(encoding="utf-8").splitlines() if line)


def expected_downloads() -> int:
    """How many files jgo fetches into an empty cache."""
    return len(manifest())


def missing_files(repo: Path) -> list[str]:
    return [path for path in manifest() if not (repo / path).exists()]


def archive_source() -> str | None:
    """The archive: a copy next to the installation (an installation without
    internet), or the release. ABBA_JARS_URL replaces the release; "none"
    turns the archive off."""
    configured = os.environ.get("ABBA_JARS_URL")
    if configured:
        return None if configured == "none" else configured
    for folder in (APP, Path(os.environ.get("ABBA_JARS_DIR") or APP)):
        local = folder / JARS_ARCHIVE
        if local.exists():
            return str(local)
    return JARS_URL


def probe_repo_cache(repo: Path, home: Path) -> str | None:
    """Ask jgo for PROBE and check where it went: None if jgo uses `repo`,
    otherwise why not. Run before the archive is unpacked there, so that a jgo
    looking elsewhere costs a few seconds, not a download unpacked for nothing."""
    jar = repo / PROBE_PATH
    before = jar.exists()
    argv = [console_python(), "-m", "jgo", *JGO_FLAGS, "--repo-cache", str(repo),
            "--cache-dir", str(user_dir() / "jgo-probe"), "info", "classpath", PROBE]
    result = subprocess.run(argv, env=environment(home, headless=True), capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=300,
                            stdin=subprocess.DEVNULL, **_process_flags(detached=False))
    fetched = f"{DOWNLOADING}{Path(PROBE_PATH).name}" in result.stdout + result.stderr
    if result.returncode != 0:
        return f"jgo could not resolve {PROBE} (exit {result.returncode})"
    if not jar.exists():
        return f"jgo did not put {PROBE} in {repo}"
    if before and fetched:
        return f"jgo fetched {PROBE} although it is in {repo}: it uses another cache"
    return None


def download(url: str, destination: Path, step: Callable[[int, int], None]) -> None:
    """To `<name>.part`, then renamed: an interrupted download is never taken
    for a finished one."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            step(done, total)
    part.replace(destination)


def unpack(archive: Path, repo: Path, wanted: set[str], step: Callable[[int, int], None]) -> int:
    """The archive's files that are in `wanted` and not in `repo` yet: nothing
    is overwritten, and nothing outside the manifest is written. Each file via
    `.part`, so that a file jgo sees is always whole."""
    written = 0
    with zipfile.ZipFile(archive) as zipped:
        names = [name for name in zipped.namelist() if name in wanted]
        for index, name in enumerate(names, 1):
            target = repo / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                part = target.with_name(target.name + ".part")
                with zipped.open(name) as source, part.open("wb") as out:
                    shutil.copyfileobj(source, out)
                part.replace(target)
                written += 1
            if index % 50 == 0 or index == len(names):
                step(index, len(names))
    return written


def fetch_jars(home: Path, say: Callable[[str], None], progress: Progress) -> None:
    """Most of ABBA and Fiji's jars missing (a first install): put them in
    jgo's repository cache from the archive, so that jgo only fetches what the
    archive lacks. Any problem leaves it to jgo, file by file: slower, not worse."""
    repo = repo_cache()
    try:
        missing = missing_files(repo)
        if len(missing) < ARCHIVE_THRESHOLD:
            return
        source = archive_source()
        if source is None:
            return
        if os.name == "nt" and max(len(str(repo / path)) for path in missing) > WINDOWS_MAX_PATH:
            raise RuntimeError(f"{repo} is too deep: some jars would pass Windows' path limit")
        progress.archive_step(0.0, "ABBA and Fiji: checking where jgo keeps its jars")
        problem = probe_repo_cache(repo, home)
        if problem:
            raise RuntimeError(problem)
        archive = Path(source)
        if not archive.exists():  # a URL
            say(f"Downloading ABBA and Fiji in one archive: {source}")
            archive = user_dir() / "downloads" / JARS_ARCHIVE

            def downloading(done: int, total: int) -> None:
                progress.archive_step(0.85 * done / total if total else 0.0,
                                      f"ABBA and Fiji: {done >> 20} of {total >> 20} MB "
                                      "(one archive)", total)

            download(source, archive, downloading)
        written = unpack(archive, repo, set(missing), lambda index, total: progress.archive_step(
            0.85 + 0.15 * index / total, f"ABBA and Fiji: unpacking, {index} of {total} files"))
        say(f"  {written} files unpacked into {repo}")
        if archive.parent == user_dir() / "downloads":
            archive.unlink(missing_ok=True)
    except Exception as error:  # noqa: BLE001 -- jgo fetching file by file is the way back
        say(f"The jar archive could not be used ({error}); jgo fetches the files one by one "
            "instead, which takes longer.")
    finally:
        progress.set_missing(len(missing_files(repo)))
        progress.finish("archive")


# --------------------------------------------------------------------------- #
#  Preparing
# --------------------------------------------------------------------------- #

def prepare_shared_data(say: Callable[[str], None]) -> None:
    """The atlas folders of a shared installation, and the BrainGlobe
    configuration that points to them. Install.cmd lets users write there."""
    configured = os.environ.get("ABBA_SHARED_DATA")
    if configured:  # the administrator's choice wins over an earlier one
        SHARED_DATA_RECORD.write_text(configured, encoding="utf-8")
    data = shared_data()
    config = data / "brainglobe-config"
    for folder in (data / "atlases", data / "brainglobe", config):
        folder.mkdir(parents=True, exist_ok=True)
    conf = config / "bg_config.conf"
    if not conf.exists():
        conf.write_text("[default_dirs]\n"
                        f"brainglobe_dir = {data / 'brainglobe'}\n"
                        f"interm_download_dir = {data / 'brainglobe'}\n", encoding="utf-8")
    say(f"Atlases for every user: {data}")


def prepare(environments: list[str], say: Callable[[str], None] = print,
            progress: Progress | None = None) -> Iterator[str]:
    """Download now what the first start would: Java, ABBA and Fiji's jars,
    then the Python environments asked for.

    Yields what the JVM says, line by line, and feeds every line to `progress`.
    Raises if something failed.
    """
    unknown = set(environments) - set(ENVIRONMENTS)
    if unknown:
        raise ValueError(f"unknown environment(s): {', '.join(sorted(unknown))}")
    progress = progress or Progress(environments)
    if shared():
        fetch_shared_jdk(say)
        prepare_shared_data(say)
    home = java_home(say)
    progress.finish("java")
    fetch_jars(home, say, progress)
    say("Resolving ABBA and Fiji...")
    if environments:
        say(f"Python environments go to {appose_envs_dir()}")
    argv = jgo_argv(GROOVY_MAIN, args=[str(PREPARE_SCRIPT), ",".join(environments) or "none"])
    process = subprocess.Popen(argv, cwd=work_dir(), env=environment(home, headless=True),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                               errors="replace", bufsize=1, **_process_flags(detached=False))
    assert process.stdout is not None
    # The script's own lines are shown; the rest (jgo resolving, the libraries
    # logging) only when something failed, since that is when it explains why.
    tail: deque[str] = deque(maxlen=TAIL_LINES)
    previous = None
    for raw in process.stdout:
        line = raw.rstrip("\r\n")
        progress.feed(line)
        if line.startswith(PHASE_MARK):
            continue
        if line.startswith(PREPARE_LOG):
            if line != previous:  # a download reports the same line per chunk
                yield "    " + line[len(PREPARE_LOG):]
            previous = line
        elif line.startswith(PREPARE_MARK):
            yield line[len(PREPARE_MARK):]
        elif line and not noise(line):
            tail.append(line)
    returncode = process.wait()
    if returncode != 0:
        yield from tail
        raise RuntimeError(f"preparing did not complete (exit {returncode}); the reason is above")
    progress.finish_all()
