"""The launcher's command lines, layouts and output handling, without starting a JVM."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from abba_installer import launcher, settings


@pytest.fixture
def per_user(tmp_path, monkeypatch):
    """A per-user layout, with the user's folder in a temporary directory."""
    monkeypatch.setattr(launcher, "SHARED", tmp_path / "app" / "java")
    monkeypatch.setattr(launcher, "SHARED_DATA_RECORD", tmp_path / "app" / "java" / "shared-data.txt")
    monkeypatch.setattr(launcher, "user_dir", lambda: tmp_path / "user")
    monkeypatch.delenv("ABBA_SHARED_DATA", raising=False)
    monkeypatch.delenv("ABBA_JARS_DIR", raising=False)
    monkeypatch.setenv("M2_REPO", str(tmp_path / "m2"))
    monkeypatch.setenv("ABBA_JARS_URL", "none")  # tests that want the archive say so
    return tmp_path


@pytest.fixture
def shared(per_user):
    launcher.SHARED.mkdir(parents=True)
    return per_user


def test_abba_comes_first_and_extras_after(per_user):
    argv = launcher.jgo_argv(launcher.FIJI_MAIN, extra_dependencies=["sc.fiji:fiji-llm:0.1.0"])
    endpoint = argv[-1]
    assert endpoint.split("+") == [*launcher.ENDPOINT, "sc.fiji:fiji-llm:0.1.0"]
    assert endpoint.startswith("ch.epfl.biop:ImageToAtlasRegister:")


def test_jvm_options_and_script_arguments(per_user):
    argv = launcher.jgo_argv(launcher.GROOVY_MAIN, max_heap="8G", args=["script.groovy", "none"])
    assert argv[argv.index("--max-heap") + 1] == "8G"
    assert argv[argv.index("--main-class") + 1] == launcher.GROOVY_MAIN
    assert argv[-4:] == ["--", "--", "script.groovy", "none"]
    assert "--cache-dir" not in argv  # per user: jgo's own environment cache
    # but always the repository cache, where the jar archive is unpacked
    assert argv[argv.index("--repo-cache") + 1] == str(per_user / "m2")


def test_logback_configuration_goes_in_a_jar(per_user):
    argv = launcher.jgo_argv(launcher.FIJI_MAIN)
    jar = Path(argv[argv.index("--add-classpath") + 1])
    assert jar.suffix == ".jar"  # jgo adds `<entry>/*`: a folder would add nothing
    with zipfile.ZipFile(jar) as archive:
        assert archive.read("logback.xml") == launcher.LOGBACK_XML.read_bytes()
    written = jar.stat().st_mtime_ns
    launcher.logback_jar()
    assert jar.stat().st_mtime_ns == written  # unchanged configuration: not rewritten


def test_shared_layout_uses_the_installation_caches(shared):
    argv = launcher.jgo_argv(launcher.FIJI_MAIN)
    assert argv[argv.index("--cache-dir") + 1] == str(launcher.SHARED / "jgo")
    assert argv[argv.index("--repo-cache") + 1] == str(launcher.SHARED / "m2")
    env = launcher.environment(Path("jdk"), headless=False)
    assert env["APPOSE_ENVS_DIR"] == str(launcher.SHARED_APPOSE)
    assert "-Djava.awt.headless=true" not in env["JAVA_TOOL_OPTIONS"]


def test_shared_atlas_folder_is_recorded_for_the_users(shared, monkeypatch):
    data = shared / "atlases-disk"
    monkeypatch.setenv("ABBA_SHARED_DATA", str(data))
    launcher.prepare_shared_data(lambda _: None)
    assert (data / "brainglobe-config" / "bg_config.conf").read_text().count(str(data)) == 2
    monkeypatch.delenv("ABBA_SHARED_DATA")  # a user's session does not have it
    assert launcher.shared_data() == data
    marker = launcher.work_dir() / "plugins" / "BIOP" / "ABBA_Atlas_folder.txt"
    assert marker.read_text() == str(data / "atlases")


def test_per_user_atlas_folder_is_abbas_default(per_user):
    marker = per_user / "user" / "work" / "plugins" / "BIOP" / "ABBA_Atlas_folder.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("left by a shared installation")
    launcher.work_dir()
    assert not marker.exists()


class FakeProcess:
    def __init__(self, stdout: str, returncode: int) -> None:
        self.stdout = io.StringIO(stdout)
        self.returncode = returncode

    def wait(self) -> int:
        return self.returncode


def run_prepare(monkeypatch, stdout: str, returncode: int = 0) -> list[str]:
    monkeypatch.setattr(launcher, "java_home", lambda say=None: Path("jdk"))
    monkeypatch.setattr(launcher.subprocess, "Popen",
                        lambda *args, **kwargs: FakeProcess(stdout, returncode))
    return list(launcher.prepare(["elastix"], say=lambda _: None))


