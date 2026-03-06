from __future__ import annotations

"""
Outcome Performance Analyzer.

trade_outcome_tracker.py 가 생성한 trade_results.csv 를 읽어,
실제 거래 결과(수익률)를 전략/테마/세션/프로바이더별로 집계하고
요약 리포트(JSON, CSV, PNG 차트)를 생성합니다.

목적:
- 어떤 전략이 실제로 가장 잘 수행되는가?
- 어떤 테마가 실제 수익률이 가장 좋은가?
- 어떤 세션이 가장 강한가?
- 어떤 프로바이더가 가장 좋은가?
- 실제 승률과 평균 수익률은 얼마인가?

이 스크립트는 스캐너 로직을 수정하지 않으며, 기존 리포트 파이프라인과 독립적으로 동작합니다.
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rich.console import Console

# Expected column names in trade_results.csv
REQUIRED_COLUMNS = [
    "timestamp_entry",
    "timestamp_exit",
    "symbol",
    "strategy",
    "theme",
    "provider",
    "session",
    "entry_price",
    "exit_price",
    "return_pct",
]

GROUP_BY_OPTIONS = ("strategy", "theme", "session", "provider")
METRIC_OPTIONS = ("average_return", "win_rate", "trade_count", "median_return")

DEFAULT_INPUT = "reports/trade_outcomes/trade_results.csv"
DEFAULT_OUTPUT_DIR = "reports/outcome_analysis"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze trade outcome performance from trade_results.csv"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT,
        help=f"Path to trade_results.csv (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--group-by",
        type=str,
        default="strategy",
        choices=GROUP_BY_OPTIONS,
        help="Group analysis by: strategy, theme, session, provider (default: strategy)",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=3,
        help="Minimum trade count to include a group (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for reports (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="average_return",
        choices=METRIC_OPTIONS,
        help="Primary metric for chart: average_return, win_rate, trade_count, median_return (default: average_return)",
    )
    return parser.parse_args()


def _parse_float(s: str | None) -> float | None:
    """Safely parse a string to float. Returns None if invalid."""
    if s is None or (isinstance(s, str) and not s.strip()):
        return None
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return None


def _load_trades(input_path: Path, console: Console) -> list[dict[str, Any]]:
    """
    Load and validate rows from trade_results.csv.
    Returns list of dicts with at least: group_key (str), return_pct (float).
    """
    if not input_path.exists():
        console.print(f"입력 파일이 없습니다: {input_path}")
        return []

    if not input_path.is_file():
        console.print(f"입력 경로가 파일이 아닙니다: {input_path}")
        return []

    rows: list[dict[str, Any]] = []
    try:
        with input_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                # Check required fields present
                missing = [c for c in REQUIRED_COLUMNS if not (row.get(c) or "").strip()]
                if missing:
                    continue
                return_pct = _parse_float(row.get("return_pct"))
                if return_pct is None:
                    continue
                rows.append(dict(row))
    except Exception as e:
        console.print(f"CSV 읽기 오류: {e}")
        return []

    return rows


def _group_key(row: dict[str, Any], group_by: str) -> str | None:
    """Extract grouping key from row. Returns None if empty."""
    raw = (row.get(group_by) or "").strip()
    return raw if raw else None


def _compute_group_stats(returns: list[float]) -> dict[str, Any]:
    """Compute trade_count, win_count, loss_count, win_rate, average_return, median_return, best_return, worst_return."""
    n = len(returns)
    if n == 0:
        return {
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "average_return": 0.0,
            "median_return": 0.0,
            "best_return": 0.0,
            "worst_return": 0.0,
        }
    win_count = sum(1 for r in returns if r > 0)
    loss_count = n - win_count
    win_rate = (win_count / n) * 100.0 if n else 0.0
    avg_ret = mean(returns)
    med_ret = median(returns)
    best_ret = max(returns)
    worst_ret = min(returns)
    return {
        "trade_count": n,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "average_return": round(avg_ret, 2),
        "median_return": round(med_ret, 2),
        "best_return": round(best_ret, 2),
        "worst_return": round(worst_ret, 2),
    }


def _round_summary(s: dict[str, Any]) -> dict[str, Any]:
    """Ensure numeric fields are rounded for JSON/CSV output."""
    out = dict(s)
    for k in ("win_rate", "average_return", "median_return", "best_return", "worst_return"):
        if k in out and isinstance(out[k], (int, float)):
            out[k] = round(float(out[k]), 2)
    return out


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

    group_by = args.group_by
    min_trades = max(0, args.min_trades)
    metric = args.metric

    console.print("Outcome Performance Analyzer")
    console.print(f"input: {input_path}")
    console.print(f"group_by: {group_by}")
    console.print(f"min_trades: {min_trades}")
    console.print(f"metric: {metric}")
    console.print(f"output_dir: {output_dir}")

    raw_rows = _load_trades(input_path, console)
    if not raw_rows:
        console.print("유효한 거래 데이터가 없습니다. 입력 파일을 확인하거나 거래 결과를 먼저 생성하세요.")
        return 0

    # Group by key; collect return_pct per group
    groups: dict[str, list[float]] = defaultdict(list)
    for row in raw_rows:
        key = _group_key(row, group_by)
        if key is None:
            continue
        r = _parse_float(row.get("return_pct"))
        if r is None:
            continue
        groups[key].append(r)

    # Compute stats per group; exclude groups below min_trades
    summary_list: list[dict[str, Any]] = []
    for key in sorted(groups.keys()):
        returns = groups[key]
        if len(returns) < min_trades:
            continue
        stats = _compute_group_stats(returns)
        summary_list.append({"group": key, **stats})

    if not summary_list:
        console.print(
            f"min_trades={min_trades} 조건을 만족하는 그룹이 없습니다. "
            "데이터를 추가하거나 --min-trades 값을 낮춰 보세요."
        )
        return 0

    total_valid_trades = sum(s["trade_count"] for s in summary_list)
    total_groups_included = len(summary_list)

    # Sort for CSV: by selected metric descending. For worst_return, higher is better so still descending.
    def sort_key(item: dict[str, Any]) -> Any:
        m = metric
        v = item.get(m)
        if v is None:
            return -1e9 if m != "worst_return" else 1e9
        return v

    summary_list_sorted = sorted(summary_list, key=sort_key, reverse=True)

    # Metadata for JSON
    generated_at = datetime.now().isoformat(timespec="seconds")
    metadata = {
        "generated_at": generated_at,
        "input_file": str(input_path),
        "group_by": group_by,
        "metric": metric,
        "min_trades": min_trades,
        "total_valid_trades": total_valid_trades,
        "total_groups_included": total_groups_included,
    }

    payload = {
        "metadata": metadata,
        "summary": [_round_summary(s) for s in summary_list_sorted],
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"outcome_summary_{group_by}.json"
    csv_path = output_dir / f"outcome_summary_{group_by}.csv"
    png_path = output_dir / f"outcome_{group_by}_{metric}.png"

    try:
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        console.print(f"JSON 저장 실패: {e}")

    csv_columns = [
        "group",
        "trade_count",
        "win_count",
        "loss_count",
        "win_rate",
        "average_return",
        "median_return",
        "best_return",
        "worst_return",
    ]
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            for s in summary_list_sorted:
                row = {c: s.get(c, "") for c in csv_columns}
                writer.writerow(row)
    except Exception as e:
        console.print(f"CSV 저장 실패: {e}")

    # Bar chart: x = groups, y = selected metric
    try:
        groups_names = [s["group"] for s in summary_list_sorted]
        values = [s.get(metric, 0) for s in summary_list_sorted]
        if not groups_names or not values:
            console.print("차트 데이터가 없어 PNG를 생성하지 않습니다.")
        else:
            fig, ax = plt.subplots()
            ax.bar(groups_names, values)
            ax.set_xlabel(group_by)
            ax.set_ylabel(metric)
            ax.set_title(f"Outcome Performance by {group_by}\n(metric={metric})")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
            fig.tight_layout()
            fig.savefig(png_path)
            plt.close(fig)
    except Exception as e:
        console.print(f"차트 저장 실패: {e}")

    console.print("\n저장된 파일:")
    console.print(f"  JSON: {json_path}")
    console.print(f"  CSV:  {csv_path}")
    console.print(f"  PNG:  {png_path}")
    console.print(f"총 유효 거래 수: {total_valid_trades}, 포함 그룹 수: {total_groups_included}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
