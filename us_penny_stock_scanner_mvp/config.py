from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from scanner.filters import ScanFilters


@dataclass(frozen=True)
class AppConfig:
    tickers_file: Path
    universe_file: Path
    universe_output_file: Path

    # 모드 & 데이터 공급자
    scan_mode: str
    data_provider: str
    polygon_api_key: Optional[str]

    # 유니버스 생성용 설정 (거친 1차 필터)
    universe_min_price: float
    universe_max_price: float
    universe_min_dollar_volume: float
    universe_min_average_volume: float
    universe_min_prev_close: float
    universe_limit: int

    # 스캐너 필터 (정교한 2차 필터)
    filters: ScanFilters
    per_symbol_delay_seconds: float
    top_results: int


def _get_env_str(name: str, default: str) -> str:
    import os

    v = os.getenv(name)
    return default if v is None or v == "" else v


def _get_env_float(name: str, default: float) -> float:
    import os

    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _get_env_int(name: str, default: int) -> int:
    import os

    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def load_config() -> AppConfig:
    """
    Load configuration from environment (.env) with safe defaults.
    """

    load_dotenv()

    project_root = Path(__file__).resolve().parent

    # 기본 파일 경로
    tickers_file = project_root / "tickers.txt"
    universe_name = _get_env_str("UNIVERSE_FILE", "universe_candidates.txt")
    universe_file = project_root / universe_name

    universe_output_name = _get_env_str(
        "UNIVERSE_OUTPUT_FILE", "generated_universe_candidates.txt"
    )
    universe_output_file = project_root / universe_output_name

    # 모드 / provider
    raw_mode = _get_env_str("SCAN_MODE", "watchlist")
    scan_mode = (raw_mode or "watchlist").strip().lower() or "watchlist"

    raw_provider = _get_env_str("DATA_PROVIDER", "yahoo")
    data_provider = (raw_provider or "yahoo").strip().lower() or "yahoo"

    import os

    raw_polygon_key = os.getenv("POLYGON_API_KEY")
    polygon_api_key = (raw_polygon_key.strip() if raw_polygon_key else None) or None

    # 스캐너 필터 (정교한 2차 필터)
    filters = ScanFilters(
        min_price=_get_env_float("MIN_PRICE", 0.05),
        max_price=_get_env_float("MAX_PRICE", 1.00),
        min_change_percent=_get_env_float("MIN_CHANGE_PERCENT", 15.0),
        min_volume_ratio=_get_env_float("MIN_VOLUME_RATIO", 3.0),
        min_gap_percent=_get_env_float("MIN_GAP_PERCENT", 5.0),
        min_intraday_change_percent=_get_env_float(
            "MIN_INTRADAY_CHANGE_PERCENT", 10.0
        ),
        min_dollar_volume=_get_env_float("MIN_DOLLAR_VOLUME", 500_000.0),
        min_average_volume=_get_env_float("MIN_AVERAGE_VOLUME", 100_000.0),
    )

    per_symbol_delay_seconds = _get_env_float("PER_SYMBOL_DELAY_SECONDS", 0.2)

    # 유니버스 생성용 (거친 1차 필터)
    universe_min_price = _get_env_float("UNIVERSE_MIN_PRICE", 0.05)
    universe_max_price = _get_env_float("UNIVERSE_MAX_PRICE", 1.00)
    universe_min_dollar_volume = _get_env_float(
        "UNIVERSE_MIN_DOLLAR_VOLUME", 300_000.0
    )
    universe_min_average_volume = _get_env_float(
        "UNIVERSE_MIN_AVERAGE_VOLUME", 50_000.0
    )
    universe_min_prev_close = _get_env_float("UNIVERSE_MIN_PREV_CLOSE", 0.05)
    universe_limit = _get_env_int("UNIVERSE_LIMIT", 500)

    top_results = _get_env_int("TOP_RESULTS", 20)

    return AppConfig(
        tickers_file=tickers_file,
        universe_file=universe_file,
        universe_output_file=universe_output_file,
        scan_mode=scan_mode,
        data_provider=data_provider,
        polygon_api_key=polygon_api_key,
        universe_min_price=universe_min_price,
        universe_max_price=universe_max_price,
        universe_min_dollar_volume=universe_min_dollar_volume,
        universe_min_average_volume=universe_min_average_volume,
        universe_min_prev_close=universe_min_prev_close,
        universe_limit=universe_limit,
        filters=filters,
        per_symbol_delay_seconds=per_symbol_delay_seconds,
        top_results=top_results,
    )

