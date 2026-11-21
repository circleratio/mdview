"""File change detection by polling os.stat()."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

Status = Literal["unchanged", "modified", "deleted"]


class FileWatcher:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._sig = self._stat()

    def _stat(self) -> tuple[int, int] | None:
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def check(self) -> Status:
        """Report a change since the previous call.

        "deleted" is reported once when the file disappears; a re-created
        file is reported as "modified".
        """
        sig = self._stat()
        if sig == self._sig:
            return "unchanged"
        old, self._sig = self._sig, sig
        if sig is None:
            return "deleted"
        return "modified" if old != sig else "unchanged"
