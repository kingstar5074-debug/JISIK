from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Dict, Iterable, Mapping, Optional

import requests

from scanner.models import MarketSession, QuoteSnapshot
from scanner.providers.base import MarketDataProvider
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class PolygonProviderConfig:
    api_key: str
    base_url: str = "https://api.polygon.io"
    timeout_seconds: float = 10.0
    per_symbol_delay_seconds: float = 0.0
    average_volume_window: int = 20


def _to_float(v: object) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


class PolygonProvider(MarketDataProvider):
    """
    Polygon 기반 MarketDataProvider 구현.

    - Snapshot endpoint:
      /v2/snapshot/locale/us/markets/stocks/tickers/{symbol}
    - Aggregates endpoint (average volume):
      /v2/aggs/ticker/{symbol}/range/1/day/{from}/{to}
    """

    def __init__(self, cfg: PolygonProviderConfig) -> None:
        if not cfg.api_key:
            raise ValueError("PolygonProvider requires a non-empty api_key")
        self.cfg = cfg
        self._session = requests.Session()

    def _get(self, path: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}
        final_params = dict(params)
        final_params["apiKey"] = self.cfg.api_key

        url = f"{self.cfg.base_url.rstrip('/')}{path}"
        resp = self._session.get(url, params=final_params, timeout=self.cfg.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            status = data.get("status")
            if status and status not in ("OK", "success"):
                message = data.get("error") or data.get("message") or str(data)
                raise RuntimeError(f"Polygon API error status={status}: {message}")

        return data

    def _fetch_snapshot_raw(self, symbol: str) -> dict:
        return self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}")

    def _fetch_average_volume(self, symbol: str) -> Optional[float]:
        """
        최근 average_volume_window 거래일 기준 평균 거래량 계산.
        """
        from datetime import datetime, timedelta, timezone

        utc_now = datetime.now(timezone.utc)
        days = max(self.cfg.average_volume_window, 1)
        start = utc_now - timedelta(days=days * 2)
        from_str = start.strftime("%Y-%m-%d")
        to_str = utc_now.strftime("%Y-%m-%d")

        try:
            data = self._get(
                f"/v2/aggs/ticker/{symbol}/range/1/day/{from_str}/{to_str}",
                params={"adjusted": "true", "sort": "desc", "limit": days},
            )
        except Exception as e:
            log.warning("Polygon aggregates fetch failed for %s: %s", symbol, e)
            return None

        results = data.get("results") or []
        if not results:
            return None

        vols = [_to_float(r.get("v")) for r in results]
        vols = [v for v in vols if v not in (None, 0.0)]
        if not vols:
            return None

        return sum(vols) / float(len(vols))

    def _build_quote_snapshot(
        self,
        symbol: str,
        data: dict,
        avg_volume: Optional[float],
        market_session: MarketSession,
    ) -> QuoteSnapshot:
        ticker = data.get("ticker") or {}
        last_trade = ticker.get("lastTrade") or {}
        day = ticker.get("day") or {}
        prev_day = ticker.get("prevDay") or {}

        current_price = _to_float(last_trade.get("p")) or _to_float(day.get("c"))
        current_volume = _to_float(day.get("v"))

        today_open = _to_float(day.get("o"))
        prev_close = _to_float(prev_day.get("c"))

        percent_change: Optional[float] = None
        if current_price is not None and prev_close not in (None, 0.0):
            percent_change = ((current_price - prev_close) / prev_close) * 100.0

        gap_percent: Optional[float] = None
        if today_open is not None and prev_close not in (None, 0.0):
            gap_percent = ((today_open - prev_close) / prev_close) * 100.0

        intraday_change_percent: Optional[float] = None
        if current_price is not None and today_open not in (None, 0.0):
            intraday_change_percent = ((current_price - today_open) / today_open) * 100.0

        average_volume: Optional[float] = avg_volume
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
                snapshot = self._fetch_snapshot_raw(symbol)
                avg_vol = self._fetch_average_volume(symbol)
                quote = self._build_quote_snapshot(symbol, snapshot, avg_vol, market_session)
                out[symbol] = quote
            except requests.RequestException as e:
                log.warning("Polygon HTTP error for %s: %s", symbol, e)
            except Exception as e:
                log.exception("PolygonProvider failed for %s: %s", symbol, e)
            finally:
                if self.cfg.per_symbol_delay_seconds > 0:
                    time.sleep(self.cfg.per_symbol_delay_seconds)

        return out

