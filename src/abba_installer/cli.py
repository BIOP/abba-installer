"""The command line: what the window does, for a terminal or a script.

    abba start [--memory 8G] [--with GROUP:ARTIFACT:VERSION]... [--add-jar JAR]...
    abba prepare [--all | --deepslice --elastix --brainglobe]
    abba info

`start` leaves Fiji running when the terminal closes; until then it shows
Fiji's output. Its options default to what the window remembers.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from . import __version__, launcher, settings
from .launcher import ENVIRONMENTS


class Reporter:
    """Prints the progress when the phase changes, every 5 %, and every 30 s it
    moved at all, from a thread of its own: phases without a count advance with
    time, between two lines of output."""

    def __init__(self, progress: launcher.Progress) -> None:
        self.progress = progress
        self.stopped = threading.Event()
        self.shown = (None, -5, 0.0)
        threading.Thread(target=self._run, name="progress", daemon=True).start()

    def _run(self) -> None:
        while not self.stopped.wait(1.0):
            phase, percent = self.progress.current, int(100 * self.progress.fraction())
            if phase is None:
                return
            last_phase, last_percent, last_time = self.shown
            now = time.monotonic()
            if (phase != last_phase or percent >= last_percent + 5
                    or (percent > last_percent and now - last_time >= 30)):
                print(f"[{percent:3d}%] {self.progress.label()}", flush=True)
                self.shown = (phase, percent, now)

    def stop(self) -> None:
        self.stopped.set()


def start(args: argparse.Namespace) -> int:
    options = settings.options(settings.load())
    if args.memory:
        options.max_heap = args.memory
    options.extra_dependencies += args.dependencies
    options.extra_jars += [Path(jar) for jar in args.jars]
    progress = launcher.Progress()
    output = launcher.FijiOutput(progress)
    reporter = Reporter(progress)
    process = launcher.start_fiji(options)
    progress.finish("java")
    log = launcher.fiji_log()
    print(f"Fiji is starting (ABBA {launcher.ABBA_VERSION}); its output is also in {log}")
    print("The first start downloads ABBA and Fiji: allow up to 15 minutes. "
          "Closing this terminal leaves Fiji running.\n")
    try:
        with log.open(encoding="utf-8", errors="replace") as lines:
            while True:
                line = lines.readline()
                if line:
                    shown = output(line.rstrip("\r\n"))
                    if shown is not None:
                        print(shown, flush=True)
                elif process.poll() is not None:
                    break
                else:
                    time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nNo longer following Fiji's output; Fiji goes on.")
        return 0
    finally:
        reporter.stop()
    for line in output.unexplained():
        print(line)
    print(f"\nFiji closed (exit {process.returncode}).")
    return process.returncode or 0


def prepare(args: argparse.Namespace) -> int:
    chosen = list(ENVIRONMENTS) if args.all else [name for name in ENVIRONMENTS
                                                    if getattr(args, name)]
    progress = launcher.Progress(chosen)
    reporter = Reporter(progress)
    try:
        for line in launcher.prepare(chosen, progress=progress):
            print(line, flush=True)
    except (RuntimeError, ValueError) as error:
        print(f"\n{error}", file=sys.stderr)
        return 1
    finally:
        reporter.stop()
    return 0


def info(_: argparse.Namespace) -> int:
    print(f"abba-installer {__version__}")
    print(f"ABBA           {launcher.ABBA_VERSION}")
    print(f"Fiji           {launcher.FIJI_VERSION}")
    print(f"Java           {launcher.JAVA_VERSION} ({launcher.JAVA_VENDOR})")
    print(f"Installation   {launcher.APP}"
          + (" (shared: every user)" if launcher.shared() else " (this user)"))
    print(f"Python envs    {launcher.appose_envs_dir()}")
    print(f"Fiji log       {launcher.fiji_log()}")
    print(f"Settings       {settings.settings_path()}")
    if launcher.shared():
        print(f"Atlases        {launcher.shared_data()}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="abba", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__} "
                        f"(ABBA {launcher.ABBA_VERSION}, Fiji {launcher.FIJI_VERSION})")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("start", help="start Fiji with ABBA")
    run.add_argument("--memory", help="Java's maximum heap, e.g. 8G (default: jgo chooses)")
    run.add_argument("--with", dest="dependencies", action="append", default=[],
                     metavar="GROUP:ARTIFACT:VERSION", help="an extra Maven artifact (repeatable)")
    run.add_argument("--add-jar", dest="jars", action="append", default=[], metavar="JAR",
                     help="an extra jar on the class path (repeatable)")
    run.set_defaults(handler=start)

    ready = commands.add_parser("prepare", help="download now what ABBA would download on first use")
    ready.add_argument("--all", action="store_true", help="every Python environment")
    for name, label in ENVIRONMENTS.items():
        ready.add_argument(f"--{name}", action="store_true", help=label)
    ready.set_defaults(handler=prepare)

    commands.add_parser("info", help="versions and folders").set_defaults(handler=info)

    args = parser.parse_args(argv)
    sys.exit(args.handler(args))


if __name__ == "__main__":
    main()
