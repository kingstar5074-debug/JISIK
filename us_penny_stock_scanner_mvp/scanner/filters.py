from __future__ import annotations

from dataclasses import dataclass

from scanner.models import QuoteSnapshot


@dataclass(frozen=True)
class ScanFilters:
    min_price: float = 0.05
    max_price: float = 1.00
    min_change_percent: float = 15.0
    min_volume_ratio: float = 3.0
    min_gap_percent: float = 5.0
    min_intraday_change_percent: float = 10.0
    min_dollar_volume: float = 500_000.0
    min_average_volume: float = 100_000.0


def passes_filters(q: QuoteSnapshot, f: ScanFilters) -> bool:
    """
    Return True if quote passes all price/momentum/gap/volume/liquidity filters.
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
        return False

    if not (f.min_price <= q.current_price <= f.max_price):
        return False

    if q.percent_change < f.min_change_percent:
        return False

    if q.volume_ratio < f.min_volume_ratio:
        return False

    if q.gap_percent < f.min_gap_percent:
        return False

    if q.intraday_change_percent < f.min_intraday_change_percent:
        return False

    if q.average_volume < f.min_average_volume:
        return False

    if q.dollar_volume < f.min_dollar_volume:
        return False

    return True

