from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, variance, stdev
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rich.console import Console

from config import load_config


def _load_reports(reports_dir: Path, console: Console):
    json_files = sorted(reports_dir.glob("strategy_compare_*.json"))
    if not json_files:
        console.print(f"리포트 JSON 파일을 찾을 수 없습니다: {reports_dir}")
        return []

    reports = []
    skipped = 0
    for path in json_files:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            skipped += 1
            continue

        # 최소한의 구조 검증
        if not isinstance(data, dict) or "strategies" not in data:
            skipped += 1
            continue

        strategies = data.get("strategies")
        if not isinstance(strategies, dict):
            skipped += 1
            continue

        reports.append((path, data))

    if skipped:
        console.print(f"무시된 파일 수: {skipped}")

    return reports


def main() -> int:
    console = Console()
    cfg = load_config()

    reports_dir = cfg.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    console.print("전략 누적 요약 리포트")
    console.print(f"리포트 디렉터리: {reports_dir}")

    loaded = _load_reports(reports_dir, console)
    if not loaded:
        return 0

    profile_names = ["balanced", "aggressive", "conservative"]

    # 누적 통계
    returned_counts: Dict[str, List[float]] = defaultdict(list)
    passed_counts: Dict[str, List[float]] = defaultdict(list)
    avg_scores: Dict[str, List[float]] = defaultdict(list)
    win_counts: Dict[str, int] = defaultdict(int)
    top_symbol_freq: Dict[str, Counter] = {
        name: Counter() for name in profile_names
    }

    total_reports = len(loaded)
    skipped_reports_for_stats = 0

    for path, data in loaded:
        strategies = data.get("strategies") or {}

        # per-report best strategy 결정
        best_name: Optional[str] = None
        best_score: Optional[float] = None

        for name in profile_names:
            s_data = strategies.get(name)
            if not isinstance(s_data, dict):
                continue

            rc = s_data.get("returned_count")
            pc = s_data.get("passed_filters")
            ascore = s_data.get("average_score")

            if isinstance(rc, (int, float)):
                returned_counts[name].append(float(rc))
            if isinstance(pc, (int, float)):
                passed_counts[name].append(float(pc))
            if isinstance(ascore, (int, float)):
                avg_scores[name].append(float(ascore))

            # top_symbols 빈도 집계
            top_syms = s_data.get("top_symbols") or []
            if isinstance(top_syms, list):
                for entry in top_syms:
                    if not isinstance(entry, dict):
                        continue
                    sym = entry.get("symbol")
                    if isinstance(sym, str) and sym.strip():
                        top_symbol_freq[name][sym.strip().upper()] += 1

        # best strategy by average_score (한 리포트당 1승, 동점 시 첫 번째만)
        per_report_scores: Dict[str, float] = {}
        for name in profile_names:
            s_data = strategies.get(name)
            if not isinstance(s_data, dict):
                continue
            ascore = s_data.get("average_score")
            if isinstance(ascore, (int, float)):
                per_report_scores[name] = float(ascore)

        if per_report_scores:
            # 첫 번째 최대값 하나만 승리로 처리
            best_name = max(per_report_scores.items(), key=lambda kv: kv[1])[0]
            win_counts[best_name] += 1
        else:
            skipped_reports_for_stats += 1

    valid_reports = total_reports - skipped_reports_for_stats

    console.print(f"\n유효 리포트 수: {valid_reports}")
    console.print(f"통계에서 제외된 리포트 수: {skipped_reports_for_stats}")

    summaries: Dict[str, Dict] = {}

    for name in profile_names:
        scores = avg_scores[name]
        runs = len(returned_counts[name])
        avg_ret = mean(returned_counts[name]) if returned_counts[name] else 0.0
        avg_pass = mean(passed_counts[name]) if passed_counts[name] else 0.0
        average_score_mean = mean(scores) if scores else 0.0

        if len(scores) >= 2:
            score_variance = variance(scores)
            score_std_dev = stdev(scores)
        else:
            score_variance = 0.0
            score_std_dev = 0.0

        if scores:
            score_range = max(scores) - min(scores)
        else:
            score_range = 0.0

        stability_score = average_score_mean / (1.0 + score_std_dev)

        wins = win_counts.get(name, 0)
        win_rate = (wins / valid_reports * 100.0) if valid_reports > 0 else 0.0

        console.print(f"\n[{name}]")
        console.print(f"- 실행 수: {runs}")
        console.print(f"- 평균 returned_count: {avg_ret:.2f}")
        console.print(f"- 평균 passed_filters: {avg_pass:.2f}")
        console.print(f"- 평균 average_score: {average_score_mean:.2f}")
        console.print(f"- score_variance: {score_variance:.2f}")
        console.print(f"- score_std_dev: {score_std_dev:.2f}")
        console.print(f"- score_range: {score_range:.2f}")
        console.print(f"- stability_score: {stability_score:.2f}")
        console.print(f"- 최고 점수 전략 횟수: {wins}")
        console.print(f"- 최고 점수 전략 비율: {win_rate:.1f}%")

        # 상위 빈도 종목
        freq = top_symbol_freq[name]
        if freq:
            console.print(f"[{name} 상위 빈도 종목]")
            for sym, cnt in freq.most_common(10):
                console.print(f"- {sym}: {cnt}회")
        else:
            console.print(f"[{name} 상위 빈도 종목] (없음)")

        summaries[name] = {
            "number_of_runs": runs,
            "average_returned_count": avg_ret,
            "average_passed_filters": avg_pass,
            "average_score_mean": average_score_mean,
            "score_variance": score_variance,
            "score_std_dev": score_std_dev,
            "score_range": score_range,
            "stability_score": stability_score,
            "best_strategy_win_count": wins,
            "best_strategy_win_rate": win_rate,
        }

    # 가장 자주 승리한 전략
    if win_counts:
        best_overall = max(win_counts.items(), key=lambda kv: kv[1])
        console.print(
            f"\n가장 자주 최고 점수였던 전략: {best_overall[0]} "
            f"({best_overall[1]} / {valid_reports})"
        )
    else:
        best_overall = None
        console.print("\n가장 자주 최고 점수였던 전략: (없음)")

    # 결과 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"strategy_summary_{ts}.json"
    csv_path = reports_dir / f"strategy_summary_{ts}.csv"
    png_avg_path = reports_dir / f"strategy_summary_avg_score_{ts}.png"
    png_win_path = reports_dir / f"strategy_summary_win_rate_{ts}.png"
    png_stab_path = reports_dir / f"strategy_summary_stability_score_{ts}.png"

    summary_report = {
        "timestamp": ts,
        "total_reports": total_reports,
        "valid_reports": valid_reports,
        "skipped_reports": skipped_reports_for_stats,
        "strategies": summaries,
        "most_frequent_winner": {
            "strategy": best_overall[0],
            "wins": best_overall[1],
            "win_rate": (
                best_overall[1] / valid_reports * 100.0 if best_overall and valid_reports > 0 else 0.0
            ),
        }
        if best_overall
        else None,
        "top_symbol_frequency": {
            name: dict(top_symbol_freq[name].most_common(50)) for name in profile_names
        },
    }

    try:
        json_path.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")
    except Exception as e:  # pragma: no cover
        console.print(f"요약 JSON 저장 실패: {e}")

    # CSV 저장 (전략별 한 줄)
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "strategy",
                    "number_of_runs",
                    "average_returned_count",
                    "average_passed_filters",
                    "average_score_mean",
                    "score_variance",
                    "score_std_dev",
                    "score_range",
                    "stability_score",
                    "best_strategy_win_count",
                    "best_strategy_win_rate",
                ]
            )
            for name in profile_names:
                s = summaries.get(name) or {}
                writer.writerow(
                    [
                        name,
                        s.get("number_of_runs", 0),
                        f"{s.get('average_returned_count', 0.0):.6f}",
                        f"{s.get('average_passed_filters', 0.0):.6f}",
                        f"{s.get('average_score_mean', 0.0):.6f}",
                        f"{s.get('score_variance', 0.0):.6f}",
                        f"{s.get('score_std_dev', 0.0):.6f}",
                        f"{s.get('score_range', 0.0):.6f}",
                        f"{s.get('stability_score', 0.0):.6f}",
                        s.get("best_strategy_win_count", 0),
                        f"{s.get('best_strategy_win_rate', 0.0):.2f}",
                    ]
                )
    except Exception as e:  # pragma: no cover
        console.print(f"요약 CSV 저장 실패: {e}")

    # 시각화 (평균 score / win_rate / stability_score)
    try:
        names = profile_names
        avg_scores_chart = [
            summaries[n]["average_score_mean"] if n in summaries else 0.0 for n in names
        ]
        fig, ax = plt.subplots()
        ax.bar(names, avg_scores_chart)
        ax.set_title("Average score by strategy (summary)")
        ax.set_xlabel("Strategy")
        ax.set_ylabel("Average score")
        fig.tight_layout()
        fig.savefig(png_avg_path)
        plt.close(fig)

        win_rates_chart = [
            summaries[n]["best_strategy_win_rate"] if n in summaries else 0.0
            for n in names
        ]
        fig2, ax2 = plt.subplots()
        ax2.bar(names, win_rates_chart)
        ax2.set_title("Win rate by strategy (summary)")
        ax2.set_xlabel("Strategy")
        ax2.set_ylabel("Win rate (%)")
        fig2.tight_layout()
        fig2.savefig(png_win_path)
        plt.close(fig2)

        stability_chart = [
            summaries[n]["stability_score"] if n in summaries else 0.0
            for n in names
        ]
        fig3, ax3 = plt.subplots()
        ax3.bar(names, stability_chart)
        ax3.set_title("Stability score by strategy (summary)")
        ax3.set_xlabel("Strategy")
        ax3.set_ylabel("Stability score")
        fig3.tight_layout()
        fig3.savefig(png_stab_path)
        plt.close(fig3)
    except Exception as e:  # pragma: no cover
        console.print(f"요약 차트 생성 실패: {e}")

    console.print("\n요약 저장 파일:")
    console.print(f"- JSON: {json_path}")
    console.print(f"- CSV: {csv_path}")
    console.print(f"- 차트: {png_avg_path}")
    console.print(f"- 차트: {png_win_path}")
    console.print(f"- 차트: {png_stab_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

