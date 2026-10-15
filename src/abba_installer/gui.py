"""A window to start ABBA, for someone who should not need a terminal.

    Start.cmd / start.sh          (double-click; installs uv if missing)
    the ABBA shortcut             (written by Start.cmd and Install.cmd)

It does what the command line does - `launcher.start_fiji`, `launcher.prepare` -
and shows what happens: the first start downloads Java, ABBA and Fiji, which
takes minutes and must not look like a hang. Fiji's output is read from its log
file rather than a pipe, so that closing this window leaves Fiji running.

Tk is only touched from its own thread: the work runs on threads that put lines
on a queue, which the window drains every 100 ms.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__, launcher, settings
from .launcher import ENVIRONMENTS

TITLE = "ABBA"
SUBTITLE = "Aligning Big Brains & Atlases"
GREY = "#666666"
MONO = ("Consolas" if os.name == "nt" else "Menlo", 9)
POLL_MS = 100
#: Lines kept in the log pane; Fiji running for days must not grow it forever.
LOG_LINES = 5000
ASSETS = Path(__file__).resolve().parent / "assets"
#: The header logo, drawn at each display scale (Tk cannot resize smoothly).
LOGO_SCALES = (100, 125, 150, 175, 200, 250, 300)
ICON_SIZES = (16, 32, 48, 256)
DOCS = "https://abba-documentation.readthedocs.io"
FORUM = "https://forum.image.sc/tag/abba"


def load_image(name: str) -> tk.PhotoImage | None:
    try:
        return tk.PhotoImage(file=str(ASSETS / name))
    except tk.TclError:
        return None  # a missing logo is not worth refusing to start


def logo_scale(root: tk.Tk) -> int:
    """The prepared logo scale closest to the display's, 96 dpi being 100 %."""
    percent = root.winfo_fpixels("1i") / 96 * 100
    return min(LOGO_SCALES, key=lambda s: abs(s - percent))


def sharp_on_windows() -> None:
    """Draw at the display's real resolution instead of letting Windows stretch
    a 96 dpi window, which blurs text and logo on any scaled display."""
    if os.name != "nt":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def own_taskbar_entry() -> None:
    """Group under ABBA's name and icon on the Windows taskbar, not Python's."""
    if os.name != "nt":
        return
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BIOP.ABBA.Launcher")
    except (AttributeError, OSError):
        pass


