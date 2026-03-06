from __future__ import annotations

"""
Market Regime Detector.

최근 실제 거래 결과(trade_results.csv)를 사용해 현재 시장 국면을 판별합니다.

입력: reports/trade_outcomes/trade_results.csv (또는 --input)
- 최근 lookback 건의 유효 거래만 사용해 average_return, median_return, volatility, positive_rate 계산
- 규칙에 따라 regime: VOLATILE | TRENDING | WEAK | RANGE 중 하나로 설정

출력: reports/market_regime/market_regime.json

기존 스캐너/리포트 로직을 수정하지 않으며 독립적으로 동작합니다.
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from rich.console import Console

DEFAULT_INPUT = "reports/trade_outcomes/trade_results.csv"
DEFAULT_OUTPUT_DIR = "reports/market_regime"
OUTPUT_FILENAME = "market_regime.json"

REQUIRED_COLUMNS = ["return_pct"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect market regime from recent trade outcomes"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT,
        help=f"Path to trade_results.csv (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=50,
        help="Number of most recent valid trades to analyze (default: 50)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def _parse_float(s: str | None) -> float | None:
    if s is None or (isinstance(s, str) and not s.strip()):
        return None
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return None


def _load_returns(input_path: Path, lookback: int, console: Console) -> list[float]:
    """
    Load trade_results.csv, keep rows with valid return_pct, take most recent up to lookback.
    Returns list of return_pct values (newest first if we sort by timestamp_exit).
    """
    if not input_path.exists():
        console.print(f"입력 파일이 없습니다: {input_path}")
        return []

    if not input_path.is_file():
        console.print(f"입력 경로가 파일이 아닙니다: {input_path}")
        return []

    rows_with_returns: list[tuple[str, float]] = []  # (timestamp_exit or "", return_pct)

    try:
        with input_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                return_pct = _parse_float(row.get("return_pct"))
                if return_pct is None:
                    continue
                ts = (row.get("timestamp_exit") or row.get("timestamp_entry") or "").strip()
                rows_with_returns.append((ts, return_pct))
    except Exception as e:
        console.print(f"CSV 읽기 오류: {e}")
        return []

    if not rows_with_returns:
        return []

    # Sort by timestamp descending (most recent first); invalid timestamps stay at end
    def sort_key(item: tuple[str, float]) -> tuple[bool, str]:
        ts = item[0]
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (False, ts)
        except Exception:
            return (True, "")

    rows_with_returns.sort(key=sort_key, reverse=True)

    returns = [r for _, r in rows_with_returns[: lookback]]
    return returns


def _detect_regime(
    average_return: float,
    positive_rate: float,
    volatility: float,
) -> str:
    """Apply regime rules in order. Returns VOLATILE | TRENDING | WEAK | RANGE."""
    if volatility > 5:
        return "VOLATILE"
    if average_return > 1 and positive_rate >= 55:
        return "TRENDING"
    if average_return < -1 and positive_rate < 45:
        return "WEAK"
    return "RANGE"


def main() -> int:
    args = _parse_args()
    console = Console()

    project_root = Path(__file__).resolve().parent
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project_root / input_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    lookback = max(1, args.lookback)

    returns = _load_returns(input_path, lookback, console)
    if not returns:
        console.print("유효한 거래가 없습니다. trade_results.csv 를 확인하거나 먼저 trade_outcome_tracker.py --evaluate 를 실행하세요.")
        return 0

    n = len(returns)
    average_return = round(mean(returns), 2)
    median_return = round(median(returns), 2)
    volatility = round(pstdev(returns), 2) if n >= 2 else 0.0
    positive_count = sum(1 for r in returns if r > 0)
    positive_rate = round((positive_count / n) * 100.0, 1)

    regime = _detect_regime(average_return, positive_rate, volatility)

    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_file": str(input_path),
        "lookback": lookback,
        "trades_analyzed": n,
        "average_return": average_return,
        "median_return": median_return,
        "volatility": volatility,
        "positive_rate": positive_rate,
        "regime": regime,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / OUTPUT_FILENAME

    try:
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        console.print(f"저장 실패: {e}")
        return 0

    console.print("\nRegime: " + regime)
    console.print(f"Trades analyzed: {n}")
    console.print(f"Average return: {average_return}")
    console.print(f"Volatility: {volatility}")
    console.print(f"Positive rate: {positive_rate}")
    console.print(f"\n저장: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
