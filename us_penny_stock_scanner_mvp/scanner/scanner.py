from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Mapping, Tuple

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

# Per-symbol status for debug output (first failure stage)
STATUS_PASSED = "passed"
STATUS_MISSING_DATA = "missing_data"
STATUS_FAILED_PRICE = "failed_price"
STATUS_FAILED_CHANGE = "failed_change"
STATUS_FAILED_GAP = "failed_gap"
STATUS_FAILED_INTRADAY = "failed_intraday"
STATUS_FAILED_VOLUME_RATIO = "failed_volume_ratio"
STATUS_FAILED_AVG_VOLUME = "failed_avg_volume"
STATUS_FAILED_DOLLAR_VOLUME = "failed_dollar_volume"


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
    # When debug_filters was True: per-symbol status + details; effective filters for the run
    per_symbol_filter_results: Optional[List[Dict[str, Any]]] = None
    effective_filters_snapshot: Optional[ScanFilters] = None


def _filter_failure_reason(q: QuoteSnapshot, f: ScanFilters) -> Optional[str]:
    """
    필터 탈락 사유를 한 가지로 분류한다.
    - None 이면 모든 필터 통과
    - 그렇지 않으면 'missing_data', 'price', 'change', 'gap', 'intraday',
      'volume_ratio', 'average_volume', 'dollar_volume' 중 하나를 반환
    """
    status, _ = _filter_failure_status_and_details(q, f)
    if status == STATUS_PASSED:
        return None
    return status


def _filter_failure_status_and_details(
    q: QuoteSnapshot, f: ScanFilters
) -> Tuple[str, Dict[str, Any]]:
    """
    첫 번째 실패 단계의 status와 상세 정보를 반환한다.
    - status: STATUS_PASSED | STATUS_MISSING_DATA | STATUS_FAILED_* 중 하나
    - details: 실패 시 관련 값/임계값 (디버그 출력용)
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
        return (STATUS_MISSING_DATA, {})

    if not (f.min_price <= q.current_price <= f.max_price):
        return (
            STATUS_FAILED_PRICE,
            {
                "price": q.current_price,
                "allowed_min": f.min_price,
                "allowed_max": f.max_price,
            },
        )

    if q.percent_change < f.min_change_percent:
        return (
            STATUS_FAILED_CHANGE,
            {"change": q.percent_change, "min_required": f.min_change_percent},
        )

    if q.volume_ratio < f.min_volume_ratio:
        return (
            STATUS_FAILED_VOLUME_RATIO,
            {"volume_ratio": q.volume_ratio, "min_required": f.min_volume_ratio},
        )

    if q.gap_percent < f.min_gap_percent:
        return (
            STATUS_FAILED_GAP,
            {"gap_percent": q.gap_percent, "min_required": f.min_gap_percent},
        )

    if q.intraday_change_percent < f.min_intraday_change_percent:
        return (
            STATUS_FAILED_INTRADAY,
            {
                "intraday_change_percent": q.intraday_change_percent,
                "min_required": f.min_intraday_change_percent,
            },
        )

    if q.average_volume is not None and q.average_volume < f.min_average_volume:
        return (
            STATUS_FAILED_AVG_VOLUME,
            {
                "average_volume": q.average_volume,
                "min_required": f.min_average_volume,
            },
        )

    if q.dollar_volume is not None and q.dollar_volume < f.min_dollar_volume:
        return (
            STATUS_FAILED_DOLLAR_VOLUME,
            {
                "dollar_volume": q.dollar_volume,
                "min_required": f.min_dollar_volume,
            },
        )

    return (STATUS_PASSED, {})


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

    def scan(
        self, symbols: Iterable[str], debug_filters: bool = False
    ) -> ScanResult:
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

        return self.scan_with_quotes(
            quotes,
            current_session=session,
            total_requested=total_requested,
            debug_filters=debug_filters,
        )

    def scan_with_quotes(
        self,
        quotes: Mapping[str, QuoteSnapshot],
        current_session: Optional[str] = None,
        total_requested: Optional[int] = None,
        debug_filters: bool = False,
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

        # 유효 필터 (세션 기준) - 디버그 시 스냅샷 및 일관된 필터링에 사용
        effective_filters_run = get_effective_filters(
            self.base_filters, session, self.strategy_profile
        )

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

        per_symbol_results: List[Dict[str, Any]] = [] if debug_filters else []

        filtered: List[QuoteSnapshot] = []
        for sym, q in quotes.items():
            effective_filters = get_effective_filters(
                self.base_filters,
                q.market_session,
                self.strategy_profile,
            )
            status, details = _filter_failure_status_and_details(q, effective_filters)
            reason = None if status == STATUS_PASSED else status

            if debug_filters:
                if status == STATUS_PASSED:
                    weights = get_session_weights(
                        self.strategy_profile, q.market_session
                    )
                    s = score_quote(q, weights)
                    score_val = s.total_score if s is not None else None
                    per_symbol_results.append(
                        {
                            "symbol": sym,
                            "status": STATUS_PASSED,
                            "details": {"score": score_val} if score_val is not None else {},
                        }
                    )
                else:
                    per_symbol_results.append(
                        {"symbol": sym, "status": status, "details": details}
                    )

            if reason is None:
                filtered.append(q)
                passed_filters += 1
            else:
                if reason == STATUS_MISSING_DATA:
                    missing_data_filtered += 1
                elif reason == STATUS_FAILED_PRICE:
                    price_filtered += 1
                elif reason == STATUS_FAILED_CHANGE:
                    change_filtered += 1
                elif reason == STATUS_FAILED_GAP:
                    gap_filtered += 1
                elif reason == STATUS_FAILED_INTRADAY:
                    intraday_filtered += 1
                elif reason == STATUS_FAILED_VOLUME_RATIO:
                    volume_ratio_filtered += 1
                elif reason == STATUS_FAILED_AVG_VOLUME:
                    average_volume_filtered += 1
                elif reason == STATUS_FAILED_DOLLAR_VOLUME:
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
            per_symbol_filter_results=per_symbol_results if debug_filters else None,
            effective_filters_snapshot=effective_filters_run if debug_filters else None,
        )

