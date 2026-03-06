from __future__ import annotations

from pathlib import Path
from typing import List

from universe.base import UniverseProvider


class WatchlistUniverseProvider(UniverseProvider):
    """
    Universe based on the primary watchlist file (tickers.txt).

    This keeps the original MVP behaviour but hides the file access
    behind a simple interface so we can swap to other universes later.
    """

    def __init__(self, watchlist_path: Path) -> None:
        super().__init__(watchlist_path)

    def load_symbols(self) -> List[str]:
        if not self.source.exists():
            raise FileNotFoundError(f"watchlist file not found: {self.source}")

        text = self.source.read_text(encoding="utf-8")
        lines = text.splitlines()
        return self._normalize_lines(lines)

