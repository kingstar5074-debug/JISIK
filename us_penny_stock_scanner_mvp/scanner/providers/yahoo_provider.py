from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

import yfinance as yf

from ...utils.logger import get_logger
from ..models import MarketSession, QuoteSnapshot
from .base import MarketDataProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class YahooProviderConfig:
    """
    Yahoo Finance (via yfinance) configuration.

    Notes:
    - This is a free source and may be rate-limited or temporarily unavailable.
    - We keep a small delay option to be polite and reduce 429/blocks.
    """

    per_symbol_delay_seconds: float = 0.2
    timeout_seconds: int = 15  # yfinance does not expose per-call timeout consistently


def _to_float(v: object) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


class YahooFinanceProvider(MarketDataProvider):
    def __init__(self, cfg: YahooProviderConfig | None = None) -> None:
        self.cfg = cfg or YahooProviderConfig()

    def fetch_quotes(
        self,
        symbols: Iterable[str],
        market_session: MarketSession,
    ) -> Mapping[str, QuoteSnapshot]:
        out: Dict[str, QuoteSnapshot] = {}

        # Keep it simple for MVP: per-symbol fetch with robust error handling.
        # For larger symbol lists we can upgrade to batching later.
        for sym in symbols:
            sym = sym.strip().upper()
            if not sym:
                continue

            try:
                out[sym] = self._fetch_one(sym, market_session)
            except Exception as e:
                log.exception("YahooProvider failed for %s: %s", sym, e)
            finally:
                if self.cfg.per_symbol_delay_seconds > 0:
                    time.sleep(self.cfg.per_symbol_delay_seconds)

        return out

    def _fetch_one(self, symbol: str, market_session: MarketSession) -> QuoteSnapshot:
        t = yf.Ticker(symbol)

        # yfinance can provide:
        # - extended hours prices in `info` (preMarketPrice/postMarketPrice) for some tickers
        # - regular market fields (regularMarketPrice, regularMarketPreviousClose, regularMarketVolume, averageVolume)
        # - `fast_info` for faster access when available
        info: dict = {}
        fast: dict = {}
        try:
            fast = dict(getattr(t, "fast_info", {}) or {})
        except Exception:
            fast = {}

        try:
            info = dict(getattr(t, "info", {}) or {})
        except Exception:
            info = {}

        previous_close = (
            _to_float(info.get("regularMarketPreviousClose"))
            or _to_float(fast.get("previous_close"))
            or _to_float(info.get("previousClose"))
        )

        regular_price = (
            _to_float(info.get("regularMarketPrice"))
            or _to_float(fast.get("last_price"))
            or _to_float(info.get("currentPrice"))
        )

        pre_price = _to_float(info.get("preMarketPrice"))
        post_price = _to_float(info.get("postMarketPrice"))

        if market_session == "premarket":
            current_price = pre_price or regular_price
        elif market_session == "afterhours":
            current_price = post_price or regular_price
        else:
            current_price = regular_price

        current_volume = (
            _to_float(info.get("regularMarketVolume"))
            or _to_float(fast.get("last_volume"))
            or _to_float(info.get("volume"))
        )

        average_volume = (
            _to_float(info.get("averageVolume"))
            or _to_float(fast.get("three_month_average_volume"))
            or _to_float(fast.get("ten_day_average_volume"))
        )

        percent_change: Optional[float] = None
        if current_price is not None and previous_close not in (None, 0.0):
            percent_change = ((current_price - previous_close) / previous_close) * 100.0

        volume_ratio: Optional[float] = None
        if current_volume is not None and average_volume not in (None, 0.0):
            volume_ratio = current_volume / average_volume

        return QuoteSnapshot(
            symbol=symbol,
            current_price=current_price,
            percent_change=percent_change,
            current_volume=current_volume,
            average_volume=average_volume,
            volume_ratio=volume_ratio,
            market_session=market_session,
        )

