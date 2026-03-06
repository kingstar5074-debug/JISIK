from __future__ import annotations

"""
System Health Check for US Penny Stock Scanner MVP.

이 스크립트는 전체 리서치 시스템이 정상적으로 동작할 준비가 되었는지 점검합니다.

점검 항목:
- 핵심 파일 존재 여부
- reports / logs / reports/runtime 디렉터리 존재 및 생성 가능 여부
- 주요 모듈 import 가능 여부 (데이터 호출 X)
- 대시보드 관련 리포트 아티팩트 상태 (옵션)
- 런타임 상태 / lock 파일 상태
- 텔레그램 환경변수 상태 (옵션)
- 전체 health 요약 (HEALTHY / HEALTHY_WITH_WARNINGS / UNHEALTHY)

주의:
- 파이프라인을 실제 실행하지 않습니다.
- 외부 API(텔레그램 등)를 호출하지 않습니다.
"""

import argparse
import csv
import importlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd  # 이미 requirements.txt에 포함되어 있음


PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
RUNTIME_DIR = REPORTS_DIR / "runtime"


@dataclass
class CheckDetail:
    item: str
    status: str  # PASS / WARN / FAIL
    message: str


@dataclass
class CategoryResult:
    category: str
    status: str  # PASS / WARN / FAIL
    details: List[CheckDetail]


def _add_detail(details: List[CheckDetail], item: str, status: str, message: str) -> None:
    details.append(CheckDetail(item=item, status=status, message=message))


# 1. CORE FILE CHECKS
def check_core_files() -> CategoryResult:
    details: List[CheckDetail] = []
    core_files = [
        ("main.py", True),
        ("research_pipeline.py", True),
        ("dashboard.py", True),
        ("scheduler_runner.py", False),
        ("telegram_reporter.py", False),
        ("trade_outcome_tracker.py", False),
        ("outcome_performance_analyzer.py", False),
        ("auto_strategy_selector.py", False),
        ("market_regime_detector.py", False),
        ("strategy_regime_fusion.py", False),
    ]
    worst = "PASS"
    for name, critical in core_files:
        path = PROJECT_ROOT / name
        if path.exists():
            _add_detail(details, name, "PASS", "exists")
        else:
            status = "FAIL" if critical else "WARN"
            msg = "missing (critical)" if critical else "missing"
            _add_detail(details, name, status, msg)
            if status == "FAIL":
                worst = "FAIL"
            elif worst != "FAIL":
                worst = "WARN"
    return CategoryResult("core_files", worst, details)


# 2. DIRECTORY CHECKS
def check_directories(output_dir: Path) -> CategoryResult:
    details: List[CheckDetail] = []
    worst = "PASS"
    for d in [REPORTS_DIR, LOGS_DIR, RUNTIME_DIR, output_dir]:
        name = str(d)
        if d.exists():
            if d.is_dir():
                _add_detail(details, name, "PASS", "exists")
            else:
                _add_detail(details, name, "FAIL", "is not a directory")
                worst = "FAIL"
        else:
            try:
                d.mkdir(parents=True, exist_ok=True)
                _add_detail(details, name, "PASS", "created")
            except Exception as e:
                _add_detail(details, name, "FAIL", f"cannot create: {e}")
                worst = "FAIL"
    return CategoryResult("directories", worst, details)


# 3. PROVIDER / SCANNER IMPORT CHECK
def check_imports() -> CategoryResult:
    details: List[CheckDetail] = []
    worst = "PASS"
    modules = ["main", "dashboard", "trade_outcome_tracker", "research_pipeline"]
    for mod in modules:
        try:
            importlib.import_module(mod)
            _add_detail(details, mod, "PASS", "import ok")
        except Exception as e:
            _add_detail(details, mod, "FAIL", f"import failed: {e}")
            worst = "FAIL"

    try:
        from scanner.providers.factory import get_market_data_provider  # noqa: F401

        _add_detail(details, "scanner.providers.factory", "PASS", "import ok")
    except Exception as e:
        _add_detail(details, "scanner.providers.factory", "FAIL", f"import failed: {e}")
        worst = "FAIL"

    return CategoryResult("imports", worst, details)


