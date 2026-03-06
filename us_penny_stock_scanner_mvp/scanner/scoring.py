from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from scanner.models import QuoteSnapshot, MarketSession
from scanner.strategy_profiles import StrategyWeights


@dataclass(frozen=True)
class StockScore:
    symbol: str
    momentum_score: float
    volume_score: float
    gap_score: float
    liquidity_score: float
    total_score: float


def score_quote(
    q: QuoteSnapshot,
    weights: StrategyWeights,
) -> Optional[StockScore]:
    """
    세션/전략별 가중치를 받아 점수를 계산한다.

    - momentum_score = percent_change
    - volume_score   = volume_ratio * 10
    - gap_score      = gap_percent
    - liquidity_score = min(dollar_volume / 1_000_000, 10)

    total_score =
      momentum_score * weights.momentum_weight
      + volume_score * weights.volume_weight
      + gap_score * weights.gap_weight
      + liquidity_score * weights.liquidity_weight
    """

    if not q.symbol:
        return None

    momentum = q.percent_change or 0.0
    volume_ratio = q.volume_ratio or 0.0
    gap = q.gap_percent or 0.0
    dollar_volume = q.dollar_volume or 0.0

    momentum_score = momentum
    volume_score = volume_ratio * 10.0
    gap_score = gap
    liquidity_score = min(dollar_volume / 1_000_000.0, 10.0)

    total = (
        momentum_score * weights.momentum_weight
        + volume_score * weights.volume_weight
        + gap_score * weights.gap_weight
        + liquidity_score * weights.liquidity_weight
    )

    return StockScore(
        symbol=q.symbol,
        momentum_score=momentum_score,
        volume_score=volume_score,
        gap_score=gap_score,
        liquidity_score=liquidity_score,
        total_score=total,
    )

