"""Link target resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

MARKDOWN_SUFFIXES = (".md", ".markdown")


@dataclass(frozen=True)
class Target:
    kind: Literal["anchor", "file", "external", "unsupported"]
    path: Path | None = None
    anchor: str | None = None
    url: str | None = None


def resolve(href: str, base: Path | None) -> Target:
    href = href.strip()
    if not href:
        return Target("unsupported")
    if href.startswith("#"):
        return Target("anchor", anchor=unquote(href[1:]))
    scheme = urlsplit(href).scheme
    # A single letter "scheme" is a Windows drive letter, not a URL.
    if scheme and len(scheme) > 1:
        if scheme.lower() == "file":
            return _local(unquote(urlsplit(href).path), "", base)
        return Target("external", url=href)
    path_part, _, fragment = href.partition("#")
    return _local(unquote(path_part), unquote(fragment), base)


def _local(path_str: str, fragment: str, base: Path | None) -> Target:
    path = Path(path_str)
    if path.suffix.lower() not in MARKDOWN_SUFFIXES:
        return Target("unsupported")
    if not path.is_absolute():
        root = base.parent if base is not None else Path.cwd()
        path = root / path
    return Target("file", path=path, anchor=fragment or None)
