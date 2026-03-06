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

