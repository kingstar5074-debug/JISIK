from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

import yfinance as yf

from utils.logger import get_logger
from scanner.models import MarketSession, QuoteSnapshot
from scanner.providers.base import MarketDataProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class YahooProviderConfig:
    per_symbol_delay_seconds: float = 0.2
    timeout_seconds: int = 15


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

        for sym in symbols:
            symbol = sym.strip().upper()
            if not symbol:
                continue

            try:
                out[symbol] = self._fetch_one(symbol, market_session)
            except Exception as e:
                log.exception("YahooProvider failed for %s: %s", symbol, e)
            finally:
                if self.cfg.per_symbol_delay_seconds > 0:
                    time.sleep(self.cfg.per_symbol_delay_seconds)

        return out

    def _fetch_one(self, symbol: str, market_session: MarketSession) -> QuoteSnapshot:
        t = yf.Ticker(symbol)

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

        prev_close = (
            _to_float(info.get("regularMarketPreviousClose"))
            or _to_float(fast.get("previous_close"))
            or _to_float(info.get("previousClose"))
        )

        regular_price = (
            _to_float(info.get("regularMarketPrice"))
            or _to_float(fast.get("last_price"))
            or _to_float(info.get("currentPrice"))
        )

        today_open = (
            _to_float(info.get("regularMarketOpen"))
            or _to_float(fast.get("open"))
            or _to_float(info.get("open"))
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
        if current_price is not None and prev_close not in (None, 0.0):
            percent_change = ((current_price - prev_close) / prev_close) * 100.0

        gap_percent: Optional[float] = None
        if today_open is not None and prev_close not in (None, 0.0):
            gap_percent = ((today_open - prev_close) / prev_close) * 100.0

        intraday_change_percent: Optional[float] = None
        if current_price is not None and today_open not in (None, 0.0):
            intraday_change_percent = ((current_price - today_open) / today_open) * 100.0

        volume_ratio: Optional[float] = None
        if current_volume is not None and average_volume not in (None, 0.0):
            volume_ratio = current_volume / average_volume

        dollar_volume: Optional[float] = None
        if current_price is not None and current_volume not in (None, 0.0):
            dollar_volume = current_price * current_volume

        return QuoteSnapshot(
            symbol=symbol,
            current_price=current_price,
            percent_change=percent_change,
            gap_percent=gap_percent,
            intraday_change_percent=intraday_change_percent,
            current_volume=current_volume,
            average_volume=average_volume,
            volume_ratio=volume_ratio,
            prev_close=prev_close,
            today_open=today_open,
            dollar_volume=dollar_volume,
            market_session=market_session,
        )

