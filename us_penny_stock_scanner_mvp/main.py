from __future__ import annotations

from rich.console import Console

from config import load_config
from scanner.market_hours import MarketClock
from scanner.providers.factory import get_market_data_provider
from scanner.scanner import PennyStockScanner
from universe.generated_universe import GeneratedUniverseProvider
from universe.watchlist_universe import WatchlistUniverseProvider
from utils.formatter import render_console_tables
from utils.logger import get_logger

log = get_logger(__name__)


def main() -> int:
    cfg = load_config()
    console = Console()

    if cfg.scan_mode not in {"watchlist", "universe"}:
        console.print(
            f"지원하지 않는 SCAN_MODE 값입니다: '{cfg.scan_mode}'. "
            "watchlist 또는 universe 중 하나여야 합니다."
        )
        return 1

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
    console.print(f"현재 시장 세션(ET): {session}")
    console.print(f"현재 스캔 모드: {cfg.scan_mode}")
    console.print(f"현재 데이터 provider: {cfg.data_provider}")
    console.print(f"로드한 티커 수: {len(tickers)}")
    console.print(
        f"필터: price {cfg.filters.min_price}~{cfg.filters.max_price} / "
        f"change >= {cfg.filters.min_change_percent} / "
        f"volume_ratio >= {cfg.filters.min_volume_ratio}"
    )

    try:
        provider = get_market_data_provider(cfg)
    except RuntimeError as e:
        console.print(str(e))
        return 1

    scanner = PennyStockScanner(provider=provider, filters=cfg.filters, clock=clock)

    result = scanner.scan(tickers)

    render_console_tables(result.matched, console=console)

    console.print(f"조회 성공: {result.fetch_success}")
    console.print(f"조회 실패: {result.fetch_failed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

