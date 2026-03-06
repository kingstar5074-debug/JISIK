from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Mapping

from utils.logger import get_logger
from scanner.filters import ScanFilters
from scanner.market_hours import MarketClock
from scanner.models import QuoteSnapshot
from scanner.providers.base import MarketDataProvider
from scanner.scoring import StockScore, score_quote
from scanner.strategy_profiles import (
    StrategyProfile,
    get_effective_filters,
    get_session_weights,
)
from scanner.theme_tagger import detect_theme_tags

log = get_logger(__name__)


@dataclass(frozen=True)
class FilterReport:
    total_requested: int
    fetch_success: int
    fetch_failed: int
    missing_data_filtered: int
    price_filtered: int
    change_filtered: int
    gap_filtered: int
    intraday_filtered: int
    volume_ratio_filtered: int
    average_volume_filtered: int
    dollar_volume_filtered: int
    passed_filters: int
    scored_count: int
    returned_count: int


@dataclass(frozen=True)
class ScanResult:
    matched: List[QuoteSnapshot]
    scores: List[StockScore]
    current_session: str
    total_requested: int
    fetch_success: int
    fetch_failed: int
    filter_report: FilterReport
    theme_tags: Dict[str, List[str]]


def _filter_failure_reason(q: QuoteSnapshot, f: ScanFilters) -> Optional[str]:
    """
    필터 탈락 사유를 한 가지로 분류한다.
    - None 이면 모든 필터 통과
    - 그렇지 않으면 'missing_data', 'price', 'change', 'gap', 'intraday',
      'volume_ratio', 'average_volume', 'dollar_volume' 중 하나를 반환
    """

    if (
        q.current_price is None
        or q.percent_change is None
        or q.volume_ratio is None
        or q.gap_percent is None
        or q.intraday_change_percent is None
        or q.average_volume is None
        or q.dollar_volume is None
    ):
        return "missing_data"

    if not (f.min_price <= q.current_price <= f.max_price):
        return "price"

    if q.percent_change < f.min_change_percent:
        return "change"

    if q.volume_ratio < f.min_volume_ratio:
        return "volume_ratio"

    if q.gap_percent < f.min_gap_percent:
        return "gap"

    if q.intraday_change_percent < f.min_intraday_change_percent:
        return "intraday"

    if q.average_volume < f.min_average_volume:
        return "average_volume"

    if q.dollar_volume < f.min_dollar_volume:
        return "dollar_volume"

    return None


