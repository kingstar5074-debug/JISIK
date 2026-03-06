from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List


class UniverseProvider(ABC):
    """
    Abstract base for symbol-universe providers.

    Examples:
    - WatchlistUniverseProvider: read symbols from tickers.txt
    - GeneratedUniverseProvider: read symbols from a larger candidate file
    - Future API-based providers (e.g. Polygon / Finnhub) can implement this.
    """

    def __init__(self, source: Path) -> None:
        self.source = source

    @abstractmethod
    def load_symbols(self) -> List[str]:
        """
        Load symbols for scanning.

        Returns:
        - Uppercased symbols with whitespace stripped.
        - Duplicates removed where possible.
        """

    @staticmethod
    def _normalize_lines(lines: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in lines:
            s = raw.strip().upper()
            if not s or s.startswith("#"):
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

