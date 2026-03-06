from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from utils.logger import get_logger
from scanner.filters import ScanFilters, passes_filters
from scanner.market_hours import MarketClock
from scanner.models import QuoteSnapshot
from scanner.providers.base import MarketDataProvider
from scanner.scoring import StockScore, score_quote

log = get_logger(__name__)


@dataclass(frozen=True)
class ScanResult:
    matched: List[QuoteSnapshot]
    scores: List[StockScore]
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
        top_results: int = 20,
    ) -> None:
        self.provider = provider
        self.filters = filters
        self.clock = clock or MarketClock()
        self.top_results = top_results

    def scan(self, symbols: Iterable[str]) -> ScanResult:
        dt_et = self.clock.now_et()
        session = self.clock.session_of(dt_et)
        log.info("Current market session (ET): %s (%s)", session, dt_et.strftime("%Y-%m-%d %H:%M:%S %Z"))

        # Normalize incoming symbols
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

        filtered: List[QuoteSnapshot] = []
        for sym, q in quotes.items():
            if passes_filters(q, self.filters):
                filtered.append(q)
            else:
                log.debug("Filtered out %s", sym)

        scored_pairs: List[tuple[QuoteSnapshot, StockScore]] = []
        for q in filtered:
            s = score_quote(q)
            if s is None:
                continue
            scored_pairs.append((q, s))

        scored_pairs.sort(key=lambda pair: pair[1].total_score, reverse=True)

        if self.top_results > 0:
            scored_pairs = scored_pairs[: self.top_results]

        matched: List[QuoteSnapshot] = [q for q, _ in scored_pairs]
        scores: List[StockScore] = [s for _, s in scored_pairs]

        return ScanResult(
            matched=matched,
            scores=scores,
            current_session=session,
            total_requested=total_requested,
            fetch_success=fetch_success,
            fetch_failed=fetch_failed,
        )

