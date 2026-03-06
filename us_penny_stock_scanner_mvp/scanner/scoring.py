from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from scanner.models import QuoteSnapshot


@dataclass(frozen=True)
class StockScore:
    symbol: str
    momentum_score: float
    volume_score: float
    gap_score: float
    total_score: float


def score_quote(q: QuoteSnapshot) -> Optional[StockScore]:
    """
    Compute simple momentum/volume/gap-based score for a quote.

    현재 버전:
    - momentum_score = percent_change
    - volume_score   = volume_ratio * 10
    - gap_score      = gap_percent
    - total_score    = 0.5 * momentum + 0.3 * volume + 0.2 * gap
    """

    if q.symbol is None:
        return None

    momentum = q.percent_change or 0.0
    volume_ratio = q.volume_ratio or 0.0
    gap = q.gap_percent or 0.0

    volume_score = volume_ratio * 10.0
    momentum_score = momentum
    gap_score = gap

    total = momentum_score * 0.5 + volume_score * 0.3 + gap_score * 0.2

    return StockScore(
        symbol=q.symbol,
        momentum_score=momentum_score,
        volume_score=volume_score,
        gap_score=gap_score,
        total_score=total,
    )

