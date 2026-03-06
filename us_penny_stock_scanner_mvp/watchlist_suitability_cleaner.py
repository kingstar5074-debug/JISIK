from __future__ import annotations

"""
Watchlist Suitability Cleaner.

현재 watchlist(tickers.txt)에 포함된 심볼들을
- 현재 활성 전략 프로파일의 유효 필터(effective filters)
- 현재 세션 기준 시세(provider quote)
를 사용해 적합/부적합으로 분류하고,
선택적으로 구조적으로 부적합한 심볼을 watchlist 에서 제거(clean)하는 도구입니다.

주의:
- 새로운 종목을 찾거나(universe search) 시장 전역을 스캔하지 않습니다.
- 오직 현재 watchlist 에 있는 심볼만 평가합니다.
"""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from scanner.filters import ScanFilters
from scanner.market_hours import MarketClock
from scanner.models import QuoteSnapshot
from scanner.providers.factory import get_market_data_provider
from scanner.strategy_profiles import (
    StrategyProfile,
    get_effective_filters,
    get_strategy_profile,
)
from universe.watchlist_universe import WatchlistUniverseProvider
from config import load_config


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ClassificationResult:
    symbol: str
    status: str
    reason: str
    details: Dict[str, object]


class _ProviderConfig:
    """
    get_market_data_provider 에 필요한 최소 필드만 제공하는 경량 설정 객체.
    - data_provider
    - polygon_api_key
    - per_symbol_delay_seconds
    """

    def __init__(self, name: str, polygon_api_key: str | None, per_symbol_delay_seconds: float) -> None:
        self.data_provider = name
        self.polygon_api_key = polygon_api_key or ""
        self.per_symbol_delay_seconds = per_symbol_delay_seconds


def _load_watchlist(path: Path) -> List[str]:
    provider = WatchlistUniverseProvider(path)
    try:
        return provider.load_symbols()
    except FileNotFoundError:
        print(f"watchlist file not found: {path}")
        return []


def _build_provider(provider_name: str, polygon_api_key: str | None, per_symbol_delay_seconds: float):
    cfg = _ProviderConfig(provider_name, polygon_api_key, per_symbol_delay_seconds)
    return get_market_data_provider(cfg)


def _classify_symbol(
    symbol: str,
    quote: QuoteSnapshot | None,
    filters: ScanFilters,
) -> ClassificationResult:
    """
    활성 전략 프로파일의 유효 필터를 기준으로 심볼 하나를 분류한다.
    최소 분류:
    - unsuitable_price_too_high
    - unsuitable_price_too_low
    - unsuitable_negative_change
    - unsuitable_change_below_threshold
    - unsuitable_intraday
    - unsuitable_missing_data
    - suitable
    """

    if quote is None:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_missing_data",
            reason="missing quote data",
            details={},
        )

    price = quote.current_price
    change = quote.percent_change
    intraday = quote.intraday_change_percent

    # 필수 값 누락 시 missing_data 로 분류
    if price is None or change is None or intraday is None:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_missing_data",
            reason="missing price/change/intraday data",
            details={
                "has_price": price is not None,
                "has_change": change is not None,
                "has_intraday": intraday is not None,
            },
        )

    if price > filters.max_price:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_price_too_high",
            reason="price above allowed maximum",
            details={
                "price": price,
                "price_max": filters.max_price,
            },
        )

    if price < filters.min_price:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_price_too_low",
            reason="price below allowed minimum",
            details={
                "price": price,
                "price_min": filters.min_price,
            },
        )

    # 음수 변동은 전략 기대와 반대 방향인 경우가 많으므로 별도 분류
    if change < 0:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_negative_change",
            reason="negative daily change",
            details={
                "change": change,
            },
        )

    if change < filters.min_change_percent:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_change_below_threshold",
            reason="change below strategy threshold",
            details={
                "change": change,
                "change_min": filters.min_change_percent,
            },
        )

    if intraday < filters.min_intraday_change_percent:
        return ClassificationResult(
            symbol=symbol,
            status="unsuitable_intraday",
            reason="intraday move below strategy threshold",
            details={
                "intraday": intraday,
                "intraday_min": filters.min_intraday_change_percent,
            },
        )

    return ClassificationResult(
        symbol=symbol,
        status="suitable",
        reason="passes all checks",
        details={},
    )


def _format_console_line(result: ClassificationResult) -> str:
    s = result.symbol
    st = result.status
    d = result.details

    if st == "suitable":
        return f"- {s} -> suitable"
    if st == "unsuitable_price_too_high":
        return f"- {s} -> unsuitable_price_too_high (price={d.get('price')} > max={d.get('price_max')})"
    if st == "unsuitable_price_too_low":
        return f"- {s} -> unsuitable_price_too_low (price={d.get('price')} < min={d.get('price_min')})"
    if st == "unsuitable_negative_change":
        return f"- {s} -> unsuitable_negative_change (change={d.get('change')})"
    if st == "unsuitable_change_below_threshold":
        return (
            f"- {s} -> unsuitable_change_below_threshold "
            f"(change={d.get('change')} < min={d.get('change_min')})"
        )
    if st == "unsuitable_intraday":
        return (
            f"- {s} -> unsuitable_intraday "
            f"(intraday={d.get('intraday')} < min={d.get('intraday_min')})"
        )
    if st == "unsuitable_missing_data":
        return f"- {s} -> unsuitable_missing_data"
    return f"- {s} -> {st}"


