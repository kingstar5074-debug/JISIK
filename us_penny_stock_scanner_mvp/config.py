from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from scanner.filters import ScanFilters


@dataclass(frozen=True)
class AppConfig:
    tickers_file: Path
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


def load_config() -> AppConfig:
    """
    Load configuration from environment (.env) with safe defaults.
    """

    load_dotenv()

    project_root = Path(__file__).resolve().parent
    tickers_file = project_root / "tickers.txt"

    filters = ScanFilters(
        min_price=_get_env_float("MIN_PRICE", 0.05),
        max_price=_get_env_float("MAX_PRICE", 1.00),
        min_change_percent=_get_env_float("MIN_CHANGE_PERCENT", 15.0),
        min_volume_ratio=_get_env_float("MIN_VOLUME_RATIO", 3.0),
    )

    per_symbol_delay_seconds = _get_env_float("PER_SYMBOL_DELAY_SECONDS", 0.2)

    return AppConfig(
        tickers_file=tickers_file,
        filters=filters,
        per_symbol_delay_seconds=per_symbol_delay_seconds,
    )

