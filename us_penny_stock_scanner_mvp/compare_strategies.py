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
from scanner.market_hours import MarketClock
from scanner.providers.factory import get_market_data_provider
from scanner.scanner import PennyStockScanner, ScanResult
from scanner.strategy_profiles import get_strategy_profile
from scanner.theme_tagger import detect_theme_tags
from universe.generated_universe import GeneratedUniverseProvider
from universe.watchlist_universe import WatchlistUniverseProvider
from utils.logger import get_logger

log = get_logger(__name__)


def _load_universe_and_provider():
    cfg = load_config()
    console = Console()

    if cfg.scan_mode not in {"watchlist", "universe"}:
        console.print(
            f"지원하지 않는 SCAN_MODE 값입니다: '{cfg.scan_mode}'. "
            "watchlist 또는 universe 중 하나여야 합니다."
        )
        raise SystemExit(1)

    # universe
    if cfg.scan_mode == "universe":
        universe = GeneratedUniverseProvider(cfg.universe_file)
    else:
        universe = WatchlistUniverseProvider(cfg.tickers_file)

    try:
        tickers = universe.load_symbols()
    except FileNotFoundError as e:
        console.print(str(e))
        raise SystemExit(1)

    if not tickers:
        console.print("스캔할 티커가 없습니다.")
        raise SystemExit(1)

    # provider
    try:
        provider = get_market_data_provider(cfg)
    except (RuntimeError, ValueError) as e:
        console.print(str(e))
        raise SystemExit(1)

    return cfg, console, tickers, provider


def _run_for_profile(
    profile_name: str,
    cfg,
    quotes,
    session: str,
    console: Console,
    clock: MarketClock,
) -> ScanResult:
    try:
        profile = get_strategy_profile(profile_name, cfg.strategy_profiles_file)
    except ValueError as e:
        console.print(str(e))
        raise SystemExit(1)

    scanner = PennyStockScanner(
        provider=None,  # scan_with_quotes 에서는 provider 를 사용하지 않음
        filters=cfg.filters,
        strategy_profile=profile,
        clock=clock,
        top_results=cfg.top_results,
    )

    log.info("Running compare for profile=%s", profile.name)
    return scanner.scan_with_quotes(quotes, current_session=session)