def _save_json_report(
    out_dir: Path,
    provider_name: str,
    profile: StrategyProfile,
    effective_filters: ScanFilters,
    results: List[ClassificationResult],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "watchlist_suitability_report.json"

    suitable_count = sum(1 for r in results if r.status == "suitable")
    total = len(results)
    summary = {
        "total": total,
        "suitable": suitable_count,
        "unsuitable": total - suitable_count,
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider_name,
        "strategy_profile": profile.name,
        "effective_filters": {
            "price_min": effective_filters.min_price,
            "price_max": effective_filters.max_price,
            "change_min": effective_filters.min_change_percent,
            "gap_min": effective_filters.min_gap_percent,
            "intraday_min": effective_filters.min_intraday_change_percent,
            "volume_ratio_min": effective_filters.min_volume_ratio,
            "avg_volume_min": effective_filters.min_average_volume,
            "dollar_volume_min": effective_filters.min_dollar_volume,
        },
        "summary": summary,
        "results": [
            {
                "symbol": r.symbol,
                "status": r.status,
                "reason": r.reason,
                "details": r.details,
            }
            for r in results
        ],
    }

    try:
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report saved to {out_path}")
    except Exception as e:  # pragma: no cover - 방어적
        print(f"Failed to save JSON report: {e}")


def _clean_watchlist(tickers_file: Path, original_symbols: List[str], results: List[ClassificationResult]) -> None:
    if not tickers_file.exists():
        print(f"tickers file not found, skip cleaning: {tickers_file}")
        return

    removable_statuses = {
        "unsuitable_price_too_high",
        "unsuitable_price_too_low",
        "unsuitable_missing_data",
    }
    to_remove = {r.symbol for r in results if r.status in removable_statuses}
    if not to_remove:
        print("No structurally unsuitable symbols to remove.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"watchlist_suitability_backup_{ts}.txt"
    backup_path = PROJECT_ROOT / backup_name

    try:
        backup_path.write_text(tickers_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"Failed to create backup, aborting clean: {e}")
        return

    new_symbols = [s for s in original_symbols if s.strip().upper() not in to_remove]

    try:
        content = "\n".join(new_symbols) + ("\n" if new_symbols else "")
        tickers_file.write_text(content, encoding="utf-8")
        print(f"Cleaned watchlist written to {tickers_file}")
    except Exception as e:  # pragma: no cover - 방어적
        print(f"Failed to write cleaned watchlist: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate watchlist symbols for strategy suitability.")
    parser.add_argument(
        "--provider",
        type=str,
        default="yahoo",
        help="data provider name (default: yahoo)",
    )
    parser.add_argument(
        "--strategy-profile",
        type=str,
        default=None,
        help="override active STRATEGY_PROFILE (default: value from .env)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "remove structurally unsuitable symbols from watchlist "
            "(price too high/low or missing data; creates backup first)"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print per-symbol classification (otherwise only unsuitable symbols are listed)",
    )
    args = parser.parse_args()

    cfg = load_config()
    tickers_path = cfg.tickers_file

    symbols = _load_watchlist(tickers_path)
    if not symbols:
        print("Watchlist is empty or file missing.")
        return 0

    # 전략 프로파일 로드
    profile_name = (args.strategy_profile or cfg.strategy_profile).strip()
    try:
        profile = get_strategy_profile(profile_name, cfg.strategy_profiles_file)
    except ValueError as e:
        print(str(e))
        return 1

    # 현재 세션 기준 유효 필터 계산
    clock = MarketClock()
    session = clock.current_session()
    effective_filters = get_effective_filters(cfg.filters, session, profile)

    # provider 생성
    try:
        provider = _build_provider(args.provider, cfg.polygon_api_key, cfg.per_symbol_delay_seconds)
    except Exception as e:
        print(f"provider init failed ({args.provider}): {e}")
        return 1

    # 시세 조회
    print(
        f"Evaluating {len(symbols)} symbol(s) with provider={args.provider}, "
        f"strategy_profile={profile.name}, session={session}..."
    )
    try:
        quotes: Dict[str, QuoteSnapshot] = provider.fetch_quotes(  # type: ignore[assignment]
            symbols=[s.strip().upper() for s in symbols if s.strip()],
            market_session=session,
        )
    except Exception as e:
        print(f"Failed to fetch quotes: {e}")
        quotes = {}

    # 분류
    results: List[ClassificationResult] = []
    for raw in symbols:
        sym = raw.strip().upper()
        if not sym:
            continue
        q = quotes.get(sym)
        res = _classify_symbol(sym, q, effective_filters)
        results.append(res)

    total = len(results)
    suitable_count = sum(1 for r in results if r.status == "suitable")
    unsuitable_count = total - suitable_count

    print("")
    print(f"총 심볼 수: {total}")
    print(f"Suitable: {suitable_count}")
    print(f"Unsuitable: {unsuitable_count}")

    if args.verbose:
        print("")
        print("Detailed results:")
        for r in results:
            print(_format_console_line(r))
    elif unsuitable_count > 0:
        print("")
        print("Unsuitable details:")
        for r in results:
            if r.status != "suitable":
                print(_format_console_line(r))

    # JSON 리포트 저장
    suitability_dir = cfg.reports_dir / "watchlist_suitability"
    _save_json_report(suitability_dir, args.provider, profile, effective_filters, results)

    # clean 모드: 구조적으로 부적합한 심볼만 제거
    if args.clean:
        _clean_watchlist(tickers_path, [s.strip().upper() for s in symbols if s.strip()], results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