# 4. REPORT ARTIFACT CHECKS (대시보드용, 옵션)
def check_dashboard_artifacts() -> CategoryResult:
    details: List[CheckDetail] = []
    worst = "PASS"

    json_files = [
        REPORTS_DIR / "final_strategy" / "final_strategy.json",
        REPORTS_DIR / "market_regime" / "market_regime.json",
        REPORTS_DIR / "strategy_recommendation" / "recommended_strategy.json",
    ]
    for path in json_files:
        name = str(path)
        if not path.exists():
            _add_detail(details, name, "WARN", "missing (dashboard will show no data)")
            if worst == "PASS":
                worst = "WARN"
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _add_detail(details, name, "PASS", "json ok")
            else:
                _add_detail(details, name, "WARN", "json root is not an object")
                if worst == "PASS":
                    worst = "WARN"
        except Exception as e:
            _add_detail(details, name, "WARN", f"json parse error: {e}")
            if worst == "PASS":
                worst = "WARN"

    csv_files = [
        REPORTS_DIR / "outcome_analysis" / "outcome_summary_strategy.csv",
        REPORTS_DIR / "trade_outcomes" / "trade_results.csv",
    ]
    for path in csv_files:
        name = str(path)
        if not path.exists():
            _add_detail(details, name, "WARN", "missing (dashboard table/curve may be empty)")
            if worst == "PASS":
                worst = "WARN"
            continue
        try:
            pd.read_csv(path)
            _add_detail(details, name, "PASS", "csv ok")
        except Exception as e:
            _add_detail(details, name, "WARN", f"csv read error: {e}")
            if worst == "PASS":
                worst = "WARN"

    heat_dir = REPORTS_DIR / "heatmaps"
    if heat_dir.exists() and heat_dir.is_dir():
        pngs = list(heat_dir.glob("*.png"))
        if pngs:
            _add_detail(details, str(heat_dir), "PASS", f"{len(pngs)} png file(s)")
        else:
            _add_detail(details, str(heat_dir), "WARN", "no png files")
            if worst == "PASS":
                worst = "WARN"
    else:
        _add_detail(details, str(heat_dir), "WARN", "directory missing")
        if worst == "PASS":
            worst = "WARN"

    return CategoryResult("dashboard_artifacts", worst, details)


# 5. RUNTIME STATUS CHECKS
def check_runtime_status() -> CategoryResult:
    details: List[CheckDetail] = []
    worst = "PASS"

    status_path = RUNTIME_DIR / "dashboard_runtime_status.json"
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            expected_keys = [
                "is_running",
                "last_run_start",
                "last_run_end",
                "last_result",
                "last_command",
            ]
            missing = [k for k in expected_keys if k not in data]
            if missing:
                _add_detail(
                    details,
                    str(status_path),
                    "WARN",
                    f"status json missing keys: {', '.join(missing)}",
                )
                if worst == "PASS":
                    worst = "WARN"
            else:
                _add_detail(details, str(status_path), "PASS", "status json ok")
        except Exception as e:
            _add_detail(details, str(status_path), "WARN", f"status json parse error: {e}")
            if worst == "PASS":
                worst = "WARN"
    else:
        _add_detail(details, str(status_path), "WARN", "status json missing")
        if worst == "PASS":
            worst = "WARN"

    lock_path = RUNTIME_DIR / "pipeline_running.lock"
    if lock_path.exists():
        _add_detail(details, str(lock_path), "WARN", "pipeline lock present")
        if worst == "PASS":
            worst = "WARN"
    else:
        _add_detail(details, str(lock_path), "PASS", "no lock file")

    return CategoryResult("runtime_status", worst, details)


# 6. TELEGRAM CONFIG CHECK
def _mask_value(val: str) -> str:
    if not val:
        return ""
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}***{val[-3:]}"


