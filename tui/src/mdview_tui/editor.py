"""External editor command resolution."""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path


def editor_command(
    path: Path, env: Mapping[str, str] | None = None, platform: str | None = None
) -> list[str]:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    windows = platform.startswith("win")
    value = (env.get("VISUAL") or "").strip() or (env.get("EDITOR") or "").strip()
    if value:
        parts = shlex.split(value, posix=not windows)
        if windows:
            parts = [p.strip('"') for p in parts]
    else:
        parts = ["notepad" if windows else "vi"]
    return [*parts, str(path)]
