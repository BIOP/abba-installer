"""What the window and the command line remember, per user, never next to the code.

    {
      "memory": "8G",                  # Java's maximum heap; empty: jgo chooses
      "prepare": ["elastix"],          # the window's Prepare checkboxes
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


def options(settings: dict) -> Options:
    return Options(max_heap=(settings.get("memory") or "").strip() or None,
                   extra_dependencies=list(settings.get("extra_dependencies") or []),
                   extra_jars=[Path(jar) for jar in settings.get("extra_jars") or []])