def check_telegram_config() -> CategoryResult:
    details: List[CheckDetail] = []

    # 1) env vars
    env_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    env_chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    env_has_both = bool(env_token and env_chat)

    if env_token or env_chat:
        msg = f"env: token={bool(env_token)}, chat_id={bool(env_chat)}"
        _add_detail(
            details,
            "env",
            "PASS" if env_has_both else "WARN",
            msg,
        )
    else:
        _add_detail(details, "env", "WARN", "env vars not set")

    # 2) .env file
    env_path = PROJECT_ROOT / ".env"
    file_has_token = False
    file_has_chat = False
    if env_path.exists():
        try:
            txt = env_path.read_text(encoding="utf-8")
            file_has_token = "TELEGRAM_BOT_TOKEN" in txt
            file_has_chat = "TELEGRAM_CHAT_ID" in txt
            msg = f".env has token={file_has_token}, chat_id={file_has_chat}"
            _add_detail(details, str(env_path), "PASS", msg)
        except Exception as e:
            _add_detail(details, str(env_path), "WARN", f"cannot read .env: {e}")
    else:
        _add_detail(details, str(env_path), "WARN", ".env missing")

    effective_token = bool(env_token or file_has_token)
    effective_chat = bool(env_chat or file_has_chat)

    if effective_token and effective_chat:
        status = "PASS"
    else:
        status = "WARN"

    source_parts = []
    source_parts.append(f"env_token={bool(env_token)}")
    source_parts.append(f"env_chat_id={bool(env_chat)}")
    source_parts.append(f"envfile_token={file_has_token}")
    source_parts.append(f"envfile_chat_id={file_has_chat}")
    _add_detail(details, "effective_config", status, ", ".join(source_parts))

    return CategoryResult("telegram", status, details)


def summarize_categories(categories: List[CategoryResult]) -> str:
    overall = "HEALTHY"
    for cat in categories:
        if cat.status == "FAIL":
            overall = "UNHEALTHY"
            break
    else:
        if any(cat.status == "WARN" for cat in categories):
            overall = "HEALTHY_WITH_WARNINGS"
    return overall


def main() -> int:
    parser = argparse.ArgumentParser(description="System health check for US Penny Stock Scanner MVP")
    parser.add_argument("--verbose", action="store_true", help="Print detailed checks")
    parser.add_argument("--json", action="store_true", help="Save JSON report")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR / "health_check"),
        help="Output directory for JSON report (default: reports/health_check)",
    )
    parser.add_argument("--check-telegram", action="store_true", help="Include Telegram env checks")
    parser.add_argument("--check-dashboard", action="store_true", help="Include dashboard/report artifact checks")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if overall status is UNHEALTHY")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    categories: List[CategoryResult] = []

    core_res = check_core_files()
    categories.append(core_res)

    dir_res = check_directories(output_dir)
    categories.append(dir_res)

    imp_res = check_imports()
    categories.append(imp_res)

    if args.check_dashboard:
        dash_res = check_dashboard_artifacts()
        categories.append(dash_res)

    rt_res = check_runtime_status()
    categories.append(rt_res)

    if args.check_telegram:
        tel_res = check_telegram_config()
        categories.append(tel_res)

    overall = summarize_categories(categories)

    print("System Health Check Summary")
    print("---------------------------")
    for cat in categories:
        print(f"[{cat.status}] {cat.category}")
        if args.verbose:
            for d in cat.details:
                print(f"  - {d.item}: {d.status} ({d.message})")
    print("")
    print(f"Overall health: {overall}")

    # Recommended next action
    recommended = "System is healthy enough to proceed."
    core_cat = next((c for c in categories if c.category == "core_files"), None)
    if core_cat:
        for d in core_cat.details:
            if d.item == "dashboard.py" and d.status == "FAIL":
                recommended = "Restore dashboard.py and rerun health check."
                break
    if recommended == "System is healthy enough to proceed.":
        dash_cat = next((c for c in categories if c.category == "dashboard_artifacts"), None)
        if dash_cat:
            if any(
                d.status == "WARN"
                and (
                    "final_strategy" in d.item
                    or "market_regime" in d.item
                    or "strategy_recommendation" in d.item
                )
                for d in dash_cat.details
            ):
                recommended = "Run research_pipeline.py to generate dashboard artifacts."

    print(f"Recommended next action: {recommended}")

    if args.json:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "system_health_report.json"
        payload: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall,
            "checks": [
                {
                    "category": c.category,
                    "status": c.status,
                    "details": [asdict(d) for d in c.details],
                }
                for c in categories
            ],
        }
        try:
            report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"JSON report saved to {report_path}")
        except Exception as e:
            print(f"Failed to save JSON report: {e}")

    if args.strict and overall == "UNHEALTHY":
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())