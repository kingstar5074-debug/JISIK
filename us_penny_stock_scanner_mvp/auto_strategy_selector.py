from __future__ import annotations

"""
Auto Strategy Selector.

Outcome Performance Analyzer 가 생성한 outcome_summary_strategy.json 을 읽어,
실제 성능 데이터 기반으로 복합 점수를 계산하고 최적 전략을 추천합니다.

입력:
- reports/outcome_analysis/outcome_summary_strategy.json (필수)
- reports/outcome_analysis/outcome_summary_theme.json (선택)

복합 점수:
  strategy_score = (average_return * 0.5) + (win_rate * 0.3) + (median_return * 0.2)

출력:
- reports/strategy_recommendation/recommended_strategy.json

기존 스캐너/리포트 로직을 수정하지 않으며 독립적으로 동작합니다.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

DEFAULT_STRATEGY_INPUT = "reports/outcome_analysis/outcome_summary_strategy.json"
DEFAULT_THEME_INPUT = "reports/outcome_analysis/outcome_summary_theme.json"
DEFAULT_OUTPUT_DIR = "reports/strategy_recommendation"
OUTPUT_FILENAME = "recommended_strategy.json"

# Composite score weights
WEIGHT_AVERAGE_RETURN = 0.5
WEIGHT_WIN_RATE = 0.3
WEIGHT_MEDIAN_RETURN = 0.2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recommend best strategy from outcome summary (strategy/theme)"
    )
    parser.add_argument(
        "--strategy-summary",
        type=str,
        default=DEFAULT_STRATEGY_INPUT,
        help=f"Path to outcome_summary_strategy.json (default: {DEFAULT_STRATEGY_INPUT})",
    )
    parser.add_argument(
        "--theme-summary",
        type=str,
        default="",
        help="Optional path to outcome_summary_theme.json",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def _load_json(path: Path, console: Console) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as e:
        console.print(f"JSON 읽기 실패 ({path}): {e}")
        return None


def _float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _compute_strategy_score(item: dict[str, Any]) -> float:
    """Composite score: (average_return * 0.5) + (win_rate * 0.3) + (median_return * 0.2)."""
    avg_ret = _float(item.get("average_return"))
    win_rate = _float(item.get("win_rate"))
    med_ret = _float(item.get("median_return"))
    return (
        avg_ret * WEIGHT_AVERAGE_RETURN
        + win_rate * WEIGHT_WIN_RATE
        + med_ret * WEIGHT_MEDIAN_RETURN
    )


def _confidence(top_score: float, second_score: float | None) -> float:
    """Confidence in [0, 1]: higher when top strategy leads by more."""
    if second_score is None:
        return 0.5
    if top_score <= 0:
        return 0.0
    diff = top_score - second_score
    # Normalize: 0 when tied, up to 1 when top dominates
    ratio = diff / (top_score + 1e-9)
    return max(0.0, min(1.0, round(ratio, 2)))


def main() -> int:
    args = _parse_args()
    console = Console()

    project_root = Path(__file__).resolve().parent
    strategy_path = Path(args.strategy_summary)
    if not strategy_path.is_absolute():
        strategy_path = project_root / strategy_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    console.print("Auto Strategy Selector")
    console.print(f"strategy summary: {strategy_path}")

    data = _load_json(strategy_path, console)
    if not data:
        console.print(
            "outcome_summary_strategy.json 을 찾을 수 없거나 비어 있습니다. "
            "먼저 outcome_performance_analyzer.py --group-by strategy 를 실행하세요."
        )
        return 0

    summary = data.get("summary")
    if not isinstance(summary, list) or not summary:
        console.print("요약(summary) 데이터가 없습니다.")
        return 0

    # Build ranking: each item has group, average_return, win_rate, median_return
    scored: list[dict[str, Any]] = []
    for item in summary:
        group = (item.get("group") or "").strip()
        if not group:
            continue
        score = _compute_strategy_score(item)
        scored.append({
            "strategy": group,
            "score": round(score, 2),
            "average_return": _float(item.get("average_return")),
            "win_rate": _float(item.get("win_rate")),
            "median_return": _float(item.get("median_return")),
        })

    if not scored:
        console.print("유효한 전략 항목이 없습니다.")
        return 0

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[0]
    second_score = scored[1]["score"] if len(scored) > 1 else None
    confidence = _confidence(top["score"], second_score)

    ranking = [{"strategy": x["strategy"], "score": x["score"]} for x in scored]
    recommended_strategy = top["strategy"]

    # Optional: load theme summary for metadata only (no change to recommendation)
    theme_path: Path | None = None
    if args.theme_summary and args.theme_summary.strip():
        theme_path = Path(args.theme_summary)
        if not theme_path.is_absolute():
            theme_path = project_root / theme_path
    else:
        theme_path = project_root / DEFAULT_THEME_INPUT
    theme_loaded = _load_json(theme_path, console) if theme_path else None

    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "recommended_strategy": recommended_strategy,
        "confidence": round(confidence, 2),
        "ranking": ranking,
        "input_file": str(strategy_path),
        "score_weights": {
            "average_return": WEIGHT_AVERAGE_RETURN,
            "win_rate": WEIGHT_WIN_RATE,
            "median_return": WEIGHT_MEDIAN_RETURN,
        },
    }
    if theme_loaded and isinstance(theme_loaded.get("summary"), list):
        payload["theme_summary_loaded"] = True
    else:
        payload["theme_summary_loaded"] = False

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / OUTPUT_FILENAME

    try:
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        console.print(f"저장 실패: {e}")
        return 0

    console.print(f"\n추천 전략: {recommended_strategy}")
    console.print(f"신뢰도: {confidence:.2f}")
    console.print("순위:")
    for i, r in enumerate(ranking, start=1):
        console.print(f"  {i}. {r['strategy']}: {r['score']:.2f}")
    console.print(f"\n저장: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
