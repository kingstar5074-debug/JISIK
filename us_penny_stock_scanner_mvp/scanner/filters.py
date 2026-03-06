from __future__ import annotations

from dataclasses import dataclass

from .models import QuoteSnapshot


@dataclass(frozen=True)
class ScanFilters:
    min_price: float = 0.05
    max_price: float = 1.00
    min_change_percent: float = 15.0
    min_volume_ratio: float = 3.0


def passes_filters(q: QuoteSnapshot, f: ScanFilters) -> bool:
    if q.current_price is None or q.percent_change is None or q.volume_ratio is None:
        return False

    if not (f.min_price <= q.current_price <= f.max_price):
        return False

    if q.percent_change < f.min_change_percent:
        return False

    if q.volume_ratio < f.min_volume_ratio:
        return False

    return True

