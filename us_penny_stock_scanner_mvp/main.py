from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from config import load_config
from scanner.market_hours import MarketClock
from scanner.providers.factory import get_market_data_provider
from scanner.scanner import PennyStockScanner
from scanner.strategy_profiles import get_effective_filters, get_strategy_profile
from universe.generated_universe import GeneratedUniverseProvider
from universe.watchlist_universe import WatchlistUniverseProvider
from utils.formatter import render_console_tables
from utils.logger import get_logger

log = get_logger(__name__)


def _format_debug_line(entry: dict) -> str:
    """종목별 필터 디버그 한 줄 포맷 (예: ABCD -> failed_price (price=2.14, allowed=0.05~1.0))"""
    sym = entry.get("symbol", "")
    status = entry.get("status", "")
    details = entry.get("details") or {}
    if status == "passed":
        score = details.get("score")
        if score is not None:
            return f"- {sym} -> passed (score={score:.1f})"
        return f"- {sym} -> passed"
    if status == "missing_data":
        return f"- {sym} -> missing_data"
    if status == "failed_price":
        p = details.get("price")
        lo = details.get("allowed_min")
        hi = details.get("allowed_max")
        return f"- {sym} -> failed_price (price={p}, allowed={lo}~{hi})"
    if status == "failed_change":
        c = details.get("change")
        m = details.get("min_required")
        return f"- {sym} -> failed_change (change={c}, min={m})"
    if status == "failed_gap":
        g = details.get("gap_percent")
        m = details.get("min_required")
        return f"- {sym} -> failed_gap (gap={g}, min={m})"
    if status == "failed_intraday":
        i = details.get("intraday_change_percent")
        m = details.get("min_required")
        return f"- {sym} -> failed_intraday (intraday={i}, min={m})"
    if status == "failed_volume_ratio":
        v = details.get("volume_ratio")
        m = details.get("min_required")
        return f"- {sym} -> failed_volume_ratio (volume_ratio={v}, min={m})"
    if status == "failed_avg_volume":
        a = details.get("average_volume")
        m = details.get("min_required")
        return f"- {sym} -> failed_avg_volume (avg_vol={a}, min={m})"
    if status == "failed_dollar_volume":
        d = details.get("dollar_volume")
        m = details.get("min_required")
        return f"- {sym} -> failed_dollar_volume (dollar_vol={d}, min={m})"
    return f"- {sym} -> {status}"


