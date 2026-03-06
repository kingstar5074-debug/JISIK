from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional

from scanner.models import QuoteSnapshot, MarketSession


@dataclass(frozen=True)
class StockScore:
    symbol: str
    momentum_score: float
    volume_score: float
    gap_score: float
    liquidity_score: float
    total_score: float


def _session_weights(session: MarketSession) -> Tuple[float, float, float]:
    """
    Return (momentum_weight, volume_weight, gap_weight) for given session.
    """

    if session == "premarket":
        return 0.35, 0.25, 0.40
    if session == "regular":
        return 0.45, 0.35, 0.20
    if session == "afterhours":
        return 0.35, 0.40, 0.25
    # closed 또는 기타: regular와 동일
    return 0.45, 0.35, 0.20


def score_quote(q: QuoteSnapshot) -> Optional[StockScore]:
    """
    Compute session-aware score for a quote.

    - momentum_score = percent_change
    - volume_score   = volume_ratio * 10
    - gap_score      = gap_percent
    - liquidity_score = min(dollar_volume / 1_000_000, 10)

    total_score =
      momentum_score * momentum_weight
      + volume_score * volume_weight
      + gap_score * gap_weight
      + liquidity_score * 0.15
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

    m_w, v_w, g_w = _session_weights(q.market_session)
    total = (
        momentum_score * m_w
        + volume_score * v_w
        + gap_score * g_w
        + liquidity_score * 0.15
    )

    return StockScore(
        symbol=q.symbol,
        momentum_score=momentum_score,
        volume_score=volume_score,
        gap_score=gap_score,
        liquidity_score=liquidity_score,
        total_score=total,
    )

