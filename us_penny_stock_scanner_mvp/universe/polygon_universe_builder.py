from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from config import AppConfig
from scanner.providers.polygon_provider import PolygonProvider, PolygonProviderConfig
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class UniverseBuildResult:
    total_candidates: int
    price_filtered: int
    liquidity_filtered: int
    saved_symbols: int
    output_file: Path


def _fetch_all_snapshots(provider: PolygonProvider) -> Iterable[dict]:
    """
    Polygon US 주식 전체 스냅샷 조회.

    NOTE: all-tickers 스냅샷 엔드포인트이므로 무료 플랜에서는 무거울 수 있다.
    유니버스 생성은 주기적인 오프라인 작업이므로 허용 가능한 수준으로 본다.
    """

    url = (
        f"{provider.cfg.base_url.rstrip('/')}"
        "/v2/snapshot/locale/us/markets/stocks/tickers"
    )
    params = {"apiKey": provider.cfg.api_key}

    resp = requests.get(url, params=params, timeout=provider.cfg.timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    tickers = data.get("tickers") or []
    return tickers


def _normalize_symbol(raw: str) -> Optional[str]:
    """
    심볼 정규화:
    - 앞뒤 공백 제거
    - 대문자 통일
    - A-Z / 0-9 / '.' 만 허용
    - 그 외 문자가 포함되면 None 반환
    """

    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    for ch in s:
        if not (("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "."):
            return None
    return s


def _safe_float(v: object) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _first_stage_price_and_dollar_filter(
    snapshots: Iterable[dict],
    cfg: AppConfig,
) -> List[Dict[str, object]]:
    """
    1단계 필터:
    - 가격 범위 (universe_min_price ~ universe_max_price)
    - prev_close >= universe_min_prev_close
    - 현재 dollar_volume >= universe_min_dollar_volume

    여기서는 snapshot 데이터만 사용해 후보를 크게 압축한다.
    """

    candidates: List[Dict[str, object]] = []
    seen: set[str] = set()

    for t in snapshots:
        symbol = _normalize_symbol(t.get("ticker") or "")
        if not symbol or symbol in seen:
            continue

        last_trade = t.get("lastTrade") or {}
        day = t.get("day") or {}
        prev_day = t.get("prevDay") or {}

        # price: lastTrade.p 우선, 없으면 day.c 사용
        price = _safe_float(
            last_trade.get("p") if last_trade.get("p") is not None else day.get("c")
        )
        prev_close = _safe_float(prev_day.get("c"))
        current_volume = _safe_float(day.get("v"))

        if price is None or prev_close is None or current_volume is None:
            continue

        if not (cfg.universe_min_price <= price <= cfg.universe_max_price):
            continue

        if prev_close < cfg.universe_min_prev_close:
            continue

        dollar_volume = price * current_volume
        if dollar_volume < cfg.universe_min_dollar_volume:
            continue

        seen.add(symbol)
        candidates.append(
            {
                "symbol": symbol,
                "price": price,
                "prev_close": prev_close,
                "current_volume": current_volume,
                "dollar_volume": dollar_volume,
            }
        )

    # dollar_volume 내림차순으로 정렬 (더 유동성 좋은 종목 우선)
    candidates.sort(key=lambda x: x["dollar_volume"], reverse=True)
    return candidates


def _fetch_average_volume_for_candidates(
    provider: PolygonProvider,
    candidates: List[Dict[str, object]],
) -> List[Tuple[str, float]]:
    """
    2단계: 압축된 후보들에 대해서만 Polygon aggregates API 를 사용해
    평균 거래량을 계산한다.

    반환값: (symbol, average_volume)
    """

    results: List[Tuple[str, float]] = []
    for c in candidates:
        symbol = c["symbol"]
        try:
            avg_vol = provider._fetch_average_volume(str(symbol))
        except Exception as e:  # pragma: no cover - 방어적 로깅
            log.warning("Failed to fetch average volume for %s: %s", symbol, e)
            continue

        if avg_vol is None:
            continue

        results.append((str(symbol), avg_vol))

    return results


def _save_universe_file(path: Path, symbols: List[str]) -> None:
    # 중복 제거 및 정렬 (심볼은 이미 정규화됐다고 가정)
    unique_sorted = sorted({s.strip().upper() for s in symbols if s.strip()})
    text = "\n".join(unique_sorted) + ("\n" if unique_sorted else "")
    path.write_text(text, encoding="utf-8")


def build_universe(config: AppConfig) -> UniverseBuildResult:
    """
    Polygon 스냅샷 + aggregates 를 활용해
    가격 + 유동성(달러 거래대금, 평균 거래량) 기반으로
    동전주 유니버스를 생성한다.
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
        "Building universe with Polygon: "
        "price %.2f ~ %.2f, prev_close>=%.2f, "
        "universe_min_dollar_volume=%.0f, "
        "universe_min_average_volume=%.0f, limit=%d",
        config.universe_min_price,
        config.universe_max_price,
        config.universe_min_prev_close,
        config.universe_min_dollar_volume,
        config.universe_min_average_volume,
        config.universe_limit,
    )

    snapshots = list(_fetch_all_snapshots(provider))
    total_candidates = len(snapshots)

    # 1단계: 가격 + prev_close + dollar_volume 기반 압축
    stage1_candidates = _first_stage_price_and_dollar_filter(snapshots, config)
    price_filtered = len(stage1_candidates)

    # 2단계: 압축된 후보에 대해서만 평균 거래량 계산
    avg_volume_list = _fetch_average_volume_for_candidates(provider, stage1_candidates)

    liquidity_pass: List[str] = []
    for symbol, avg_vol in avg_volume_list:
        if avg_vol >= config.universe_min_average_volume:
            liquidity_pass.append(symbol)

    liquidity_filtered = len(liquidity_pass)

    # 최종 limit 적용
    final_symbols = liquidity_pass[: config.universe_limit]
    _save_universe_file(config.universe_output_file, final_symbols)

    log.info(
        "Universe build complete: total=%d, price_filtered=%d, "
        "liquidity_filtered=%d, saved=%d, output=%s",
        total_candidates,
        price_filtered,
        liquidity_filtered,
        len(final_symbols),
        config.universe_output_file,
    )

    return UniverseBuildResult(
        total_candidates=total_candidates,
        price_filtered=price_filtered,
        liquidity_filtered=liquidity_filtered,
        saved_symbols=len(final_symbols),
        output_file=config.universe_output_file,
    )

