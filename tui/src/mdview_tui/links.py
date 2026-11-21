"""Link target resolution."""

from __future__ import annotations

import os
import re
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


def display_href(href: str) -> str:
    """Return a link target as the user wrote it, for showing on screen.

    markdown-it percent-encodes every href and image src (normalizeLink), so
    `[x](図.png)` arrives as `%E5%9B%B3.png`. Malformed escapes are left as they are.
    """
    return unquote(href)


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
            # Local paths, never handed to the OS (doc/common.md 4).
            return _local(*_file_url(href), base)
        return Target("external", url=href)
    path_part, _, fragment = href.partition("#")
    return _local(unquote(path_part), unquote(fragment), base)


def _file_url(href: str) -> tuple[str, str]:
    """Split a `file:` URL into (local path, anchor)."""
    parts = urlsplit(href)
    path = unquote(parts.path)
    # file:///C:/x.md -> C:/x.md, only meaningful where drive letters exist.
    if os.name == "nt" and re.match(r"/[A-Za-z]:([/\\]|$)", path):
        path = path[1:]
    if parts.netloc and parts.netloc.lower() != "localhost":
        path = f"//{parts.netloc}{path}"  # UNC path: file://server/share/x.md
    return path, unquote(parts.fragment)


def _local(path_str: str, fragment: str, base: Path | None) -> Target:
    path = Path(path_str)
    if path.suffix.lower() not in MARKDOWN_SUFFIXES:
        return Target("unsupported")
    if not path.is_absolute():
        root = base.parent if base is not None else Path.cwd()
        path = root / path
    return Target("file", path=path, anchor=fragment or None)
