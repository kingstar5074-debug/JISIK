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
    - 'polygon' : use PolygonProvider (requires POLYGON_API_KEY)
    """

    provider_name = (getattr(cfg, "data_provider", "yahoo") or "yahoo").strip().lower()

    if provider_name == "polygon":
        api_key = getattr(cfg, "polygon_api_key", "") or ""
        if not api_key:
            raise RuntimeError(
                "DATA_PROVIDER=polygon 이지만 POLYGON_API_KEY 가 설정되어 있지 않습니다. "
                ".env 에 유효한 키를 설정하거나 DATA_PROVIDER=yahoo 로 변경해 주세요."
            )

        cfg_obj = PolygonProviderConfig(api_key=api_key)
        log.info("Using PolygonProvider for market data.")
        return PolygonProvider(cfg_obj)

    if provider_name == "yahoo":
        log.info("Using YahooFinanceProvider for market data.")
        return YahooFinanceProvider(
            YahooProviderConfig(per_symbol_delay_seconds=getattr(cfg, "per_symbol_delay_seconds", 0.2))
        )

    raise ValueError(f"지원하지 않는 DATA_PROVIDER 값입니다: '{provider_name}'. (지원: yahoo, polygon)")