JGO_NOISE = "WARNING  Invalid JDK version specification '[9,' in\n"


def test_prepare_shows_its_own_lines_only(per_user, monkeypatch):
    lines = run_prepare(monkeypatch, JGO_NOISE
                        + "Picked up JAVA_TOOL_OPTIONS: -Dx\n"
                        + "ABBA_PREPARE Elastix: building...\n"
                        + "ABBA_PREPARE_LOG Downloading pixi\n" * 3
                        + "ABBA_PREPARE Elastix: ready (3 s)\n")
    assert lines == ["Elastix: building...", "    Downloading pixi", "Elastix: ready (3 s)"]


def test_prepare_failure_shows_the_rest(per_user, monkeypatch):
    with pytest.raises(RuntimeError, match="exit 1"):
        run_prepare(monkeypatch, JGO_NOISE + "ABBA_PREPARE Elastix: FAILED - boom\n", 1)


def test_prepare_refuses_unknown_environments(per_user):
    with pytest.raises(ValueError, match="cellpose"):
        list(launcher.prepare(["cellpose"]))


def test_settings_to_options():
    options = settings.options({"memory": " 16G ", "extra_dependencies": ["a:b:1"],
                                "extra_jars": ["x.jar"]})
    assert options.max_heap == "16G"
    assert options.extra_dependencies == ["a:b:1"]
    assert options.extra_jars == [Path("x.jar")]
    assert settings.options({}).max_heap is None


def test_versions_agree():
    """The launcher's version is the ABBA it runs (plus .postN for a fix of the
    launcher alone), in __init__ and pyproject alike."""
    from abba_installer import __version__

    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject
    assert __version__.split(".post")[0] == launcher.ABBA_VERSION


