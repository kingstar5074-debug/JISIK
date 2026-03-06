from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MarketSession = Literal["premarket", "regular", "afterhours", "closed"]


@dataclass(frozen=True)
class QuoteSnapshot:
    """
    Minimal quote snapshot used by the scanner.

    Notes:
    - Provider-agnostic 구조를 유지해 Polygon / Yahoo 등 어떤 provider든
      이 모델만 맞춰주면 스캐너가 동작하도록 설계한다.
    - 일부 필드는 provider가 값을 줄 수 없으면 None 일 수 있다.
    """

    symbol: str
    current_price: Optional[float]
    percent_change: Optional[float]
    gap_percent: Optional[float]
    intraday_change_percent: Optional[float]
    current_volume: Optional[float]
    average_volume: Optional[float]
    volume_ratio: Optional[float]
    market_session: MarketSession

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MarketSession = Literal["premarket", "regular", "afterhours", "closed"]


@dataclass(frozen=True)
class QuoteSnapshot:
    """
    Minimal quote snapshot needed for the MVP.

    Notes:
    - We intentionally keep the model provider-agnostic so we can swap data providers later.
    - Some fields can be None if the provider does not supply them; the scanner skips invalid rows.
    """

    symbol: str
    current_price: Optional[float]
    percent_change: Optional[float]
    current_volume: Optional[float]
    average_volume: Optional[float]
    volume_ratio: Optional[float]
    market_session: MarketSession

