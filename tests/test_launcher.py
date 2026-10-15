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
    assert "--cache-dir" not in argv  # per user: jgo's own caches


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


def test_progress_counts_the_jars_then_follows_the_phases(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(launcher.time, "monotonic", lambda: clock[0])
    progress = launcher.Progress(["elastix"])
    assert progress.current == "java" and progress.fraction() == 0
    progress.finish("java")
    for _ in range(launcher.EXPECTED_DOWNLOADS // 2):
        progress.feed("Downloading fiji-2.18.0.pom ---- 24.6/3.5 kB")
    assert progress.current == "jars"
    assert "961 of about 1923 files" in progress.label()
    halfway = progress.fraction()
    progress.feed("Picked up JAVA_TOOL_OPTIONS: --add-opens=...")
    assert progress.current == "elastix" and progress.fraction() > halfway
    progress.feed("ABBA_PHASE elastix start")
    before = progress.fraction()
    clock[0] += 10 * launcher.DURATIONS["elastix"]  # far longer than expected
    assert before < progress.fraction() < 1  # advances with time, never claims the end
    progress.feed("ABBA_PHASE elastix done")
    assert progress.current is None and progress.fraction() == 1 and progress.label() == "Done."


def test_more_downloads_than_expected_do_not_finish_the_jars():
    progress = launcher.Progress()
    progress.downloads = 3 * launcher.EXPECTED_DOWNLOADS
    assert progress.phase_fraction("jars") < 1


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