def test_progress_follows_the_phases(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(launcher.time, "monotonic", lambda: clock[0])
    progress = launcher.Progress(["elastix"])
    assert progress.current == "java" and progress.fraction() == 0
    progress.finish("java")
    progress.archive_step(0.5, "ABBA and Fiji: 250 of 500 MB (one archive)", 500 << 20)
    assert progress.current == "archive" and "250 of 500 MB" in progress.label()
    halfway_archive = progress.fraction()
    progress.finish("archive")
    progress.set_missing(10)  # what the archive did not bring
    for _ in range(5):
        progress.feed("Downloading natives-linux-1.0.jar ---- 24.6/3.5 kB")
    assert progress.current == "jars" and "5 of about 10 files" in progress.label()
    assert progress.fraction() > halfway_archive
    halfway = progress.fraction()
    progress.feed("Picked up JAVA_TOOL_OPTIONS: --add-opens=...")
    assert progress.current == "elastix" and progress.fraction() > halfway
    progress.feed("ABBA_PHASE elastix start")
    before = progress.fraction()
    clock[0] += 10 * launcher.DURATIONS["elastix"]  # far longer than expected
    assert before < progress.fraction() < 1  # advances with time, never claims the end
    progress.feed("ABBA_PHASE elastix done")
    assert progress.current is None and progress.fraction() == 1 and progress.label() == "Done."


def test_without_the_archive_the_jars_are_counted_against_the_manifest():
    progress = launcher.Progress()
    assert progress.missing == launcher.expected_downloads() == len(launcher.manifest())
    progress.downloads = 3 * progress.missing  # more than expected
    assert progress.phase_fraction("jars") < 1


# -- the jar archive ----------------------------------------------------------

FILES = ("a/b/1.0/b-1.0.jar", "a/b/1.0/b-1.0.pom", launcher.PROBE_PATH)


@pytest.fixture
def archive(per_user, monkeypatch):
    """A three-file manifest, its archive next to the installation, and a probe
    that finds jgo using the repository cache."""
    monkeypatch.setattr(launcher, "manifest", lambda: FILES)
    monkeypatch.setattr(launcher, "ARCHIVE_THRESHOLD", 2)
    path = per_user / "dl" / launcher.JARS_ARCHIVE
    path.parent.mkdir()
    with zipfile.ZipFile(path, "w") as zipped:
        for name in (*FILES, "../outside.jar", "not/in/manifest.jar"):
            zipped.writestr(name, f"archive {name}")
    monkeypatch.setenv("ABBA_JARS_URL", str(path))
    monkeypatch.setattr(launcher, "probe_repo_cache", lambda repo, home: None)
    return per_user / "m2"


def fetch(progress=None) -> list[str]:
    said = []
    launcher.fetch_jars(Path("jdk"), said.append, progress or launcher.Progress())
    return said


def test_the_archive_adds_only_missing_manifest_files(archive):
    (archive / "a/b/1.0").mkdir(parents=True)
    (archive / "a/b/1.0/b-1.0.pom").write_text("already there")
    progress = launcher.Progress()
    fetch(progress)
    assert (archive / "a/b/1.0/b-1.0.jar").read_text() == "archive a/b/1.0/b-1.0.jar"
    assert (archive / "a/b/1.0/b-1.0.pom").read_text() == "already there"  # never overwritten
    assert not (archive / "not/in/manifest.jar").exists()
    assert not (archive.parent / "outside.jar").exists()
    assert not list(archive.rglob("*.part"))
    assert progress.missing == 0 and "archive" in progress.done


def test_little_missing_no_archive(archive, monkeypatch):
    monkeypatch.setattr(launcher, "ARCHIVE_THRESHOLD", 5)
    fetch()
    assert not archive.exists()


def test_a_probe_finding_another_cache_leaves_everything_to_jgo(archive, monkeypatch):
    monkeypatch.setattr(launcher, "probe_repo_cache",
                        lambda repo, home: "jgo fetched it although it is there")
    progress = launcher.Progress()
    said = fetch(progress)
    assert not archive.exists()  # nothing unpacked anywhere
    assert "jgo fetches the files one by one" in said[-1]
    assert progress.missing == len(FILES) and "archive" in progress.done


@pytest.mark.skipif(launcher.os.name != "nt", reason="Windows' path limit")
def test_a_too_deep_repository_cache_is_refused(archive, monkeypatch):
    monkeypatch.setenv("M2_REPO", str(archive / ("x" * 250)))
    said = fetch()
    assert "too deep" in said[-1]


def probe_with(monkeypatch, repo: Path, before: bool, writes: bool, output: str) -> str | None:
    jar = repo / launcher.PROBE_PATH
    if before:
        jar.parent.mkdir(parents=True)
        jar.write_text("cached")

    def run(argv, **kwargs):
        assert argv[argv.index("--repo-cache") + 1] == str(repo)
        if writes:
            jar.parent.mkdir(parents=True, exist_ok=True)
            jar.write_text("fetched")
        return launcher.subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(launcher.subprocess, "run", run)
    return launcher.probe_repo_cache(repo, Path("jdk"))


FETCHED = "Downloading aopalliance-1.0.jar ---- 4.5/4.5 kB\n"


def test_probe_jgo_fetching_into_the_cache(per_user, monkeypatch):
    assert probe_with(monkeypatch, per_user / "m2", False, True, FETCHED) is None


def test_probe_jgo_finding_it_in_the_cache(per_user, monkeypatch):
    assert probe_with(monkeypatch, per_user / "m2", True, False, "") is None


def test_probe_jgo_putting_it_elsewhere(per_user, monkeypatch):
    assert "did not put" in probe_with(monkeypatch, per_user / "m2", False, False, FETCHED)


def test_probe_jgo_fetching_what_the_cache_has(per_user, monkeypatch):
    assert "another cache" in probe_with(monkeypatch, per_user / "m2", True, False, FETCHED)


def test_fiji_output_holds_jgo_back_until_the_jvm_starts():
    output = launcher.FijiOutput(launcher.Progress())
    assert output("Downloading fiji-2.18.0.pom ----") is None
    assert output("                         kB   MB/s") is None
    assert output.unexplained() == ["Downloading fiji-2.18.0.pom ----", "                         kB   MB/s"]
    assert output("Picked up JAVA_TOOL_OPTIONS: --add-opens") is None
    assert output("[ERROR] Cannot create plugin: org.scijava.plugins.scripting.javascript."
                  "JavaScriptScriptLanguage") is None  # on every start, harmless
    assert output("WARN  bdv - something") == "WARN  bdv - something"
    assert output.unexplained() == []


def test_install_is_remembered_per_abba_version(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")
    assert settings.installed(settings.load()) is None  # never installed: the window offers it
    settings.record_installed(["elastix"])
    settings.record_installed(["deepslice"])  # a second install adds to the first
    assert settings.installed(settings.load()) == ["deepslice", "elastix"]
    other = {"installed": {"0.24.1": ["deepslice"]}}
    assert settings.installed(other) is None  # another ABBA version: not installed


def test_intel_macs_get_brainglobe_only(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher.platform, "machine", lambda: "x86_64")
    assert launcher.supported_environments() == ["brainglobe"]
    monkeypatch.setattr(launcher.platform, "machine", lambda: "arm64")
    assert launcher.supported_environments() == list(launcher.ENVIRONMENTS)


def test_install_size_counts_java_and_jars():
    assert launcher.install_size_gb([]) == pytest.approx(0.8)
    assert round(launcher.install_size_gb(list(launcher.ENVIRONMENTS))) == 6