def open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 -- a folder of ours
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        #: From the worker threads: lines for the log pane, and calls to make on
        #: Tk's thread when their work is done.
        self.lines: queue.Queue[str | Callable[[], None]] = queue.Queue()
        self.fiji: subprocess.Popen | None = None
        self.fiji_log = None  # the log file, read as Fiji writes it
        self.fiji_output: launcher.FijiOutput | None = None
        self.progress: launcher.Progress | None = None
        self.preparing = False

        saved = settings.load()
        self.settings = saved
        self.memory = tk.StringVar(value=saved.get("memory", ""))
        chosen = set(saved.get("prepare", list(ENVIRONMENTS)))
        self.chosen = {name: tk.BooleanVar(value=name in chosen) for name in ENVIRONMENTS}
        self.status = tk.StringVar()

        root.title(f"{TITLE} {launcher.ABBA_VERSION}")
        self.icons = [image for size in ICON_SIZES if (image := load_image(f"icon-{size}.png"))]
        if self.icons:
            root.iconphoto(True, *self.icons)
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.idle()
        root.after(POLL_MS, self.poll)

    # -- layout ------------------------------------------------------------ #

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        self.logo = load_image(f"logo-{logo_scale(self.root)}.png")
        if self.logo is not None:
            ttk.Label(header, image=self.logo).pack(side="left", padx=(0, 12))
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="x")
        ttk.Label(titles, text=f"{TITLE} - {SUBTITLE}",
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(titles, foreground=GREY, text=(
            f"ABBA {launcher.ABBA_VERSION} · Fiji {launcher.FIJI_VERSION} · "
            f"Java {launcher.JAVA_VERSION} · launcher {__version__}"
            + (" · installed for every user" if launcher.shared() else ""))).pack(anchor="w")

        start = ttk.Frame(outer)
        start.pack(fill="x", pady=(14, 0))
        self.start_button = ttk.Button(start, text="Start ABBA", command=self.start)
        self.start_button.pack(side="left", ipadx=12, ipady=4)
        ttk.Label(start, text="Java memory").pack(side="left", padx=(18, 4))
        ttk.Entry(start, textvariable=self.memory, width=7).pack(side="left")
        ttk.Label(start, foreground=GREY,
                  text="e.g. 16G; empty: chosen from this computer's memory").pack(
            side="left", padx=(6, 0))

        frame = ttk.LabelFrame(outer, text="Prepare (optional)", padding=10)
        frame.pack(fill="x", pady=(14, 0))
        if launcher.shared():
            ttk.Label(frame, foreground=GREY, text=(
                "Prepared for every user of this computer when ABBA was installed.")).pack(
                anchor="w")
            self.prepare_button = None
        else:
            ttk.Label(frame, foreground=GREY, wraplength=640, justify="left", text=(
                "ABBA downloads these the first time it uses them. Download them now, "
                "for instance before a workshop or before going offline. Java, ABBA "
                "and Fiji are downloaded too.")).pack(anchor="w")
            checks = ttk.Frame(frame)
            checks.pack(fill="x", pady=(6, 0))
            for name, label in ENVIRONMENTS.items():
                ttk.Checkbutton(checks, text=label, variable=self.chosen[name]).pack(
                    side="left", padx=(0, 14))
            self.prepare_button = ttk.Button(checks, text="Prepare", command=self.prepare)
            self.prepare_button.pack(side="right")

        progress = ttk.Frame(outer)
        progress.pack(fill="x", pady=(14, 0))
        self.bar = ttk.Progressbar(progress, mode="determinate", maximum=1000)
        self.bar.pack(fill="x")
        self.progress_text = tk.StringVar()
        ttk.Label(progress, textvariable=self.progress_text, foreground=GREY).pack(anchor="w")

        self.log = ScrolledText(outer, height=16, width=100, font=MONO, wrap="none",
                                state="disabled")
        self.log.pack(fill="both", expand=True, pady=(8, 6))

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status, foreground=GREY).pack(side="left")
        for text, action in (("Fiji's log", lambda: open_path(launcher.fiji_log().parent)),
                             ("Forum", lambda: webbrowser.open(FORUM)),
                             ("Documentation", lambda: webbrowser.open(DOCS))):
            ttk.Button(bottom, text=text, command=action).pack(side="right", padx=(6, 0))

    # -- the log pane ------------------------------------------------------ #

    def write(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        excess = int(self.log.index("end-1c").split(".")[0]) - LOG_LINES
        if excess > 0:
            self.log.delete("1.0", f"{excess + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll(self) -> None:
        while True:
            try:
                item = self.lines.get_nowait()
            except queue.Empty:
                break
            item() if callable(item) else self.write(item)
        if self.fiji_log is not None and self.fiji_output is not None:
            for line in self.fiji_log.readlines():
                shown = self.fiji_output(line.rstrip("\r\n"))
                if shown is not None:
                    self.write(shown)
        if self.fiji is not None and self.fiji.poll() is not None:
            code = self.fiji.returncode
            self.fiji = None
            for line in self.fiji_output.unexplained() if self.fiji_output else []:
                self.write(line)
            self.idle(f"Fiji closed (exit {code})." if code else "Fiji closed.")
        if self.progress is not None:
            self.bar["value"] = 1000 * self.progress.fraction()
            self.progress_text.set(self.progress.label() if self.progress.current else "")
        self.root.after(POLL_MS, self.poll)

    def idle(self, message: str = "Ready.") -> None:
        self.status.set(message)
        busy = self.fiji is not None or self.preparing
        self.start_button.configure(state="disabled" if busy else "normal")
        if self.prepare_button is not None:
            self.prepare_button.configure(state="disabled" if busy else "normal")

    def remember(self) -> None:
        self.settings.update(memory=self.memory.get().strip(),
                             prepare=[name for name, var in self.chosen.items() if var.get()])
        settings.save(self.settings)

    # -- actions ----------------------------------------------------------- #

    def start(self) -> None:
        self.remember()
        options = settings.options(self.settings)
        self.start_button.configure(state="disabled")
        self.status.set("Starting Fiji. The first start downloads Java, ABBA and Fiji: "
                        "allow up to 15 minutes.")
        self.progress = launcher.Progress()
        self.fiji_output = launcher.FijiOutput(self.progress)

        def work() -> None:
            try:
                process = launcher.start_fiji(options, say=self.lines.put)
            except Exception as error:  # noqa: BLE001 -- shown, not lost on a thread
                message = f"Could not start Fiji: {error}"
                self.lines.put(lambda: self.idle(message))
                return
            self.lines.put(lambda: self.started(process))

        threading.Thread(target=work, name="start", daemon=True).start()

    def started(self, process: subprocess.Popen) -> None:
        self.fiji = process
        if self.progress is not None:
            self.progress.finish("java")
        if self.fiji_log is not None:
            self.fiji_log.close()
        self.fiji_log = launcher.fiji_log().open(encoding="utf-8", errors="replace")
        self.idle("Fiji is running. Closing this window leaves it open.")

    def prepare(self) -> None:
        chosen = [name for name, var in self.chosen.items() if var.get()]
        self.remember()
        self.preparing = True
        self.idle("Preparing. The first time, this takes from a few minutes to half an hour.")
        progress = self.progress = launcher.Progress(chosen)

        def work() -> None:
            try:
                for line in launcher.prepare(chosen, say=self.lines.put, progress=progress):
                    self.lines.put(line)
                message = "Prepared."
            except Exception as error:  # noqa: BLE001 -- shown, not lost on a thread
                self.lines.put(str(error))
                message = "Preparing failed; the reason is in the log above."
            self.lines.put(lambda: self.prepared(message))

        threading.Thread(target=work, name="prepare", daemon=True).start()

    def prepared(self, message: str) -> None:
        self.preparing = False
        self.idle(message)

    def on_close(self) -> None:
        if self.preparing and not messagebox.askyesno(
                TITLE, "Preparing is not finished. Close anyway? It resumes next time."):
            return
        self.remember()
        self.root.destroy()


def main() -> None:
    sharp_on_windows()  # both before the first window exists
    own_taskbar_entry()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
