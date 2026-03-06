from __future__ import annotations

from typing import Any

from scanner.providers.base import MarketDataProvider
from scanner.providers.polygon_provider import PolygonProvider, PolygonProviderConfig
from scanner.providers.yahoo_provider import YahooFinanceProvider, YahooProviderConfig
from utils.logger import get_logger

log = get_logger(__name__)


def get_market_data_provider(cfg: Any) -> MarketDataProvider:
    """
    Select an appropriate MarketDataProvider based on configuration.

    DATA_PROVIDER options (via cfg.data_provider):
    - 'yahoo'   : use YahooFinanceProvider (default)
    - 'polygon' : structure prepared, but NOT implemented in this batch
    """

    provider_name = (getattr(cfg, "data_provider", "yahoo") or "yahoo").strip().lower()

    if provider_name == "polygon":
        api_key = getattr(cfg, "polygon_api_key", "") or ""
        if not api_key:
            raise RuntimeError(
                "DATA_PROVIDER=polygon 이지만 POLYGON_API_KEY 가 설정되어 있지 않습니다. "
                "현재 배치에서는 구조만 준비되어 있으므로 DATA_PROVIDER=yahoo 로 사용해 주세요."
            )

        raise RuntimeError(
            "Polygon provider는 현재 설계/코드틀만 존재하며 실제 API 호출은 아직 구현되지 않았습니다. "
            "DATA_PROVIDER=yahoo 로 되돌려 사용해 주세요."
        )

    # Default: yahoo
    return YahooFinanceProvider(
        YahooProviderConfig(per_symbol_delay_seconds=getattr(cfg, "per_symbol_delay_seconds", 0.2))
    )

