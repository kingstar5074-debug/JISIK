from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import requests

from config import AppConfig
from scanner.providers.polygon_provider import PolygonProvider, PolygonProviderConfig
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class UniverseBuildResult:
    total_candidates: int
    saved_symbols: int
    output_file: Path


def _fetch_all_snapshots(provider: PolygonProvider) -> Iterable[dict]:
    """
    Fetch market-wide snapshots from Polygon.

    NOTE: This uses the 'all tickers' snapshot endpoint and may be heavy on
    free plans. For now this is acceptable for a one-off universe build step.
    """
    url = f"{provider.cfg.base_url.rstrip('/')}/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {"apiKey": provider.cfg.api_key}

    resp = requests.get(url, params=params, timeout=provider.cfg.timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    tickers = data.get("tickers") or []
    return tickers


def _filter_penny_universe(
    snapshots: Iterable[dict],
    min_price: float,
    max_price: float,
    limit: int,
) -> List[str]:
    symbols: List[str] = []
    seen: set[str] = set()

    for t in snapshots:
        symbol = (t.get("ticker") or "").strip().upper()
        if not symbol or symbol in seen:
            continue

        last_trade = t.get("lastTrade") or {}
        day = t.get("day") or {}

        price = (
            last_trade.get("p")
            if last_trade.get("p") is not None
            else day.get("c")
        )
        try:
            price_f = float(price)
        except Exception:
            continue

        if not (min_price <= price_f <= max_price):
            continue

        seen.add(symbol)
        symbols.append(symbol)

        if len(symbols) >= limit:
            break

    symbols.sort()
    return symbols


def _save_universe_file(path: Path, symbols: List[str]) -> None:
    text = "\n".join(symbols) + ("\n" if symbols else "")
    path.write_text(text, encoding="utf-8")


def build_universe(config: AppConfig) -> UniverseBuildResult:
    """
    Build a penny-stock universe using Polygon snapshots and save to file.
    """

    if config.data_provider != "polygon":
        raise RuntimeError(
            "자동 유니버스 생성은 현재 DATA_PROVIDER=polygon 일 때만 지원합니다. "
            "먼저 .env 에서 DATA_PROVIDER=polygon 과 POLYGON_API_KEY 를 설정해 주세요."
        )

    if not config.polygon_api_key:
        raise RuntimeError(
            "POLYGON_API_KEY 가 설정되어 있지 않습니다. "
            "자동 유니버스 생성을 위해 유효한 Polygon API 키를 .env 에 넣어 주세요."
        )

    provider = PolygonProvider(
        PolygonProviderConfig(api_key=config.polygon_api_key)
    )

    log.info(
        "Building universe with Polygon: price %.2f ~ %.2f, limit=%d",
        config.universe_min_price,
        config.universe_max_price,
        config.universe_limit,
    )

    snapshots = list(_fetch_all_snapshots(provider))
    total_candidates = len(snapshots)

    symbols = _filter_penny_universe(
        snapshots,
        min_price=config.universe_min_price,
        max_price=config.universe_max_price,
        limit=config.universe_limit,
    )

    _save_universe_file(config.universe_output_file, symbols)

    log.info(
        "Universe build complete: total candidates=%d, saved=%d, output=%s",
        total_candidates,
        len(symbols),
        config.universe_output_file,
    )

    return UniverseBuildResult(
        total_candidates=total_candidates,
        saved_symbols=len(symbols),
        output_file=config.universe_output_file,
    )

