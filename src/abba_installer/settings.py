"""What the window and the command line remember, per user, never next to the code.

    {
      "memory": "8G",                  # Java's maximum heap; empty: jgo chooses
      "prepare": ["elastix"],          # the window's choice of what to install
      "installed": {"0.25.0": [...]},  # what Install completed, per ABBA version
      "extra_dependencies": [],        # Maven coordinates added to ABBA's, e.g. "sc.fiji:fiji-llm:0.1.0"
      "extra_jars": []                 # jar files added to the class path
    }

The last two have no field in the window: they are for whoever edits this file,
or passes --with / --add-jar on the command line.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import launcher
from .launcher import Options


def settings_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "abba-installer" / "settings.json"


def load() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(settings: dict) -> None:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass  # forgetting a setting is not worth an error


def installed(settings: dict) -> list[str] | None:
    """The environments installed with this ABBA version (Java, ABBA and Fiji
    with them), or None if Install was never run for it. Remembered rather than
    checked: checking means starting Java, and what is missing is downloaded
    on first use anyway."""
    record = (settings.get("installed") or {}).get(launcher.ABBA_VERSION)
    return None if record is None else list(record)


def record_installed(environments: list[str]) -> None:
    """After a successful install: merged into the settings as they are on disk,
    since the window may hold older ones."""
    current = load()
    done = set(installed(current) or []) | set(environments)
    current.setdefault("installed", {})[launcher.ABBA_VERSION] = [
        name for name in launcher.ENVIRONMENTS if name in done]
    save(current)


def options(settings: dict) -> Options:
    return Options(max_heap=(settings.get("memory") or "").strip() or None,
                   extra_dependencies=list(settings.get("extra_dependencies") or []),
                   extra_jars=[Path(jar) for jar in settings.get("extra_jars") or []])
