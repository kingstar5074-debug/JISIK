from __future__ import annotations

from pathlib import Path

from rich.console import Console

from config import load_config
from scanner.market_hours import MarketClock
from scanner.providers.yahoo_provider import YahooFinanceProvider, YahooProviderConfig
from scanner.scanner import PennyStockScanner
from utils.formatter import render_console_tables
from utils.logger import get_logger

log = get_logger(__name__)


def read_tickers(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"tickers.txt not found: {path}")

    symbols: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip().upper()
        if not s:
            continue
        if s.startswith("#"):
            continue
        symbols.append(s)
    return symbols


def main() -> int:
    cfg = load_config()
    console = Console()

    tickers = read_tickers(cfg.tickers_file)
    if not tickers:
        console.print("tickers.txt에 티커가 없습니다.")
        return 1

    clock = MarketClock()
    session = clock.current_session()
    console.print(f"현재 시장 세션(ET): {session}")

    provider = YahooFinanceProvider(
        YahooProviderConfig(per_symbol_delay_seconds=cfg.per_symbol_delay_seconds)
    )
    scanner = PennyStockScanner(provider=provider, filters=cfg.filters, clock=clock)

    result = scanner.scan(tickers)

    render_console_tables(result.matched, console=console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

