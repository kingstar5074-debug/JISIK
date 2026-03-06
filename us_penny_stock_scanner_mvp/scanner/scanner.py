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
    total_requested: int
    fetch_success: int
    fetch_failed: int


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

        # Normalize the incoming iterable so we can compute counts reliably.
        symbol_list: list[str] = []
        for raw in symbols:
            s = raw.strip().upper()
            if not s:
                continue
            symbol_list.append(s)

        total_requested = len(symbol_list)
        quotes = self.provider.fetch_quotes(symbols=symbol_list, market_session=session)
        fetch_success = len(quotes)
        fetch_failed = max(total_requested - fetch_success, 0)

        matched: List[QuoteSnapshot] = []
        for sym, q in quotes.items():
            if passes_filters(q, self.filters):
                matched.append(q)
            else:
                # For MVP, keep non-matching details out of console; logs can be expanded later.
                log.debug("Filtered out %s", sym)

        matched.sort(
            key=lambda x: (x.percent_change or float("-inf"), x.volume_ratio or float("-inf")),
            reverse=True,
        )
        return ScanResult(
            matched=matched,
            current_session=session,
            total_requested=total_requested,
            fetch_success=fetch_success,
            fetch_failed=fetch_failed,
        )