def main() -> int:
    cfg, console, tickers, provider = _load_universe_and_provider()
    clock = MarketClock()
    dt_et = clock.now_et()
    session = clock.session_of(dt_et)

    console.print("전략 비교 리포트")
    console.print(f"입력 종목 수: {len(tickers)}")
    console.print(f"세션(ET): {session}")
    console.print(f"데이터 provider: {cfg.data_provider}")
    console.print(f"전략 프로파일 파일: {cfg.strategy_profiles_file.name}")

    # 한 번만 quotes 조회
    # normalize symbols
    symbol_list: list[str] = []
    for raw in tickers:
        s = raw.strip().upper()
        if not s:
            continue
        symbol_list.append(s)

    quotes = provider.fetch_quotes(symbols=symbol_list, market_session=session)

    profile_names = ["balanced", "aggressive", "conservative"]
    results: Dict[str, ScanResult] = {}

    for name in profile_names:
        res = _run_for_profile(name, cfg, quotes, session, console, clock)
        results[name] = res

    # 전략별 요약 출력
    top_n = 5
    symbol_sets: Dict[str, set] = {}
    summaries: Dict[str, Dict] = {}
    theme_frequency_global: Dict[str, int] = {}
    for pname in profile_names:
        res = results.get(pname)
        if res is None:
            continue

        console.print(f"\n[{pname}]")
        console.print(
            f"통과 {res.filter_report.passed_filters} / 출력 {res.filter_report.returned_count}"
        )

        if res.scores:
            avg_score = mean(s.total_score for s in res.scores)
            console.print(f"평균 score: {avg_score:.2f}")
        else:
            avg_score = None
            console.print("평균 score: N/A")

        console.print(f"상위 {min(top_n, len(res.scores))} 종목:")
        top_list = []
        for s in res.scores[:top_n]:
            tags = detect_theme_tags(s.symbol)
            console.print(f"- {s.symbol} {s.total_score:.2f} (themes: {', '.join(tags)})")
            top_list.append(
                {
                    "symbol": s.symbol,
                    "score": s.total_score,
                    "theme_tags": tags,
                }
            )
            for t in tags:
                theme_frequency_global[t] = theme_frequency_global.get(t, 0) + 1

        symbol_sets[pname] = {q.symbol for q in res.matched}

        summaries[pname] = {
            "passed_filters": res.filter_report.passed_filters,
            "returned_count": res.filter_report.returned_count,
            "average_score": avg_score,
            "top_symbols": top_list,
        }

    bal = symbol_sets.get("balanced", set())
    agg = symbol_sets.get("aggressive", set())
    cons = symbol_sets.get("conservative", set())

    common = bal & agg & cons
    agg_only = agg - (bal | cons)
    cons_only = cons - (bal | agg)
    bal_only = bal - (agg | cons)

    console.print("\n공통 종목:")
    if common:
        for s in sorted(common):
            console.print(f"- {s}")
    else:
        console.print("- (없음)")

    console.print("\naggressive 전용 종목:")
    if agg_only:
        for s in sorted(agg_only):
            console.print(f"- {s}")
    else:
        console.print("- (없음)")

    console.print("\nconservative 전용 종목:")
    if cons_only:
        for s in sorted(cons_only):
            console.print(f"- {s}")
    else:
        console.print("- (없음)")

    console.print("\nbalanced 전용 종목:")
    if bal_only:
        for s in sorted(bal_only):
            console.print(f"- {s}")
    else:
        console.print("- (없음)")

    # 결과 저장
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = cfg.reports_dir / f"strategy_compare_{ts}.json"
    csv_path = cfg.reports_dir / f"strategy_compare_{ts}.csv"
    png_counts_path = cfg.reports_dir / f"strategy_compare_counts_{ts}.png"
    png_avg_path = cfg.reports_dir / f"strategy_compare_avg_score_{ts}.png"

    report = {
        "timestamp": ts,
        "provider": cfg.data_provider,
        "session": session,
        "scan_mode": cfg.scan_mode,
        "input_symbol_count": len(symbol_list),
        "strategy_profiles_file": cfg.strategy_profiles_file.name,
        "strategies": summaries,
        "intersections": {
            "common_symbols": sorted(common),
            "balanced_only": sorted(bal_only),
            "aggressive_only": sorted(agg_only),
            "conservative_only": sorted(cons_only),
        },
        "theme_frequency": theme_frequency_global,
    }

    try:
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception as e:  # pragma: no cover
        console.print(f"JSON 리포트 저장 실패: {e}")

    # CSV 저장 (long format: strategy/symbol/score/rank/metrics)
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "strategy",
                    "symbol",
                    "score",
                    "rank",
                    "session",
                    "current_price",
                    "percent_change",
                    "gap_percent",
                    "intraday_change_percent",
                    "volume_ratio",
                    "average_volume",
                    "dollar_volume",
                    "theme_tags",
                ]
            )
            for pname in profile_names:
                res = results.get(pname)
                if res is None:
                    continue
                qmap = {q.symbol: q for q in res.matched}
                for rank, s in enumerate(res.scores, start=1):
                    q = qmap.get(s.symbol)
                    tags = detect_theme_tags(s.symbol)
                    writer.writerow(
                        [
                            pname,
                            s.symbol,
                            f"{s.total_score:.6f}",
                            rank,
                            res.current_session,
                            "" if q is None or q.current_price is None else q.current_price,
                            "" if q is None or q.percent_change is None else q.percent_change,
                            "" if q is None or q.gap_percent is None else q.gap_percent,
                            "" if q is None or q.intraday_change_percent is None else q.intraday_change_percent,
                            "" if q is None or q.volume_ratio is None else q.volume_ratio,
                            "" if q is None or q.average_volume is None else q.average_volume,
                            "" if q is None or q.dollar_volume is None else q.dollar_volume,
                            ",".join(tags),
                        ]
                    )
    except Exception as e:  # pragma: no cover
        console.print(f"CSV 리포트 저장 실패: {e}")

    # 시각화 (bar chart)
    try:
        # counts chart
        names = profile_names
        counts = [
            results[n].filter_report.returned_count for n in names if n in results
        ]
        fig, ax = plt.subplots()
        ax.bar(names, counts)
        ax.set_title("Returned count by strategy")
        ax.set_xlabel("Strategy")
        ax.set_ylabel("Returned count")
        fig.tight_layout()
        fig.savefig(png_counts_path)
        plt.close(fig)

        # avg score chart
        avg_scores = []
        for n in names:
            res = results.get(n)
            if res and res.scores:
                avg_scores.append(mean(s.total_score for s in res.scores))
            else:
                avg_scores.append(0.0)
        fig2, ax2 = plt.subplots()
        ax2.bar(names, avg_scores)
        ax2.set_title("Average score by strategy")
        ax2.set_xlabel("Strategy")
        ax2.set_ylabel("Average score")
        fig2.tight_layout()
        fig2.savefig(png_avg_path)
        plt.close(fig2)
    except Exception as e:  # pragma: no cover
        console.print(f"차트 생성 실패: {e}")

    console.print("\n저장 파일:")
    console.print(f"- JSON: {json_path}")
    console.print(f"- CSV: {csv_path}")
    console.print(f"- 차트: {png_counts_path}")
    console.print(f"- 차트: {png_avg_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

