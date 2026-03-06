from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from utils.logger import get_logger
from scanner.filters import ScanFilters, passes_filters
from scanner.market_hours import MarketClock
from scanner.models import QuoteSnapshot
from scanner.providers.base import MarketDataProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class ScanResult:
    matched: List[QuoteSnapshot]
    current_session: str


class PennyStockScanner:
    def __init__(
        self,
        provider: MarketDataProvider,
        filters: ScanFilters,
        clock: MarketClock | None = None,
    ) -> None:
        self.provider = provider
        self.filters = filters
        self.clock = clock or MarketClock()

    def scan(self, symbols: Iterable[str]) -> ScanResult:
        dt_et = self.clock.now_et()
        session = self.clock.session_of(dt_et)
        log.info("Current market session (ET): %s (%s)", session, dt_et.strftime("%Y-%m-%d %H:%M:%S %Z"))

        quotes = self.provider.fetch_quotes(symbols=symbols, market_session=session)

        matched: List[QuoteSnapshot] = []
        for sym, q in quotes.items():
            if passes_filters(q, self.filters):
                matched.append(q)
            else:
                # For MVP, keep non-matching details out of console; logs can be expanded later.
                log.debug("Filtered out %s", sym)

        matched.sort(key=lambda x: (x.percent_change or float("-inf"), x.volume_ratio or float("-inf")), reverse=True)
        return ScanResult(matched=matched, current_session=session)

