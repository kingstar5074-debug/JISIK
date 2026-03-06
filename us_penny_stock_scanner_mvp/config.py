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
    scan_mode: str
    data_provider: str
    polygon_api_key: Optional[str]
    universe_min_price: float
    universe_max_price: float
    universe_limit: int
    filters: ScanFilters
    per_symbol_delay_seconds: float


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

    import os

    tickers_file = project_root / "tickers.txt"
    universe_name = os.getenv("UNIVERSE_FILE", "universe_candidates.txt")
    universe_file = project_root / universe_name

    universe_output_name = os.getenv("UNIVERSE_OUTPUT_FILE", "generated_universe_candidates.txt")
    universe_output_file = project_root / universe_output_name

    raw_mode = os.getenv("SCAN_MODE", "watchlist")
    scan_mode = (raw_mode or "watchlist").strip().lower() or "watchlist"

    raw_provider = os.getenv("DATA_PROVIDER", "yahoo")
    data_provider = (raw_provider or "yahoo").strip().lower() or "yahoo"

    raw_polygon_key = os.getenv("POLYGON_API_KEY")
    polygon_api_key = (raw_polygon_key.strip() if raw_polygon_key else None) or None

    filters = ScanFilters(
        min_price=_get_env_float("MIN_PRICE", 0.05),
        max_price=_get_env_float("MAX_PRICE", 1.00),
        min_change_percent=_get_env_float("MIN_CHANGE_PERCENT", 15.0),
        min_volume_ratio=_get_env_float("MIN_VOLUME_RATIO", 3.0),
    )

    per_symbol_delay_seconds = _get_env_float("PER_SYMBOL_DELAY_SECONDS", 0.2)

    universe_min_price = _get_env_float("UNIVERSE_MIN_PRICE", 0.05)
    universe_max_price = _get_env_float("UNIVERSE_MAX_PRICE", 1.00)
    universe_limit = _get_env_int("UNIVERSE_LIMIT", 500)

    return AppConfig(
        tickers_file=tickers_file,
        universe_file=universe_file,
        universe_output_file=universe_output_file,
        scan_mode=scan_mode,
        data_provider=data_provider,
        polygon_api_key=polygon_api_key,
        universe_min_price=universe_min_price,
        universe_max_price=universe_max_price,
        universe_limit=universe_limit,
        filters=filters,
        per_symbol_delay_seconds=per_symbol_delay_seconds,
    )

