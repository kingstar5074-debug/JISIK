from __future__ import annotations

"""
Trade Outcome Tracker.

이 스크립트는 두 가지 모드를 제공하여,

1) 현재 스캔 결과를 CSV 스냅샷으로 저장하고
2) 일정 시간(delay) 후 같은 종목의 실제 가격을 다시 조회해 단순 수익률(PnL)을 계산합니다.

저장 위치:
- reports/trade_outcomes/scan_snapshots.csv
- reports/trade_outcomes/trade_results.csv

이 도구는 주문/자동매매와는 무관하며,
순수히 "점수 기반 스캔 결과가 이후 실제 가격에서 어떻게 움직였는지"를 분석하기 위한 용도입니다.
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from rich.console import Console

from config import load_config
from scanner.market_hours import MarketClock
from scanner.providers.factory import get_market_data_provider
from scanner.scanner import PennyStockScanner
from scanner.strategy_profiles import get_strategy_profile
from universe.generated_universe import GeneratedUniverseProvider
from universe.watchlist_universe import WatchlistUniverseProvider
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class _ProviderConfigWrapper:
    """
    get_market_data_provider 에 넘기기 위한 최소 구성 래퍼.
    """

    data_provider: str
    polygon_api_key: str | None
    per_symbol_delay_seconds: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trade Outcome Tracker")
    parser.add_argument(
        "--save-scan",
        action="store_true",
        help="현재 스캔 결과를 scan_snapshots.csv 에 저장",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="이전에 저장된 스냅샷을 기반으로 실제 수익률을 계산",
    )
    parser.add_argument(
        "--delay-minutes",
        type=int,
        default=30,
        help="evaluate 모드에서 최소 경과 시간(분) (기본: 30)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="",
        help="데이터 provider 강제 지정 (yahoo / polygon). 미지정 시 .env 설정 사용",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="",
        help="evaluate 모드에서 snapshot 의 session 컬럼 필터 (예: premarket, regular)",
    )
    return parser.parse_args()


def _get_reports_dir() -> Path:
    project_root = Path(__file__).resolve().parent
    base = project_root / "reports" / "trade_outcomes"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ensure_csv_header(path: Path, headers: List[str]) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        return

    # 파일이 존재하지만 비어있는 경우에도 헤더를 보장
    try:
        with path.open("r", encoding="utf-8") as f:
            first = f.readline()
    except Exception:
        first = ""

    if not first:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)


def _build_provider(cfg, override_name: str | None) -> Any:
    """
    .env 설정(cfg)와 CLI override(provider) 를 조합해 실제 provider 인스턴스를 생성.
    """

    provider_name = (override_name or cfg.data_provider or "yahoo").strip().lower()
    wrapper = _ProviderConfigWrapper(
        data_provider=provider_name,
        polygon_api_key=cfg.polygon_api_key,
        per_symbol_delay_seconds=cfg.per_symbol_delay_seconds,
    )
    return get_market_data_provider(wrapper)


def _load_universe_symbols(cfg, console: Console) -> List[str]:
    if cfg.scan_mode not in {"watchlist", "universe"}:
        console.print(
            f"지원하지 않는 SCAN_MODE 값입니다: '{cfg.scan_mode}'. "
            "watchlist 또는 universe 중 하나여야 합니다."
        )
        return []

    if cfg.scan_mode == "universe":
        universe = GeneratedUniverseProvider(cfg.universe_file)
    else:
        universe = WatchlistUniverseProvider(cfg.tickers_file)

    try:
        symbols = universe.load_symbols()
    except FileNotFoundError as e:
        console.print(str(e))
        return []

    if not symbols:
        console.print("스캔할 티커가 없습니다.")
        return []

    return symbols


def _run_save_scan(args: argparse.Namespace, console: Console) -> int:
    cfg = load_config()

    symbols = _load_universe_symbols(cfg, console)
    if not symbols:
        return 0

    try:
        provider = _build_provider(cfg, args.provider or None)
    except (RuntimeError, ValueError) as e:
        console.print(str(e))
        return 0

    try:
        profile = get_strategy_profile(cfg.strategy_profile, cfg.strategy_profiles_file)
    except ValueError as e:
        console.print(str(e))
        return 0

    clock = MarketClock()
    session = clock.current_session()

    scanner = PennyStockScanner(
        provider=provider,
        filters=cfg.filters,
        strategy_profile=profile,
        clock=clock,
        top_results=cfg.top_results,
    )

    console.print("스캔 실행 중 (snapshot 저장 모드)...")
    result = scanner.scan(symbols)

    reports_dir = _get_reports_dir()
    snapshot_path = reports_dir / "scan_snapshots.csv"
    headers = [
        "timestamp",
        "symbol",
        "price",
        "strategy",
        "theme",
        "provider",
        "session",
    ]
    _ensure_csv_header(snapshot_path, headers)

    now_iso = datetime.now().isoformat(timespec="seconds")
    provider_name = (args.provider or cfg.data_provider or "yahoo").strip().lower()

    written = 0
    with snapshot_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for q in result.matched:
            if q.current_price is None:
                continue
            symbol = q.symbol
            themes = (result.theme_tags or {}).get(symbol) or []
            theme = themes[0] if themes else "unknown"
            writer.writerow(
                [
                    now_iso,
                    symbol,
                    f"{q.current_price:.6f}",
                    profile.name,
                    theme,
                    provider_name,
                    result.current_session or session,
                ]
            )
            written += 1

    console.print(f"scan_snapshots.csv 에 저장된 종목 수: {written}")
    return 0


def _run_evaluate(args: argparse.Namespace, console: Console) -> int:
    reports_dir = _get_reports_dir()
    snapshot_path = reports_dir / "scan_snapshots.csv"
    results_path = reports_dir / "trade_results.csv"

    # 스냅샷 파일이 없으면 조용히 종료
    if not snapshot_path.exists():
        console.print("scan_snapshots.csv 파일이 없어 평가할 스냅샷이 없습니다.")
        return 0

    _ensure_csv_header(
        results_path,
        [
            "timestamp_entry",
            "timestamp_exit",
            "symbol",
            "strategy",
            "theme",
            "provider",
            "session",
            "entry_price",
            "exit_price",
            "return_pct",
        ],
    )

    cfg = load_config()
    try:
        provider = _build_provider(cfg, args.provider or None)
    except (RuntimeError, ValueError) as e:
        console.print(str(e))
        return 0

    clock = MarketClock()
    current_session = clock.current_session()

    delay = max(int(args.delay_minutes), 0)
    now = datetime.now()
    threshold = now - timedelta(minutes=delay)

    provider_filter = (args.provider or "").strip().lower()
    session_filter = (args.session or "").strip().lower()

    # 스냅샷 로드
    try:
        with snapshot_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
    except Exception as e:
        console.print(f"scan_snapshots.csv 읽기 실패: {e}")
        return 0

    if not rows:
        console.print("scan_snapshots.csv 가 비어 있습니다.")
        return 0

    remaining_rows: List[Dict[str, Any]] = []
    processed_count = 0
    skipped_symbols = 0

    with results_path.open("a", newline="", encoding="utf-8") as rf:
        writer = csv.writer(rf)

        for row in rows:
            try:
                ts_str = row.get("timestamp", "")
                symbol = (row.get("symbol") or "").strip().upper()
                entry_price_str = row.get("price", "")
                strategy = row.get("strategy") or ""
                theme = row.get("theme") or ""
                row_provider = (row.get("provider") or "").strip().lower()
                row_session = (row.get("session") or "").strip().lower()
            except Exception:
                skipped_symbols += 1
                continue

            if not ts_str or not symbol or not entry_price_str:
                # 필수 컬럼이 없으면 그대로 남겨두지 않고 스킵만
                skipped_symbols += 1
                continue

            # provider / session 필터 적용 (해당하지 않는 스냅샷은 남겨둔다)
            if provider_filter and row_provider and row_provider != provider_filter:
                remaining_rows.append(row)
                continue
            if provider_filter and not row_provider:
                remaining_rows.append(row)
                continue

            if session_filter and row_session and row_session != session_filter:
                remaining_rows.append(row)
                continue
            if session_filter and not row_session:
                remaining_rows.append(row)
                continue

            # delay-minutes 보다 오래된 것만 평가 대상
            try:
                ts_entry = datetime.fromisoformat(ts_str)
            except Exception:
                skipped_symbols += 1
                continue

            if ts_entry > threshold:
                # 아직 충분히 시간이 지나지 않은 스냅샷은 남겨둔다
                remaining_rows.append(row)
                continue

            try:
                entry_price = float(entry_price_str)
            except Exception:
                skipped_symbols += 1
                continue

            # 현재 세션 기준 최신 가격 조회
            try:
                quotes = provider.fetch_quotes([symbol], market_session=current_session)
            except Exception as e:
                log.exception("가격 조회 실패(%s): %s", symbol, e)
                skipped_symbols += 1
                # 재평가 기회를 위해 스냅샷은 남겨둔다
                remaining_rows.append(row)
                continue

            q = quotes.get(symbol)
            if q is None or q.current_price is None:
                skipped_symbols += 1
                # 나중에 다시 평가할 수 있도록 스냅샷 유지
                remaining_rows.append(row)
                continue

            exit_price = float(q.current_price)
            if entry_price <= 0.0:
                skipped_symbols += 1
                continue

            return_pct = ((exit_price - entry_price) / entry_price) * 100.0

            writer.writerow(
                [
                    ts_str,
                    now.isoformat(timespec="seconds"),
                    symbol,
                    strategy,
                    theme,
                    row_provider,
                    row_session,
                    f"{entry_price:.6f}",
                    f"{exit_price:.6f}",
                    f"{return_pct:.2f}",
                ]
            )
            processed_count += 1

    # 처리된 스냅샷 제거 (remaining_rows 만 다시 저장)
    try:
        with snapshot_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if fieldnames:
                writer.writerow(fieldnames)
            for r in remaining_rows:
                writer.writerow([r.get(h, "") for h in fieldnames])
    except Exception as e:
        console.print(f"scan_snapshots.csv 갱신 실패: {e}")

    console.print(f"Processed trades: {processed_count}")
    console.print(f"Skipped symbols: {skipped_symbols}")
    console.print(f"Remaining snapshots: {len(remaining_rows)}")

    return 0


def main() -> int:
    console = Console()
    args = _parse_args()

    if not args.save_scan and not args.evaluate:
        console.print(
            "하나 이상의 모드를 지정해야 합니다. "
            "--save-scan 또는 --evaluate 중 하나를 사용하세요."
        )
        return 0

    if args.save_scan and args.evaluate:
        console.print("한 번에 하나의 모드만 실행할 수 있습니다. (--save-scan 또는 --evaluate)")
        return 0

    if args.save_scan:
        return _run_save_scan(args, console)

    if args.evaluate:
        return _run_evaluate(args, console)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

