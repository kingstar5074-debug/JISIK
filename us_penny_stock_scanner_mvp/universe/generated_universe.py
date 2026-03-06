from __future__ import annotations

from pathlib import Path
from typing import List

from universe.base import UniverseProvider


class GeneratedUniverseProvider(UniverseProvider):
    """
    Universe based on a larger, file-based candidate list.

    Notes:
    - This is a stepping stone towards a full US-wide penny stock scanner.
    - The file may contain stale/delisted symbols; lookup failures must not
      crash the scanner.
    """

    def __init__(self, universe_path: Path) -> None:
        super().__init__(universe_path)

    def load_symbols(self) -> List[str]:
        if not self.source.exists():
            raise FileNotFoundError(f"universe candidate file not found: {self.source}")

        text = self.source.read_text(encoding="utf-8")
        lines = text.splitlines()
        return self._normalize_lines(lines)

