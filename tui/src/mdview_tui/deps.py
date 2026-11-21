"""Check the versions of the required libraries before they are imported.

This module must import only the standard library: the portable version runs
`dependency_error()` before its third-party imports.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re

# (distribution name, import name, minimum version); keep in sync with pyproject.toml
REQUIREMENTS = (
    ("textual", "textual", "2.0"),
    ("markdown-it-py", "markdown_it", "3.0"),
    ("PyYAML", "yaml", "6.0"),
)


def version_tuple(version: str) -> tuple[int, ...]:
    """Return the leading numeric release part of `version`, e.g. "2.1.2-1" -> (2, 1, 2)."""
    m = re.match(r"\d+(?:\.\d+)*", version.strip())
    return tuple(int(p) for p in m.group(0).split(".")) if m else ()


def _installed_version(dist: str, module: str) -> str | None:
    """Return the installed version, "" if importable but unknown, or None if missing."""
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return "" if importlib.util.find_spec(module) is not None else None


def dependency_error() -> str | None:
    """Return a message describing missing or too old libraries, or None if all are usable."""
    problems = []
    for dist, module, minimum in REQUIREMENTS:
        found = _installed_version(dist, module)
        if found is None:
            problems.append(f"{dist}>={minimum} is required (not installed)")
        elif found and version_tuple(found) < version_tuple(minimum):
            problems.append(f"{dist}>={minimum} is required (found {found})")
    return "; ".join(problems) or None
