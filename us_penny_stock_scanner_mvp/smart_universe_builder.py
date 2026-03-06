from __future__ import annotations

"""
Polygon Smart Universe Builder.

Polygon US 주식 데이터를 사용해 동전주 스캐너용 유니버스를 생성합니다.

- 기존 watchlist 모드를 대체하지 않고, universe 모드에서 사용할
  더 큰 심볼 풀을 만드는 것이 목적입니다.
- 내부 로직은 기존 Polygon 유니버스 빌더(universe.polygon_universe_builder)를 재사용합니다.
"""

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from config import load_config
from universe.polygon_universe_builder import UniverseBuildResult, build_universe


PROJECT_ROOT = Path(__file__).resolve().parent


def _get_env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _get_env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def _save_report(
    reports_dir: Path,
    output_file: Path,
    price_min: float,
    price_max: float,
    min_volume: float,
    min_dollar_volume: float,
    max_symbols: int,
    result: UniverseBuildResult,
) -> Path:
    out_dir = reports_dir / "universe"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "universe_build_report.json"

    try:
        rel_output = output_file.relative_to(PROJECT_ROOT)
        output_str = str(rel_output)
    except ValueError:
        output_str = str(output_file)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "polygon",
        "price_min": price_min,
        "price_max": price_max,
        "min_volume": min_volume,
        "min_dollar_volume": min_dollar_volume,
        "max_symbols": max_symbols,
        "total_candidates_seen": result.total_candidates,
        "total_selected": result.saved_symbols,
        "output_file": output_str,
    }

    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Polygon Smart Universe Builder")
    parser.add_argument(
        "--price-min",
        type=float,
        default=None,
        help="minimum price for candidates (default: UNIVERSE_PRICE_MIN or 0.05)",
    )
    parser.add_argument(
        "--price-max",
        type=float,
        default=None,
        help="maximum price for candidates (default: UNIVERSE_PRICE_MAX or 10.0)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=None,
        help="minimum average volume for candidates (default: UNIVERSE_MIN_VOLUME or 50000)",
    )
    parser.add_argument(
        "--min-dollar-volume",
        type=float,
        default=None,
        help="minimum dollar volume for candidates (default: UNIVERSE_MIN_DOLLAR_VOLUME or 100000)",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="maximum number of symbols to save (default: UNIVERSE_MAX_SYMBOLS or 1000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print detailed progress information",
    )
    args = parser.parse_args()

    cfg = load_config()

    # Polygon API 키 확인
    if not cfg.polygon_api_key:
        print(
            "POLYGON_API_KEY 가 설정되어 있지 않습니다. "
            ".env 또는 환경변수에 유효한 Polygon API 키를 설정한 뒤 다시 시도해 주세요."
        )
        return 1

    # ENV + CLI 기반 파라미터 해석
    price_min_default = _get_env_float("UNIVERSE_PRICE_MIN", 0.05)
    price_max_default = _get_env_float("UNIVERSE_PRICE_MAX", 10.0)
    min_volume_default = _get_env_float("UNIVERSE_MIN_VOLUME", 50_000.0)
    min_dollar_default = _get_env_float("UNIVERSE_MIN_DOLLAR_VOLUME", 100_000.0)
    max_symbols_default = _get_env_int("UNIVERSE_MAX_SYMBOLS", 1000)

    price_min = args.price_min if args.price_min is not None else price_min_default
    price_max = args.price_max if args.price_max is not None else price_max_default
    min_volume = args.min_volume if args.min_volume is not None else min_volume_default
    min_dollar_volume = (
        args.min_dollar_volume
        if args.min_dollar_volume is not None
        else min_dollar_default
    )
    max_symbols = args.max_symbols if args.max_symbols is not None else max_symbols_default

    # 기본 검증
    if price_min <= 0 or price_max <= 0 or price_min > price_max:
        print(f"잘못된 가격 범위입니다: price_min={price_min}, price_max={price_max}")
        return 1
    if min_volume < 0 or min_dollar_volume < 0:
        print(
            f"거래량/달러 거래대금 임계값은 0 이상이어야 합니다: "
            f"min_volume={min_volume}, min_dollar_volume={min_dollar_volume}"
        )
        return 1
    if max_symbols <= 0:
        print(f"max_symbols 값은 1 이상이어야 합니다: max_symbols={max_symbols}")
        return 1

    # 출력 파일 경로: universe/generated_universe.txt
    universe_output_file = PROJECT_ROOT / "universe" / "generated_universe.txt"
    universe_output_file.parent.mkdir(parents=True, exist_ok=True)

    # 기존 AppConfig 를 기반으로, 유니버스 관련 필드만 교체
    cfg_for_universe = replace(
        cfg,
        universe_min_price=price_min,
        universe_max_price=price_max,
        universe_min_average_volume=min_volume,
        universe_min_dollar_volume=min_dollar_volume,
        universe_limit=max_symbols,
        universe_output_file=universe_output_file,
    )

    if args.verbose:
        print("Loading Polygon market data...")
        print(
            f"Filters: price {price_min:.2f}~{price_max:.2f}, "
            f"avg_volume>={min_volume:.0f}, dollar_volume>={min_dollar_volume:.0f}, "
            f"max_symbols={max_symbols}"
        )

    try:
        result = build_universe(cfg_for_universe)
    except RuntimeError as e:
        # polygon_universe_builder 가 던지는 친절한 메시지 재사용
        print(str(e))
        return 1
    except Exception as e:
        print(f"Universe build failed: {e}")
        return 1

    # JSON 리포트 저장
    report_path = _save_report(
        cfg.reports_dir,
        universe_output_file,
        price_min,
        price_max,
        min_volume,
        min_dollar_volume,
        max_symbols,
        result,
    )

    if args.verbose:
        print(f"Seen candidates: {result.total_candidates}")
        print(f"Selected symbols: {result.saved_symbols}")
        print(f"Saved: {universe_output_file}")
        print(f"Saved report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

