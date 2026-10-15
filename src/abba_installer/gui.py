"""A window to start ABBA, for someone who should not need a terminal.

    Install for me.cmd / install-for-me.sh    (installs uv if missing, then opens it)
    the ABBA shortcut                         (written by both installers)
    Install for all users.cmd                 (runs it with --install-all)

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
LINK = "#1a5fb4"
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
    """The window. Two states for one user: not installed yet (Install
    everything first, Start ABBA below it), and installed (Start ABBA first).
    In a shared installation users only start ABBA; `install_all` is the mode
    the all-users installer runs it in: install everything, nothing else."""

    def __init__(self, root: tk.Tk, install_all: bool = False) -> None:
        self.root = root
        self.install_all = install_all
        #: The exit code of the window: the all-users installer reads it.
        self.exit_code = 0
        #: From the worker threads: lines for the log pane, and calls to make on
        #: Tk's thread when their work is done.
        self.lines: queue.Queue[str | Callable[[], None]] = queue.Queue()
        self.fiji: subprocess.Popen | None = None
        self.fiji_log = None  # the log file, read as Fiji writes it
        self.fiji_output: launcher.FijiOutput | None = None
        self.progress: launcher.Progress | None = None
        self.installing = False
        self.choosing = False  # Choose… opened: the checkboxes are shown

        saved = settings.load()
        self.settings = saved
        self.supported = launcher.supported_environments()
        self.memory = tk.StringVar(value=saved.get("memory", ""))
        chosen = set(saved.get("prepare", self.supported))
        self.chosen = {name: tk.BooleanVar(value=name in chosen and name in self.supported)
                       for name in ENVIRONMENTS}
        self.status = tk.StringVar()
        self.summary = tk.StringVar()

        root.title(f"{TITLE} {launcher.ABBA_VERSION}")
        self.icons = [image for size in ICON_SIZES if (image := load_image(f"icon-{size}.png"))]
        if self.icons:
            root.iconphoto(True, *self.icons)
        style = ttk.Style(root)
        style.configure("Primary.TButton", font=("TkDefaultFont", 10, "bold"))
        self._build()
        for var in self.chosen.values():
            var.trace_add("write", lambda *_: self.describe())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.arrange()
        self.idle()
        root.after(POLL_MS, self.poll)
        if install_all:
            root.after(500, self.install)

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

        # Start ABBA
        self.start_row = ttk.Frame(outer)
        self.start_button = ttk.Button(self.start_row, text="Start ABBA", command=self.start)
        self.start_button.pack(side="left", ipadx=12, ipady=4)
        ttk.Label(self.start_row, text="Java memory").pack(side="left", padx=(18, 4))
        ttk.Entry(self.start_row, textvariable=self.memory, width=7).pack(side="left")
        ttk.Label(self.start_row, foreground=GREY,
                  text="e.g. 16G; empty: chosen from this computer's memory").pack(
            side="left", padx=(6, 0))

        # Install
        self.install_frame = ttk.Frame(outer)
        row = ttk.Frame(self.install_frame)
        row.pack(fill="x")
        self.install_button = ttk.Button(row, text="Install everything", command=self.install)
        self.choose_link = ttk.Label(row, text="Choose…", foreground=LINK, cursor="hand2")
        self.choose_link.bind("<Button-1>", lambda _: self.toggle_choice())
        self.summary_label = ttk.Label(row, textvariable=self.summary, wraplength=520,
                                       justify="left")
        self.summary_label.pack(side="left", padx=(14, 0))
        self.checks = ttk.Frame(self.install_frame)
        for name, label in ENVIRONMENTS.items():
            supported = name in self.supported
            ttk.Checkbutton(self.checks, variable=self.chosen[name],
                            state="normal" if supported else "disabled",
                            text=label if supported else f"{label} - not on Intel Macs").pack(
                side="left", padx=(0, 14))

        # Progress, log, links
        self.progress_area = ttk.Frame(outer)
        self.bar = ttk.Progressbar(self.progress_area, mode="determinate", maximum=1000)
        self.bar.pack(fill="x")
        self.progress_text = tk.StringVar()
        ttk.Label(self.progress_area, textvariable=self.progress_text,
                  foreground=GREY).pack(anchor="w")

        self.log = ScrolledText(outer, height=14, width=100, font=MONO, wrap="none",
                                state="disabled")

        self.bottom = ttk.Frame(outer)
        ttk.Label(self.bottom, textvariable=self.status, foreground=GREY).pack(side="left")
        for text, action in (("Fiji's log", lambda: open_path(launcher.fiji_log().parent)),
                             ("Forum", lambda: webbrowser.open(FORUM)),
                             ("Documentation", lambda: webbrowser.open(DOCS))):
            ttk.Button(self.bottom, text=text, command=action).pack(side="right", padx=(6, 0))

    def shared_user(self) -> bool:
        """A user of an installation for every user: nothing to install."""
        return launcher.shared() and not self.install_all

    def installed(self) -> list[str] | None:
        """What is installed for this ABBA version; None: Install never ran."""
        if self.shared_user():
            return list(self.supported)  # the administrator installed everything
        return settings.installed(settings.load())

    def arrange(self) -> None:
        """Lay the window out for its state: what is to do first comes first."""
        for widget in (self.start_row, self.install_frame, self.progress_area, self.log,
                       self.bottom):
            widget.pack_forget()
        if self.install_all:
            order = [self.install_frame]
        elif self.installed() is None:
            order = [self.install_frame, self.start_row]
        else:
            order = [self.start_row, self.install_frame]
        for widget in order:
            widget.pack(fill="x", pady=(14, 0))
        self.progress_area.pack(fill="x", pady=(14, 0))
        self.log.pack(fill="both", expand=True, pady=(8, 6))
        self.bottom.pack(fill="x")
        self.arrange_install_row()

    def arrange_install_row(self) -> None:
        """The Install button only when there is something to install: hidden
        once installed, until Choose… asks to add or repair something. The
        action to take first is in bold."""
        self.install_button.pack_forget()
        self.choose_link.pack_forget()
        self.checks.pack_forget()
        done = self.installed()
        if not (self.shared_user() or self.install_all):
            if done is None or self.choosing:
                self.install_button.pack(side="left", ipadx=12, ipady=4,
                                         before=self.summary_label)
            self.choose_link.configure(text="Choose…" if done is None or self.choosing
                                       else "Add or repair…")
            self.choose_link.pack(side="right")
        if self.choosing:
            self.checks.pack(fill="x", pady=(8, 0))
        first = self.install_button if done is None else self.start_button
        for button in (self.install_button, self.start_button):
            button.configure(style="Primary.TButton" if button is first else "TButton")
        self.describe()

    def toggle_choice(self) -> None:
        self.choosing = not self.choosing
        self.arrange_install_row()

    def selection(self) -> list[str]:
        if self.install_all:
            return list(self.supported)  # users cannot add anything to a shared folder later
        return [name for name, var in self.chosen.items() if var.get()]

    def describe(self) -> None:
        """The line next to the Install button, and the button's own label."""
        chosen = self.selection()
        names = ["Java", "ABBA", "Fiji"] + [ENVIRONMENTS[name].split()[0] for name in chosen]
        what = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
        size = f"about {launcher.install_size_gb(chosen):.0f} GB"
        done = self.installed()
        if self.shared_user():
            self.summary.set("✓ Installed for every user of this computer.")
        elif self.install_all:
            self.summary.set(f"Installing for every user of this computer: {what}, {size}. "
                             "This takes 10 to 20 minutes, depending on the connection.")
        elif done is not None and not self.choosing:
            tools = [ENVIRONMENTS[name].split()[0] for name in done]
            self.summary.set(f"✓ Installed: ABBA {launcher.ABBA_VERSION}"
                             + (f" with {', '.join(tools)}" if tools else "") + ".")
        elif done is not None:
            self.summary.set(f"{what}: what is already there is skipped, "
                             "what is missing is downloaded.")
        else:
            self.summary.set(f"{what}: {size}, 10 to 20 minutes depending on the connection. "
                             "Or start ABBA right away: what it needs is downloaded when "
                             "first used.")
        everything = set(chosen) == set(self.supported)
        self.install_button.configure(text="Install everything" if everything
                                      else "Install selected")

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
        state = "disabled" if self.fiji is not None or self.installing else "normal"
        self.start_button.configure(state=state)
        self.install_button.configure(state=state)

    def remember(self) -> None:
        if self.install_all:
            return  # the administrator's own settings are not the users'
        self.settings.update(memory=self.memory.get().strip(),
                             prepare=[name for name, var in self.chosen.items() if var.get()])
        settings.save(self.settings)

    # -- actions ----------------------------------------------------------- #

    def start(self) -> None:
        self.remember()
        options = settings.options(self.settings)
        self.start_button.configure(state="disabled")
        self.status.set("Starting Fiji. The first start downloads Java, ABBA and Fiji: "
                        "allow a few minutes.")
        progress = self.progress = launcher.Progress()
        self.fiji_output = launcher.FijiOutput(self.progress)

        def work() -> None:
            try:
                process = launcher.start_fiji(options, say=self.lines.put, progress=progress)
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

    def install(self) -> None:
        chosen = self.selection()
        self.remember()
        self.installing = True
        self.idle("Installing. What is already downloaded is skipped.")
        progress = self.progress = launcher.Progress(chosen)

        def work() -> None:
            try:
                for line in launcher.prepare(chosen, say=self.lines.put, progress=progress):
                    self.lines.put(line)
            except Exception as error:  # noqa: BLE001 -- shown, not lost on a thread
                self.lines.put(str(error))
                self.lines.put(lambda: self.installed_now(None))
                return
            self.lines.put(lambda: self.installed_now(chosen))

        threading.Thread(target=work, name="install", daemon=True).start()

    def installed_now(self, chosen: list[str] | None) -> None:
        self.installing = False
        if chosen is None:
            self.exit_code = 1
            self.idle("The installation failed; the reason is in the log above.")
            return
        if self.install_all:
            self.idle("Installed. This window closes; the installation finishes in the console.")
            self.root.after(3000, self.root.destroy)
            return
        settings.record_installed(chosen)
        self.choosing = False
        self.arrange()
        self.idle("Installed. Start ABBA whenever you like.")

    def on_close(self) -> None:
        if self.installing:
            if not messagebox.askyesno(
                    TITLE, "The installation is not finished. Close anyway? "
                           "It resumes where it stopped next time."):
                return
            self.exit_code = 1  # the all-users installer must not go on as if it were done
        self.remember()
        self.root.destroy()


def main(argv: list[str] | None = None) -> None:
    """`python -m abba_installer.gui [--install-all]`. --install-all is what the
    all-users installer runs: install everything, then close; the exit code
    says whether it succeeded."""
    args = sys.argv[1:] if argv is None else argv
    sharp_on_windows()  # both before the first window exists
    own_taskbar_entry()
    root = tk.Tk()
    app = App(root, install_all="--install-all" in args)
    root.mainloop()
    # Only the all-users installer acts on it; for one user, an install stopped
    # or failed is shown in the window and resumed from there.
    sys.exit(app.exit_code if app.install_all else 0)


if __name__ == "__main__":
    main()
