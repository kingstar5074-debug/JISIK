from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from scanner.models import MarketSession, QuoteSnapshot
from scanner.providers.base import MarketDataProvider
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class PolygonProviderConfig:
    """
    Configuration for Polygon.io market data.

    This batch only defines the structure; actual HTTP calls and response
    parsing will be implemented in a later batch.
    """

    api_key: str
    base_url: str = "https://api.polygon.io"


class PolygonProvider(MarketDataProvider):
    """
    Polygon-based implementation of MarketDataProvider.

    NOTE:
    - In this batch the class exists only as a stub.
    - fetch_quotes is not implemented yet and MUST NOT be used in production.
    """

    def __init__(self, cfg: PolygonProviderConfig) -> None:
        self.cfg = cfg

    def fetch_quotes(
        self,
        symbols: Iterable[str],
        market_session: MarketSession,
    ) -> Mapping[str, QuoteSnapshot]:
        raise NotImplementedError(
            "PolygonProvider.fetch_quotes is not implemented yet. "
            "This batch only adds the interface and configuration."
        )

