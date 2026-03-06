from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rich.console import Console

from config import load_config


def _load_compare_reports(reports_dir: Path, console: Console):
    json_files = sorted(reports_dir.glob("strategy_compare_*.json"))
    if not json_files:
        console.print(f"strategy_compare_*.json 파일을 찾을 수 없습니다: {reports_dir}")
        return []

    reports = []
    skipped = 0
    for path in json_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue

        if not isinstance(data, dict) or "strategies" not in data:
            skipped += 1
            continue

        strategies = data.get("strategies")
        if not isinstance(strategies, dict):
            skipped += 1
            continue

        reports.append((path, data))

    if skipped:
        console.print(f"무시된 compare 리포트 수: {skipped}")

    return reports


def main() -> int:
    console = Console()
    cfg = load_config()

    reports_dir = cfg.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    theme = (cfg.theme_advisor_theme or "").strip().lower()
    provider_filter = (cfg.theme_advisor_provider or "").strip().lower()
    session_filter = (cfg.theme_advisor_session or "").strip().lower()
    tag_filter = cfg.theme_advisor_tags or []
    min_count = cfg.theme_advisor_min_count

    console.print("Theme Strategy Advisor")
    console.print(f"theme: {theme or '(설정 없음)'}")
    console.print(f"provider filter: {provider_filter or '(없음)'}")
    console.print(f"session filter: {session_filter or '(없음)'}")
    console.print(
        "tag filter: "
        + (", ".join(tag_filter) if tag_filter else "(없음)")
    )
    console.print(f"min_count: {min_count}")
    console.print(f"REPORTS_DIR: {reports_dir}")

    if not theme:
        console.print("THEME_ADVISOR_THEME 이 설정되지 않았습니다. .env 를 확인하세요.")
        return 0

    loaded = _load_compare_reports(reports_dir, console)
    if not loaded:
        return 0

    profile_names = ["balanced", "aggressive", "conservative"]

    # 필터 적용 (provider / session / tags)
    filtered = []
    for path, data in loaded:
        prov = str(data.get("provider") or "").strip().lower()
        sess = str(data.get("session") or "").strip().lower()
        tags_raw = data.get("environment_tags") or []
        tags = [str(t).strip().lower() for t in tags_raw if isinstance(t, str)]

        if provider_filter and prov != provider_filter:
            continue
        if session_filter and sess != session_filter:
            continue
        if tag_filter and not all(t in tags for t in tag_filter):
            continue

        filtered.append((path, data))

    used_reports = len(filtered)
    console.print(f"used compare reports: {used_reports}")

    if not filtered:
        console.print("필터 조건을 만족하는 compare 리포트가 없습니다.")
        return 0

    # 전략별 theme score 수집
    theme_scores: Dict[str, List[float]] = {name: [] for name in profile_names}

    for path, data in filtered:
        strategies = data.get("strategies") or {}
        for name in profile_names:
            s_data = strategies.get(name) or {}
            top_syms = s_data.get("top_symbols") or []
            if not isinstance(top_syms, list):
                continue
            for entry in top_syms:
                if not isinstance(entry, dict):
                    continue
                score = entry.get("score")
                if not isinstance(score, (int, float)):
                    continue
                tags = entry.get("theme_tags") or []
                if not isinstance(tags, list):
                    continue
                tags_norm = [str(t).strip().lower() for t in tags if isinstance(t, str)]
                if theme in tags_norm:
                    theme_scores[name].append(float(score))

    # 전략별 통계 계산
    results: Dict[str, Dict] = {}
    best_by_avg_name = None
    best_by_avg_score = None

    for name in profile_names:
        scores = theme_scores[name]
        cnt = len(scores)
        if scores:
            avg_score = mean(scores)
            if len(scores) >= 2:
                std_dev = stdev(scores)
            else:
                std_dev = 0.0
        else:
            cnt = 0
            avg_score = 0.0
            std_dev = 0.0
        stability = avg_score / (1.0 + std_dev)

        console.print(f"\n[{name}]")
        console.print(f"count={cnt}")
        console.print(f"average_score={avg_score:.2f}")
        console.print(f"score_std_dev={std_dev:.2f}")
        console.print(f"stability_score={stability:.2f}")

        results[name] = {
            "count": cnt,
            "average_score": avg_score,
            "score_std_dev": std_dev,
            "stability_score": stability,
        }

        if cnt > 0:
            if best_by_avg_score is None or avg_score > best_by_avg_score:
                best_by_avg_score = avg_score
                best_by_avg_name = name

    # 추천 전략 (stability 기반)
    candidates = []
    for name in profile_names:
        info = results[name]
        if info["count"] >= min_count:
            candidates.append(
                (
                    name,
                    info["stability_score"],
                    info["average_score"],
                    info["count"],
                )
            )

    if candidates:
        # stability_score, average_score, count 순으로 최대값
        recommended_name = max(
            candidates,
            key=lambda x: (x[1], x[2], x[3]),
        )[0]
    else:
        recommended_name = None

    console.print("")
    console.print(
        f"best_by_average_score: {best_by_avg_name or '(없음)'}"
    )
    if recommended_name:
        console.print(
            f"recommended_by_stability: {recommended_name}"
        )
    else:
        console.print("recommended_by_stability: 추천 보류 (표본 부족)")

    # 결과 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"theme_strategy_advisor_{ts}.json"
    csv_path = reports_dir / f"theme_strategy_advisor_{ts}.csv"
    png_path = reports_dir / f"theme_strategy_advisor_{ts}.png"

    summary = {
        "timestamp": ts,
        "theme": theme,
        "used_filters": {
            "provider": provider_filter or None,
            "session": session_filter or None,
            "tags": tag_filter,
            "min_count": min_count,
        },
        "used_compare_reports": used_reports,
        "strategies": results,
        "best_by_average_score": best_by_avg_name,
        "recommended_by_stability": recommended_name,
    }

    try:
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception as e:  # pragma: no cover
        console.print(f"Theme advisor JSON 저장 실패: {e}")

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "strategy",
                    "count",
                    "average_score",
                    "score_std_dev",
                    "stability_score",
                ]
            )
            for name in profile_names:
                info = results.get(name) or {}
                writer.writerow(
                    [
                        name,
                        info.get("count", 0),
                        f"{info.get('average_score', 0.0):.6f}",
                        f"{info.get('score_std_dev', 0.0):.6f}",
                        f"{info.get('stability_score', 0.0):.6f}",
                    ]
                )
    except Exception as e:  # pragma: no cover
        console.print(f"Theme advisor CSV 저장 실패: {e}")

    # 차트 (stability_score by strategy)
    try:
        names = profile_names
        stab_values = [
            results[n]["stability_score"] if n in results else 0.0 for n in names
        ]
        fig, ax = plt.subplots()
        ax.bar(names, stab_values)
        ax.set_title(f"Stability by strategy (theme={theme})")
        ax.set_xlabel("Strategy")
        ax.set_ylabel("Stability score")
        fig.tight_layout()
        fig.savefig(png_path)
        plt.close(fig)
    except Exception as e:  # pragma: no cover
        console.print(f"Theme advisor 차트 생성 실패: {e}")

    console.print("\nTheme advisor 저장 파일:")
    console.print(f"- JSON: {json_path}")
    console.print(f"- CSV: {csv_path}")
    console.print(f"- 차트: {png_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

