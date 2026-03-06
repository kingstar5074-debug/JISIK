from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Mapping

from ..models import MarketSession, QuoteSnapshot


class MarketDataProvider(ABC):
    """
    Provider interface for market data.

    Goal:
    - Keep the scanner logic independent from any single data source.
    - Allow swapping to Polygon/Finnhub later with minimal changes.
    """

    @abstractmethod
    def fetch_quotes(
        self,
        symbols: Iterable[str],
        market_session: MarketSession,
    ) -> Mapping[str, QuoteSnapshot]:
        """
        Fetch quote snapshots keyed by symbol.
        Implementations should be resilient:
        - A failure for one symbol should not crash the whole scan.
        """

