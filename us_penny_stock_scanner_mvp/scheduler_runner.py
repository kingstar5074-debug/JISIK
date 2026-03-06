from __future__ import annotations

"""
Production Runner & Scheduler.

pipeline_config.json 설정에 따라 research_pipeline.py 를 주기적으로 실행합니다.

- run_interval_minutes 간격으로 파이프라인 실행
- 실행 로그를 log_directory 에 기록
- 실패 시 로그 남기고 auto_restart 이면 계속 실행
- 종료 시까지 무한 루프로 동작
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "pipeline_config.json"


def _load_config(config_path: Path) -> dict | None:
    if not config_path.exists() or not config_path.is_file():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _ensure_log_dir(log_dir: Path) -> Path:
    if not log_dir.is_absolute():
        log_dir = PROJECT_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log_run(log_path: Path, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line.rstrip())


def main() -> int:
    config_path = DEFAULT_CONFIG_PATH
    config = _load_config(config_path)
    if not config:
        print(f"Config not found or invalid: {config_path}")
        return 1

    run_interval_minutes = int(config.get("run_interval_minutes", 60))
    run_interval_minutes = max(1, run_interval_minutes)
    log_directory = config.get("log_directory", "logs")
    pipeline_script = config.get("pipeline_script", "research_pipeline.py")
    auto_restart = bool(config.get("auto_restart", True))

    log_dir = _ensure_log_dir(Path(log_directory))
    log_file = log_dir / "scheduler_runner.log"
    script_path = PROJECT_ROOT / pipeline_script
    if not script_path.exists():
        _log_run(log_file, f"ERROR: Pipeline script not found: {script_path}")
        return 1

    _log_run(log_file, f"Scheduler started. interval={run_interval_minutes} min, script={pipeline_script}, auto_restart={auto_restart}")

    run_count = 0
    while True:
        run_count += 1
        _log_run(log_file, f"Run #{run_count} starting pipeline...")
        try:
            result = subprocess.run(
                [sys.executable, pipeline_script],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode == 0:
                _log_run(log_file, f"Run #{run_count} completed successfully.")
            else:
                _log_run(log_file, f"Run #{run_count} exited with code {result.returncode}.")
                if result.stderr:
                    for line in result.stderr.strip().split("\n")[:20]:
                        _log_run(log_file, f"  stderr: {line}")
        except subprocess.TimeoutExpired:
            _log_run(log_file, f"Run #{run_count} timed out after 3600s.")
        except Exception as e:
            _log_run(log_file, f"Run #{run_count} error: {e}")

        if not auto_restart:
            _log_run(log_file, "auto_restart is false; exiting.")
            break

        _log_run(log_file, f"Sleeping {run_interval_minutes} minutes until next run.")
        try:
            time.sleep(run_interval_minutes * 60)
        except KeyboardInterrupt:
            _log_run(log_file, "Scheduler stopped by user.")
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
