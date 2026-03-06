from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


MarketSession = Literal["premarket", "regular", "afterhours", "closed"]


@dataclass(frozen=True)
class QuoteSnapshot:
    """
    Provider-agnostic quote snapshot used by the scanner.

    - Providers는 가능한 한 모든 필드를 채우되, 값이 없으면 None 을 넣는다.
    - 필터 단계에서 None 인 값은 자동으로 탈락 처리된다.
    """

    symbol: str
    current_price: Optional[float]
    percent_change: Optional[float]
    gap_percent: Optional[float]
    intraday_change_percent: Optional[float]
    current_volume: Optional[float]
    average_volume: Optional[float]
    volume_ratio: Optional[float]
    prev_close: Optional[float]
    today_open: Optional[float]
    dollar_volume: Optional[float]
    market_session: MarketSession

