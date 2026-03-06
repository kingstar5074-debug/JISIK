from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rich.console import Console

from config import load_config


def _load_summary_reports(reports_dir: Path, console: Console):
    json_files = sorted(reports_dir.glob("strategy_summary_*.json"))
    if not json_files:
        console.print(f"summary JSON 파일을 찾을 수 없습니다: {reports_dir}")
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

        reports.append((path, data))

    if skipped:
        console.print(f"무시된 summary 파일 수: {skipped}")

    return reports


def main() -> int:
    console = Console()
    cfg = load_config()

    reports_dir = cfg.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    console.print("summary 조합 비교 리포트")
    console.print(f"리포트 디렉터리: {reports_dir}")

    loaded = _load_summary_reports(reports_dir, console)
    if not loaded:
        return 0

    # 필터 (summary 레벨)
    import os

    def _get_list(name: str) -> list[str]:
        raw = os.getenv(name)
        if not raw:
            return []
        items: list[str] = []
        for part in raw.split(","):
            s = part.strip().lower()
            if s:
                items.append(s)
        # 중복 제거
        seen: set[str] = set()
        out: list[str] = []
        for s in items:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    filter_tags = _get_list("SUMMARY_OF_SUMMARIES_FILTER_TAGS")
    filter_provider = (os.getenv("SUMMARY_OF_SUMMARIES_FILTER_PROVIDER") or "").strip().lower()
    filter_session = (os.getenv("SUMMARY_OF_SUMMARIES_FILTER_SESSION") or "").strip().lower()

    console.print("적용 필터(2차 요약):")
    console.print(f"- tags: {', '.join(filter_tags) if filter_tags else '(없음)'}")
    console.print(f"- provider: {filter_provider or '(없음)'}")
    console.print(f"- session: {filter_session or '(없음)'}")

    # used_filters 기반 필터링
    filtered = []
    skipped_by_filter = 0
    for path, data in loaded:
        used_filters = data.get("used_filters") or {}
        tags = [str(t).lower() for t in (used_filters.get("tags") or [])]
        prov = str(used_filters.get("provider") or "").lower()
        sess = str(used_filters.get("session") or "").lower()

        if filter_provider and prov != filter_provider:
            skipped_by_filter += 1
            continue
        if filter_session and sess != filter_session:
            skipped_by_filter += 1
            continue
        if filter_tags and not all(t in tags for t in filter_tags):
            skipped_by_filter += 1
            continue

        filtered.append((path, data))

    if not filtered:
        console.print("필터 조건을 만족하는 summary 리포트가 없습니다.")
        return 0

    total_summary_files = len(loaded)
    used_summary_files = len(filtered)

    console.print(f"\n읽은 summary 파일 수: {total_summary_files}")
    console.print(f"사용된 summary 파일 수: {used_summary_files}")
    console.print(f"필터로 제외된 summary 파일 수: {skipped_by_filter}")

    profile_names = ["balanced", "aggressive", "conservative"]

    # 전략별 누적 통계
    avg_avg_scores: Dict[str, list[float]] = {n: [] for n in profile_names}
    avg_win_rates: Dict[str, list[float]] = {n: [] for n in profile_names}
    avg_ret_counts: Dict[str, list[float]] = {n: [] for n in profile_names}
    stab_scores: Dict[str, list[float]] = {n: [] for n in profile_names}
    summary_level_wins: Dict[str, int] = {n: 0 for n in profile_names}

    for path, data in filtered:
        strategies = data.get("strategies") or {}
        # per-summary 집계
        per_summary_scores: Dict[str, float] = {}
        for n in profile_names:
            s = strategies.get(n) or {}
            avg_score_mean = s.get("average_score_mean")
            win_rate = s.get("best_strategy_win_rate")
            ret_count = s.get("average_returned_count")
            stability_score = s.get("stability_score")

            if isinstance(avg_score_mean, (int, float)):
                avg_avg_scores[n].append(float(avg_score_mean))
                per_summary_scores[n] = float(avg_score_mean)
            if isinstance(win_rate, (int, float)):
                avg_win_rates[n].append(float(win_rate))
            if isinstance(ret_count, (int, float)):
                avg_ret_counts[n].append(float(ret_count))
            if isinstance(stability_score, (int, float)):
                stab_scores[n].append(float(stability_score))

        # summary 레벨 winner (average_score_mean 기준)
        if per_summary_scores:
            best_name = max(per_summary_scores.items(), key=lambda kv: kv[1])[0]
            summary_level_wins[best_name] += 1

    summaries: Dict[str, Dict] = {}
    for n in profile_names:
        runs = len(avg_avg_scores[n])
        avg_score_mean = mean(avg_avg_scores[n]) if avg_avg_scores[n] else 0.0
        avg_win_rate = mean(avg_win_rates[n]) if avg_win_rates[n] else 0.0
        avg_ret = mean(avg_ret_counts[n]) if avg_ret_counts[n] else 0.0
        avg_stability_score = mean(stab_scores[n]) if stab_scores[n] else 0.0
        wins = summary_level_wins.get(n, 0)
        win_rate_summary = (wins / used_summary_files * 100.0) if used_summary_files > 0 else 0.0

        console.print(
            f"\n[{n}]\n"
            f"- 평균 average_score_mean: {avg_score_mean:.2f}\n"
            f"- 평균 best_strategy_win_rate: {avg_win_rate:.2f}%\n"
            f"- 평균 average_returned_count: {avg_ret:.2f}\n"
            f"- 평균 stability_score: {avg_stability_score:.2f}\n"
            f"- summary 레벨 승리 횟수: {wins}\n"
            f"- summary 레벨 승리 비율: {win_rate_summary:.1f}%"
        )

        summaries[n] = {
            "avg_average_score_mean": avg_score_mean,
            "avg_best_strategy_win_rate": avg_win_rate,
            "avg_average_returned_count": avg_ret,
            "avg_stability_score": avg_stability_score,
            "summary_level_win_count": wins,
            "summary_level_win_rate": win_rate_summary,
        }

    # summary 레벨 최다 winner
    if any(summary_level_wins.values()):
        best_overall = max(summary_level_wins.items(), key=lambda kv: kv[1])
        console.print(
            f"\nsummary 레벨 최다 winner: {best_overall[0]} "
            f"({best_overall[1]} / {used_summary_files})"
        )
    else:
        best_overall = None
        console.print("\nsummary 레벨 최다 winner: (없음)")

    # 결과 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_json_path = reports_dir / f"summary_compare_{ts}.json"
    summary_csv_path = reports_dir / f"summary_compare_{ts}.csv"
    png_avg_path = reports_dir / f"summary_compare_avg_score_{ts}.png"
    png_win_path = reports_dir / f"summary_compare_win_rate_{ts}.png"
    png_stab_path = reports_dir / f"summary_compare_stability_score_{ts}.png"

    summary_report = {
        "timestamp": ts,
        "total_summary_files": total_summary_files,
        "used_summary_files": used_summary_files,
        "skipped_by_filter": skipped_by_filter,
        "used_filters": {
            "tags": filter_tags,
            "provider": filter_provider or None,
            "session": filter_session or None,
        },
        "strategies": summaries,
        "summary_level_most_frequent_winner": {
            "strategy": best_overall[0],
            "wins": best_overall[1],
            "win_rate": (
                best_overall[1] / used_summary_files * 100.0
                if best_overall and used_summary_files > 0
                else 0.0
            ),
        }
        if best_overall
        else None,
    }

    try:
        summary_json_path.write_text(
            json.dumps(summary_report, indent=2), encoding="utf-8"
        )
    except Exception as e:  # pragma: no cover
        console.print(f"summary 비교 JSON 저장 실패: {e}")

    # CSV 저장
    try:
        with summary_csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "strategy",
                    "avg_average_score_mean",
                    "avg_best_strategy_win_rate",
                    "avg_average_returned_count",
                    "avg_stability_score",
                    "summary_level_win_count",
                    "summary_level_win_rate",
                ]
            )
            for n in profile_names:
                s = summaries.get(n) or {}
                writer.writerow(
                    [
                        n,
                        f"{s.get('avg_average_score_mean', 0.0):.6f}",
                        f"{s.get('avg_best_strategy_win_rate', 0.0):.6f}",
                        f"{s.get('avg_average_returned_count', 0.0):.6f}",
                        f"{s.get('avg_stability_score', 0.0):.6f}",
                        s.get("summary_level_win_count", 0),
                        f"{s.get('summary_level_win_rate', 0.0):.2f}",
                    ]
                )
    except Exception as e:  # pragma: no cover
        console.print(f"summary 비교 CSV 저장 실패: {e}")

    # 차트 (avg score / win rate / stability_score)
    try:
        names = profile_names
        avg_scores_chart = [
            summaries[n]["avg_average_score_mean"] if n in summaries else 0.0
            for n in names
        ]
        fig, ax = plt.subplots()
        ax.bar(names, avg_scores_chart)
        ax.set_title("Average of average_score_mean by strategy (summary compare)")
        ax.set_xlabel("Strategy")
        ax.set_ylabel("Average of average_score_mean")
        fig.tight_layout()
        fig.savefig(png_avg_path)
        plt.close(fig)

        win_rates_chart = [
            summaries[n]["avg_best_strategy_win_rate"] if n in summaries else 0.0
            for n in names
        ]
        fig2, ax2 = plt.subplots()
        ax2.bar(names, win_rates_chart)
        ax2.set_title("Average of best_strategy_win_rate by strategy (summary compare)")
        ax2.set_xlabel("Strategy")
        ax2.set_ylabel("Average win rate (%)")
        fig2.tight_layout()
        fig2.savefig(png_win_path)
        plt.close(fig2)

        stab_chart = [
            summaries[n]["avg_stability_score"] if n in summaries else 0.0
            for n in names
        ]
        fig3, ax3 = plt.subplots()
        ax3.bar(names, stab_chart)
        ax3.set_title("Average of stability_score by strategy (summary compare)")
        ax3.set_xlabel("Strategy")
        ax3.set_ylabel("Average stability_score")
        fig3.tight_layout()
        fig3.savefig(png_stab_path)
        plt.close(fig3)
    except Exception as e:  # pragma: no cover
        console.print(f"summary 비교 차트 생성 실패: {e}")

    console.print("\nsummary 비교 저장 파일:")
    console.print(f"- JSON: {summary_json_path}")
    console.print(f"- CSV: {summary_csv_path}")
    console.print(f"- 차트: {png_avg_path}")
    console.print(f"- 차트: {png_win_path}")
    console.print(f"- 차트: {png_stab_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