def main() -> int:
    parser = argparse.ArgumentParser(description="US Penny Stock Scanner MVP")
    parser.add_argument(
        "--debug-filters",
        action="store_true",
        help="Print per-symbol filter debug output (why each symbol passed or failed).",
    )
    parser.add_argument(
        "--debug-filter-json",
        action="store_true",
        help="Save per-symbol filter outcomes to reports/filter_debug/filter_debug_<timestamp>.json",
    )
    parser.add_argument(
        "--build-universe",
        action="store_true",
        help=(
            "When SCAN_MODE=universe, run Polygon smart universe builder first "
            "before scanning."
        ),
    )
    args = parser.parse_args()

    cfg = load_config()
    console = Console()

    if cfg.scan_mode not in {"watchlist", "universe"}:
        console.print(
            f"지원하지 않는 SCAN_MODE 값입니다: '{cfg.scan_mode}'. "
            "watchlist 또는 universe 중 하나여야 합니다."
        )
        return 1

    # 전략 프로파일 로드/검증
    try:
        profile = get_strategy_profile(cfg.strategy_profile, cfg.strategy_profiles_file)
    except ValueError as e:
        console.print(str(e))
        return 1

    # SCAN_MODE=universe 이고 --build-universe 가 지정된 경우,
    # Polygon 기반 스마트 유니버스를 먼저 생성한다.
    if args.build_universe and cfg.scan_mode == "universe":
        console.print("SCAN_MODE=universe 이므로 Polygon 스마트 유니버스를 먼저 생성합니다.")
        try:
            from smart_universe_builder import main as smart_universe_main
        except Exception as e:  # pragma: no cover - 방어적
            console.print(f"스마트 유니버스 빌더를 로드하지 못했습니다: {e}")
            return 1

        ret = smart_universe_main()
        if ret != 0:
            console.print("스마트 유니버스 생성에 실패했습니다. 스캔을 중단합니다.")
            return ret

    # Select symbol universe based on scan mode.
    if cfg.scan_mode == "universe":
        universe = GeneratedUniverseProvider(cfg.universe_file)
    else:
        universe = WatchlistUniverseProvider(cfg.tickers_file)

    try:
        tickers = universe.load_symbols()
    except FileNotFoundError as e:
        console.print(str(e))
        return 1

    if not tickers:
        console.print("스캔할 티커가 없습니다.")
        return 1

    clock = MarketClock()
    session = clock.current_session()

    # 유효 필터: config 기본값 + 전략 프로파일 오버레이 (필터링/로그 동일 값 사용)
    effective_filters = get_effective_filters(cfg.filters, session, profile)

    console.print(f"현재 시장 세션(ET): {session}")
    console.print(f"현재 스캔 모드: {cfg.scan_mode}")
    console.print(f"현재 데이터 provider: {cfg.data_provider}")
    console.print(f"현재 전략 프로파일: {profile.name}")
    console.print(f"전략 프로파일 파일: {cfg.strategy_profiles_file.name}")
    console.print(f"로드한 티커 수: {len(tickers)}")
    console.print(
        "기본 config 필터: "
        f"price {cfg.filters.min_price}~{cfg.filters.max_price} / "
        f"change >= {cfg.filters.min_change_percent} / "
        f"gap >= {cfg.filters.min_gap_percent} / "
        f"intraday >= {cfg.filters.min_intraday_change_percent} / "
        f"volume_ratio >= {cfg.filters.min_volume_ratio} / "
        f"avg_volume >= {cfg.filters.min_average_volume} / "
        f"dollar_volume >= {cfg.filters.min_dollar_volume}"
    )
    console.print(
        "전략 적용 후 유효 필터: "
        f"price {effective_filters.min_price}~{effective_filters.max_price} / "
        f"change >= {effective_filters.min_change_percent} / "
        f"gap >= {effective_filters.min_gap_percent} / "
        f"intraday >= {effective_filters.min_intraday_change_percent} / "
        f"volume_ratio >= {effective_filters.min_volume_ratio} / "
        f"avg_volume >= {effective_filters.min_average_volume} / "
        f"dollar_volume >= {effective_filters.min_dollar_volume}"
    )

    try:
        provider = get_market_data_provider(cfg)
    except (RuntimeError, ValueError) as e:
        console.print(str(e))
        return 1

    scanner = PennyStockScanner(
        provider=provider,
        filters=cfg.filters,
        strategy_profile=profile,
        clock=clock,
        top_results=cfg.top_results,
    )

    result = scanner.scan(tickers, debug_filters=args.debug_filters or args.debug_filter_json)

    render_console_tables(result.matched, scores=result.scores, console=console)

    console.print(f"조회 성공: {result.fetch_success}")
    console.print(f"조회 실패: {result.fetch_failed}")

    fr = result.filter_report
    console.print("필터 리포트:")
    console.print(f"- 요청 종목 수: {fr.total_requested}")
    console.print(f"- 조회 성공: {fr.fetch_success}")
    console.print(f"- 조회 실패: {fr.fetch_failed}")
    console.print(f"- 데이터 누락 탈락: {fr.missing_data_filtered}")
    console.print(f"- price 탈락: {fr.price_filtered}")
    console.print(f"- change 탈락: {fr.change_filtered}")
    console.print(f"- gap 탈락: {fr.gap_filtered}")
    console.print(f"- intraday 탈락: {fr.intraday_filtered}")
    console.print(f"- volume_ratio 탈락: {fr.volume_ratio_filtered}")
    console.print(f"- average_volume 탈락: {fr.average_volume_filtered}")
    console.print(f"- dollar_volume 탈락: {fr.dollar_volume_filtered}")
    console.print(f"- 최종 필터 통과: {fr.passed_filters}")
    console.print(f"- 점수화 완료: {fr.scored_count}")
    console.print(f"- 최종 출력: {fr.returned_count}")

    if args.debug_filters and result.per_symbol_filter_results:
        console.print("Per-symbol filter results:")
        for entry in result.per_symbol_filter_results:
            console.print(_format_debug_line(entry))

    if args.debug_filter_json and result.per_symbol_filter_results is not None:
        out_dir = cfg.reports_dir / "filter_debug"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"filter_debug_{ts}.json"
        eff = result.effective_filters_snapshot
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_profile": profile.name,
            "effective_filters": (
                {
                    "price_min": eff.min_price,
                    "price_max": eff.max_price,
                    "change_min": eff.min_change_percent,
                    "gap_min": eff.min_gap_percent,
                    "intraday_min": eff.min_intraday_change_percent,
                    "volume_ratio_min": eff.min_volume_ratio,
                    "avg_volume_min": eff.min_average_volume,
                    "dollar_volume_min": eff.min_dollar_volume,
                }
                if eff
                else {}
            ),
            "results": [
                {
                    "symbol": e["symbol"],
                    "status": e["status"],
                    "details": e.get("details") or {},
                }
                for e in result.per_symbol_filter_results
            ],
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"Filter debug JSON saved: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

