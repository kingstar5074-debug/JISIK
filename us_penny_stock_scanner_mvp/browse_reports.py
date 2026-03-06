from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from config import load_config


def _safe_get(d: dict, key: str, default=None):
    v = d.get(key, default)
    return v if v is not None else default


def main() -> int:
    console = Console()
    cfg = load_config()

    reports_dir = cfg.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    console.print("리포트 브라우저")
    console.print(f"리포트 디렉터리: {reports_dir}")

    compare_files = sorted(reports_dir.glob("strategy_compare_*.json"))
    summary_files = sorted(reports_dir.glob("strategy_summary_*.json"))
    summary_compare_files = sorted(reports_dir.glob("summary_compare_*.json"))

    console.print("\n[compare 리포트 목록]")
    if not compare_files:
        console.print("(없음)")
    else:
        for idx, path in enumerate(compare_files, start=1):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                console.print(f"{idx}. {path.name} (읽기 실패)")
                continue

            provider = str(_safe_get(data, "provider", "") or "")
            session = str(_safe_get(data, "session", "") or "")
            created_at = _safe_get(data, "created_at", _safe_get(data, "timestamp", ""))
            input_count = _safe_get(data, "input_symbol_count", 0)
            tags = _safe_get(data, "environment_tags", []) or []
            tag_str = ", ".join(tags) if tags else "(없음)"

            console.print(f"{idx}. {path.name}")
            console.print(
                f"   - created_at: {created_at} / provider: {provider} / session: {session}"
            )
            console.print(
                f"   - input_symbol_count: {input_count} / tags: {tag_str}"
            )

    console.print("\n[summary 리포트 목록]")
    if not summary_files:
        console.print("(없음)")
    else:
        for idx, path in enumerate(summary_files, start=1):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                console.print(f"{idx}. {path.name} (읽기 실패)")
                continue

            ts = _safe_get(data, "timestamp", "")
            valid = _safe_get(data, "valid_reports", 0)
            mf = data.get("most_frequent_winner") or {}
            winner = mf.get("strategy") or "(없음)"
            win_rate = mf.get("win_rate")
            win_info = (
                f"{winner} ({win_rate:.1f}%)"
                if isinstance(win_rate, (int, float))
                else winner
            )

            # avg stability leader 계산
            strategies = data.get("strategies") or {}
            profile_names = ["balanced", "aggressive", "conservative"]
            best_stab_name = None
            best_stab_value = None
            for name in profile_names:
                s = strategies.get(name) or {}
                stab = s.get("stability_score")
                if isinstance(stab, (int, float)):
                    if best_stab_value is None or stab > best_stab_value:
                        best_stab_value = stab
                        best_stab_name = name
            stability_leader = best_stab_name if best_stab_name is not None else "(없음)"

            # top theme 계산 (전체 전략 합산)
            from collections import Counter

            theme_counter: Counter[str] = Counter()
            root_theme_freq = data.get("theme_frequency")
            if isinstance(root_theme_freq, dict):
                for k, v in root_theme_freq.items():
                    if isinstance(v, (int, float)):
                        theme_counter[k] += int(v)
            else:
                for name in profile_names:
                    s = strategies.get(name) or {}
                    tf = s.get("theme_frequency") or {}
                    if isinstance(tf, dict):
                        for k, v in tf.items():
                            if isinstance(v, (int, float)):
                                theme_counter[k] += int(v)
            if theme_counter:
                top_theme = theme_counter.most_common(1)[0][0]
            else:
                top_theme = "(없음)"

            used_filters = data.get("used_filters") or {}
            tags = used_filters.get("tags") or []
            provider_filter = used_filters.get("provider") or "(없음)"
            session_filter = used_filters.get("session") or "(없음)"
            tag_str = ", ".join(tags) if tags else "(없음)"

            console.print(f"{idx}. {path.name}")
            console.print(f"   - timestamp: {ts} / valid_reports: {valid}")
            console.print(f"   - top winner: {win_info}")
            console.print(f"   - avg stability leader: {stability_leader}")
            console.print(
                f"   - top theme: {top_theme}"
            )
            console.print(
                f"   - filters: tags=[{tag_str}], provider={provider_filter}, session={session_filter}"
            )

    console.print("\n[summary-compare 리포트 목록]")
    if not summary_compare_files:
        console.print("(없음)")
    else:
        for idx, path in enumerate(summary_compare_files, start=1):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                console.print(f"{idx}. {path.name} (읽기 실패)")
                continue

            ts = _safe_get(data, "timestamp", "")
            used_count = _safe_get(data, "used_summary_files", 0)
            mf = data.get("summary_level_most_frequent_winner") or {}
            winner = mf.get("strategy") or "(없음)"
            win_rate = mf.get("win_rate")
            win_info = (
                f"{winner} ({win_rate:.1f}%)"
                if isinstance(win_rate, (int, float))
                else winner
            )

            used_filters = data.get("used_filters") or {}
            tags = used_filters.get("tags") or []
            provider_filter = used_filters.get("provider") or "(없음)"
            session_filter = used_filters.get("session") or "(없음)"
            tag_str = ", ".join(tags) if tags else "(없음)"

            console.print(f"{idx}. {path.name}")
            console.print(f"   - timestamp: {ts} / used_summary_files: {used_count}")
            console.print(f"   - summary-level top winner: {win_info}")
            console.print(
                f"   - filters: tags=[{tag_str}], provider={provider_filter}, session={session_filter}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

