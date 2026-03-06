from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.table import Table

from scanner.models import QuoteSnapshot
from scanner.scoring import StockScore


def render_console_tables(
    items: List[QuoteSnapshot],
    scores: Optional[List[StockScore]] = None,
    console: Console | None = None,
) -> None:
    console = console or Console()

    if not items:
        console.print("조건 충족 종목 없음")
        return

    by_symbol = {s.symbol: s for s in (scores or [])}

    table = Table(title="Penny Stock Scanner Results", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("ticker", justify="left")
    table.add_column("session", justify="left")
    table.add_column("price", justify="right")
    table.add_column("change%", justify="right")
    table.add_column("gap%", justify="right")
    table.add_column("intraday%", justify="right")
    table.add_column("vol_ratio", justify="right")
    table.add_column("score", justify="right")

    for idx, q in enumerate(items, start=1):
        s = by_symbol.get(q.symbol)

        price = "-" if q.current_price is None else f"{q.current_price:.4f}".rstrip("0").rstrip(".")
        change = "-" if q.percent_change is None else f"{q.percent_change:+.1f}%"
        gap = "-" if q.gap_percent is None else f"{q.gap_percent:+.1f}%"
        intraday = "-" if q.intraday_change_percent is None else f"{q.intraday_change_percent:+.1f}%"
        vr = "-" if q.volume_ratio is None else f"{q.volume_ratio:.2f}x"
        score_str = "-" if s is None else f"{s.total_score:.2f}"

        table.add_row(
            str(idx),
            q.symbol,
            q.market_session,
            price,
            change,
            gap,
            intraday,
            vr,
            score_str,
        )

    console.print(table)

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Mapping

from rich.console import Console
from rich.table import Table

from scanner.models import MarketSession, QuoteSnapshot


def group_by_session(items: Iterable[QuoteSnapshot]) -> Mapping[MarketSession, List[QuoteSnapshot]]:
    grouped: dict[MarketSession, list[QuoteSnapshot]] = defaultdict(list)
    for q in items:
        grouped[q.market_session].append(q)
    return grouped


def render_console_tables(
    items: List[QuoteSnapshot],
    console: Console | None = None,
) -> None:
    console = console or Console()

    if not items:
        console.print("조건 충족 종목 없음")
        return

    grouped = group_by_session(items)
    order: list[MarketSession] = ["premarket", "regular", "afterhours", "closed"]

    for session in order:
        rows = grouped.get(session, [])
        if not rows:
            continue

        title = f"[{session.upper()}]"
        table = Table(title=title, show_lines=False)
        table.add_column("#", justify="right")
        table.add_column("ticker", justify="left")
        table.add_column("price", justify="right")
        table.add_column("change", justify="right")
        table.add_column("volume_ratio", justify="right")

        for i, q in enumerate(rows, start=1):
            price = "-" if q.current_price is None else f"{q.current_price:.4f}".rstrip("0").rstrip(".")
            change = "-" if q.percent_change is None else f"{q.percent_change:+.1f}%"
            vr = "-" if q.volume_ratio is None else f"{q.volume_ratio:.2f}x"
            table.add_row(str(i), q.symbol, price, change, vr)

        console.print(table)