class PennyStockScanner:
    def __init__(
        self,
        provider: MarketDataProvider,
        filters: ScanFilters,
        strategy_profile: StrategyProfile,
        clock: MarketClock | None = None,
        top_results: int = 20,
    ) -> None:
        self.provider = provider
        self.base_filters = filters
        self.strategy_profile = strategy_profile
        self.clock = clock or MarketClock()
        self.top_results = top_results

    def scan(self, symbols: Iterable[str]) -> ScanResult:
        dt_et = self.clock.now_et()
        session = self.clock.session_of(dt_et)
        log.info(
            "Current market session (ET): %s (%s)",
            session,
            dt_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )
        log.info("Using strategy profile: %s", self.strategy_profile.name)

        # Normalize incoming symbols
        symbol_list: list[str] = []
        for raw in symbols:
            s = raw.strip().upper()
            if not s:
                continue
            symbol_list.append(s)

        total_requested = len(symbol_list)
        quotes = self.provider.fetch_quotes(symbols=symbol_list, market_session=session)

        return self.scan_with_quotes(quotes, current_session=session, total_requested=total_requested)

    def scan_with_quotes(
        self,
        quotes: Mapping[str, QuoteSnapshot],
        current_session: Optional[str] = None,
        total_requested: Optional[int] = None,
    ) -> ScanResult:
        """
        이미 조회된 quotes 를 기반으로 필터/점수화를 수행한다.
        - compare_strategies.py 등에서 provider 호출을 재사용하기 위한 용도.
        """

        session = current_session or self.clock.current_session()
        fetch_success = len(quotes)
        if total_requested is None:
            total_requested = fetch_success
        fetch_failed = max(total_requested - fetch_success, 0)

        # 필터 카운트 초기화
        missing_data_filtered = 0
        price_filtered = 0
        change_filtered = 0
        gap_filtered = 0
        intraday_filtered = 0
        volume_ratio_filtered = 0
        average_volume_filtered = 0
        dollar_volume_filtered = 0
        passed_filters = 0

        filtered: List[QuoteSnapshot] = []
        for sym, q in quotes.items():
            effective_filters = get_effective_filters(
                self.base_filters,
                q.market_session,
                self.strategy_profile,
            )
            reason = _filter_failure_reason(q, effective_filters)
            if reason is None:
                filtered.append(q)
                passed_filters += 1
            else:
                if reason == "missing_data":
                    missing_data_filtered += 1
                elif reason == "price":
                    price_filtered += 1
                elif reason == "change":
                    change_filtered += 1
                elif reason == "gap":
                    gap_filtered += 1
                elif reason == "intraday":
                    intraday_filtered += 1
                elif reason == "volume_ratio":
                    volume_ratio_filtered += 1
                elif reason == "average_volume":
                    average_volume_filtered += 1
                elif reason == "dollar_volume":
                    dollar_volume_filtered += 1
                log.debug("Filtered out %s due to %s", sym, reason)

        scored_pairs: List[tuple[QuoteSnapshot, StockScore]] = []
        for q in filtered:
            weights = get_session_weights(self.strategy_profile, q.market_session)
            s = score_quote(q, weights)
            if s is None:
                continue
            scored_pairs.append((q, s))

        scored_pairs.sort(key=lambda pair: pair[1].total_score, reverse=True)

        if self.top_results > 0:
            scored_pairs = scored_pairs[: self.top_results]

        matched: List[QuoteSnapshot] = [q for q, _ in scored_pairs]
        scores: List[StockScore] = [s for _, s in scored_pairs]

        theme_map: Dict[str, List[str]] = {}
        for q in matched:
            theme_map[q.symbol] = detect_theme_tags(q.symbol)

        filter_report = FilterReport(
            total_requested=total_requested,
            fetch_success=fetch_success,
            fetch_failed=fetch_failed,
            missing_data_filtered=missing_data_filtered,
            price_filtered=price_filtered,
            change_filtered=change_filtered,
            gap_filtered=gap_filtered,
            intraday_filtered=intraday_filtered,
            volume_ratio_filtered=volume_ratio_filtered,
            average_volume_filtered=average_volume_filtered,
            dollar_volume_filtered=dollar_volume_filtered,
            passed_filters=passed_filters,
            scored_count=len(scored_pairs),
            returned_count=len(matched),
        )

        log.info(
            "Filter report: total=%d, success=%d, failed=%d, "
            "missing=%d, price=%d, change=%d, gap=%d, intraday=%d, "
            "vol_ratio=%d, avg_vol=%d, dollar_vol=%d, passed=%d, "
            "scored=%d, returned=%d",
            filter_report.total_requested,
            filter_report.fetch_success,
            filter_report.fetch_failed,
            filter_report.missing_data_filtered,
            filter_report.price_filtered,
            filter_report.change_filtered,
            filter_report.gap_filtered,
            filter_report.intraday_filtered,
            filter_report.volume_ratio_filtered,
            filter_report.average_volume_filtered,
            filter_report.dollar_volume_filtered,
            filter_report.passed_filters,
            filter_report.scored_count,
            filter_report.returned_count,
        )

        return ScanResult(
            matched=matched,
            scores=scores,
            current_session=session,
            total_requested=total_requested,
            fetch_success=fetch_success,
            fetch_failed=fetch_failed,
            filter_report=filter_report,
            theme_tags=theme_map,
        )

