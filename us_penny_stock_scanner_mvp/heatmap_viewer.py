from __future__ import annotations

"""
Theme & Session-aware Heatmap Viewer.

이 스크립트는 summarize_strategy_reports.py 가 생성한 전략 요약 JSON
(`strategy_summary_*.json`) 파일들을 읽고,

- theme (행)
- strategy (열)

축으로 구성된 성능 지표 heatmap 을 생성한다.

지원 메트릭:
- average_score    : mean_average_score
- stability_score  : mean_stability_score
- count            : 총 표본 수

필터 옵션:
- provider / session / tag (요약 JSON에 메타데이터가 있을 경우에만 적용)
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from rich.console import Console


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Theme vs Strategy Heatmap Viewer"
    )
    parser.add_argument(
        "--summary-dir",
        type=str,
        default="reports",
        help="strategy_summary_*.json 파일이 들어있는 디렉터리 (기본: reports)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="average_score",
        choices=["average_score", "stability_score", "count"],
        help="heatmap 에 사용할 메트릭 (기본: average_score)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="",
        help="summary JSON 의 provider 필터 (예: yahoo, polygon)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="",
        help="summary JSON 의 session 필터 (예: premarket, regular)",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="summary JSON 의 used_filters.tags 필터 (여러 개 지정 시 AND 조건)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="셀에 포함되기 위한 최소 표본 수 (기본: 3)",
    )
    return parser.parse_args()


def _load_summaries(
    summary_dir: Path,
    console: Console,
    provider_filter: str,
    session_filter: str,
    tag_filters: List[str],
) -> List[Tuple[Path, Dict]]:
    json_files = sorted(summary_dir.glob("strategy_summary_*.json"))
    if not json_files:
        console.print(f"strategy_summary_*.json 파일을 찾을 수 없습니다: {summary_dir}")
        return []

    loaded: List[Tuple[Path, Dict]] = []
    skipped = 0

    tag_filters_norm = [t.strip().lower() for t in tag_filters if t.strip()]

    for path in json_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue

        if not isinstance(data, dict) or "strategies" not in data:
            skipped += 1
            continue

        # provider / session / tags 메타데이터 추출 (없으면 필터 미적용)
        used_filters = data.get("used_filters") or {}
        prov = str(data.get("provider") or used_filters.get("provider") or "").strip().lower()
        sess = str(data.get("session") or used_filters.get("session") or "").strip().lower()
        tags_raw = used_filters.get("tags") or []
        tags = [str(t).strip().lower() for t in tags_raw if isinstance(t, str)]

        if provider_filter and prov and prov != provider_filter:
            continue
        if provider_filter and not prov:
            # provider 필터가 설정됐는데 메타데이터가 없으면 제외
            continue

        if session_filter and sess and sess != session_filter:
            continue
        if session_filter and not sess:
            # session 필터가 설정됐는데 메타데이터가 없으면 제외
            continue

        if tag_filters_norm:
            if not tags:
                continue
            if not all(t in tags for t in tag_filters_norm):
                continue

        loaded.append((path, data))

    if skipped:
        console.print(f"무시된 summary 파일 수: {skipped}")

    return loaded


def main() -> int:
    args = _parse_args()
    console = Console()

    summary_dir = Path(args.summary_dir)
    metric = args.metric
    provider_filter = (args.provider or "").strip().lower()
    session_filter = (args.session or "").strip().lower()
    tag_filters = [t.strip().lower() for t in (args.tag or []) if t.strip()]
    min_samples = args.min_samples

    console.print("Theme & Strategy Heatmap Viewer")
    console.print(f"summary_dir: {summary_dir}")
    console.print(f"metric: {metric}")
    console.print(f"provider filter: {provider_filter or '(없음)'}")
    console.print(f"session filter: {session_filter or '(없음)'}")
    console.print(
        "tag filter: "
        + (", ".join(tag_filters) if tag_filters else "(없음)")
    )
    console.print(f"min_samples: {min_samples}")

    if not summary_dir.exists() or not summary_dir.is_dir():
        console.print(f"요약 디렉터리를 찾을 수 없습니다: {summary_dir}")
        return 0

    loaded = _load_summaries(summary_dir, console, provider_filter, session_filter, tag_filters)
    if not loaded:
        return 0

    # theme x strategy 집계 구조
    # agg[theme][strategy] = {"count": int, "ws_avg": float, "ws_stab": float}
    agg: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0.0, "ws_avg": 0.0, "ws_stab": 0.0})
    )
    all_strategies: set[str] = set()

    for path, data in loaded:
        strategies = data.get("strategies") or {}
        if not isinstance(strategies, dict):
            continue

        for strat_name, s_data in strategies.items():
            if not isinstance(s_data, dict):
                continue
            all_strategies.add(strat_name)

            tperf = s_data.get("theme_performance") or {}
            if not isinstance(tperf, dict):
                continue

            for theme, perf in tperf.items():
                if not isinstance(perf, dict):
                    continue
                t = str(theme).strip().lower()
                if not t:
                    continue
                c = perf.get("count")
                avg = perf.get("avg_score")
                stab = perf.get("stability_score")
                if not isinstance(c, (int, float)) or c <= 0:
                    continue
                count = float(c)
                avg_val = float(avg) if isinstance(avg, (int, float)) else 0.0
                stab_val = float(stab) if isinstance(stab, (int, float)) else 0.0

                cell = agg[t][strat_name]
                cell["count"] += count
                cell["ws_avg"] += avg_val * count
                cell["ws_stab"] += stab_val * count

    if not agg or not all_strategies:
        console.print("집계할 theme/strategy 데이터가 없습니다.")
        return 0

    # 전략/테마 정렬
    strategies_sorted = sorted(all_strategies)
    themes_sorted = sorted(agg.keys())

    # min_samples 기준으로 테마 필터링 (적어도 한 전략에서 min_samples 이상)
    valid_themes: List[str] = []
    for theme in themes_sorted:
        has_enough = False
        for strat in strategies_sorted:
            cell = agg[theme].get(strat)
            if not cell:
                continue
            if cell["count"] >= float(min_samples):
                has_enough = True
                break
        if has_enough:
            valid_themes.append(theme)

    if not valid_themes:
        console.print("min_samples 조건을 만족하는 theme 이 없습니다.")
        return 0

    # 행렬 생성
    n_rows = len(valid_themes)
    n_cols = len(strategies_sorted)
    matrix = np.full((n_rows, n_cols), np.nan, dtype=float)

    # 집계 결과에서 mean_average_score / mean_stability_score 계산
    # 그리고 행렬에 metric 값 채우기
    for i, theme in enumerate(valid_themes):
        for j, strat in enumerate(strategies_sorted):
            cell = agg[theme].get(strat)
            if not cell:
                continue
            count = cell["count"]
            if count < float(min_samples):
                continue
            mean_avg = cell["ws_avg"] / count if count > 0 else 0.0
            mean_stab = cell["ws_stab"] / count if count > 0 else 0.0

            if metric == "count":
                value = count
            elif metric == "average_score":
                value = mean_avg
            else:  # stability_score
                value = mean_stab

            matrix[i, j] = value

    if np.all(np.isnan(matrix)):
        console.print("선택한 metric 과 min_samples 조건을 만족하는 셀 값이 없습니다.")
        return 0

    # 출력 디렉터리
    project_root = Path(__file__).resolve().parent
    out_dir = project_root / "reports" / "heatmaps"
    out_dir.mkdir(parents=True, exist_ok=True)

    png_path = out_dir / f"heatmap_{metric}.png"
    csv_path = out_dir / f"heatmap_{metric}.csv"

    # heatmap 그리기
    try:
        fig, ax = plt.subplots()
        im = ax.imshow(matrix, aspect="auto")

        ax.set_xticks(np.arange(n_cols))
        ax.set_yticks(np.arange(n_rows))
        ax.set_xticklabels(strategies_sorted)
        ax.set_yticklabels(valid_themes)

        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        ax.set_xlabel("Strategy")
        ax.set_ylabel("Theme")
        ax.set_title(f"Theme vs Strategy Heatmap (metric={metric})")

        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.set_ylabel(metric, rotation=-90, va="bottom")

        fig.tight_layout()
        fig.savefig(png_path)
        plt.close(fig)
    except Exception as e:  # pragma: no cover
        console.print(f"heatmap 생성 실패: {e}")

    # CSV 저장 (행: theme, 열: strategy)
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            import csv as _csv

            writer = _csv.writer(f)
            writer.writerow(["theme"] + strategies_sorted)
            for i, theme in enumerate(valid_themes):
                row = [theme]
                for j in range(n_cols):
                    val = matrix[i, j]
                    if np.isnan(val):
                        row.append("")
                    else:
                        row.append(f"{val:.6f}")
                writer.writerow(row)
    except Exception as e:  # pragma: no cover
        console.print(f"heatmap CSV 저장 실패: {e}")

    console.print("\nHeatmap 저장 파일:")
    console.print(f"- PNG: {png_path}")
    console.print(f"- CSV: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

