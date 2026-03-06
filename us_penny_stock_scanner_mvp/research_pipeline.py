from __future__ import annotations

"""
Research Automation Pipeline.

스캔 → 스냅샷 저장 → 결과 평가 → 성능 분석 → 전략 추천 → 시장 regime → 최종 fusion 까지
한 번에 실행하는 연구 자동화 파이프라인입니다.

단계:
1. Scanner (main.py)
2. Scan snapshot (trade_outcome_tracker.py --save-scan)
3. Evaluate outcomes (trade_outcome_tracker.py --evaluate --delay-minutes N)
4. Outcome analysis (outcome_performance_analyzer.py)
5. Auto strategy selector (auto_strategy_selector.py)
6. Market regime detector (market_regime_detector.py)
7. Strategy + regime fusion (strategy_regime_fusion.py)

각 단계는 subprocess 로 실행하며, 일부 단계 실패 시에도 경고 후 다음 단계로 진행합니다.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full research pipeline: scan → snapshot → evaluate → analysis → selector → regime → fusion"
    )
    parser.add_argument(
        "--delay-minutes",
        type=int,
        default=30,
        help="Delay in minutes for outcome evaluation step (default: 30)",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Skip the scanner step",
    )
    parser.add_argument(
        "--skip-evaluate",
        action="store_true",
        help="Skip outcome evaluation step",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip outcome performance analysis",
    )
    parser.add_argument(
        "--skip-selector",
        action="store_true",
        help="Skip auto strategy selector",
    )
    parser.add_argument(
        "--skip-regime",
        action="store_true",
        help="Skip market regime detector",
    )
    parser.add_argument(
        "--skip-fusion",
        action="store_true",
        help="Skip final fusion step",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed logs",
    )
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="Send final result to Telegram via telegram_reporter.py after fusion",
    )
    return parser.parse_args()


def _run_step(
    project_root: Path,
    args: list[str],
    step_name: str,
    success_msg: str,
    verbose: bool,
) -> bool:
    """Run a subprocess step. Returns True if return code is 0."""
    cmd = [sys.executable] + args
    if verbose:
        print(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=not verbose,
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✓ {success_msg}")
            return True
        print(f"  ✗ {step_name} failed (exit code {result.returncode})")
        if not verbose and result.stderr:
            print(result.stderr[:500])
        return False
    except Exception as e:
        print(f"  ✗ {step_name} error: {e}")
        return False


def main() -> int:
    args = _parse_args()
    project_root = Path(__file__).resolve().parent

    print("Starting research pipeline...\n")

    steps_ok = 0
    steps_failed = 0

    # Step 1: Scanner
    if not args.skip_scan:
        print("Step 1: Running scanner")
        if _run_step(project_root, ["main.py"], "Scanner", "Scanner completed", args.verbose):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 1: Running scanner (skipped)\n")

    # Step 2: Save scan snapshot
    print("Step 2: Saving scan snapshot")
    if _run_step(
        project_root,
        ["trade_outcome_tracker.py", "--save-scan"],
        "Snapshot",
        "Snapshot saved",
        args.verbose,
    ):
        steps_ok += 1
    else:
        steps_failed += 1
    print()

    # Step 3: Evaluate trade outcomes
    if not args.skip_evaluate:
        print("Step 3: Evaluating trade outcomes")
        delay = max(0, args.delay_minutes)
        if _run_step(
            project_root,
            ["trade_outcome_tracker.py", "--evaluate", "--delay-minutes", str(delay)],
            "Evaluate",
            "Outcomes evaluated",
            args.verbose,
        ):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 3: Evaluating trade outcomes (skipped)\n")

    # Step 4: Outcome analysis
    if not args.skip_analysis:
        print("Step 4: Running outcome analysis")
        if _run_step(
            project_root,
            ["outcome_performance_analyzer.py"],
            "Outcome analysis",
            "Outcome analysis complete",
            args.verbose,
        ):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 4: Running outcome analysis (skipped)\n")

    # Step 5: Auto strategy selector
    if not args.skip_selector:
        print("Step 5: Running strategy selector")
        if _run_step(
            project_root,
            ["auto_strategy_selector.py"],
            "Strategy selector",
            "Strategy recommendation generated",
            args.verbose,
        ):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 5: Running strategy selector (skipped)\n")

    # Step 6: Market regime detector
    if not args.skip_regime:
        print("Step 6: Detecting market regime")
        if _run_step(
            project_root,
            ["market_regime_detector.py"],
            "Regime detector",
            "Market regime detected",
            args.verbose,
        ):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 6: Detecting market regime (skipped)\n")

    # Step 7: Strategy + regime fusion
    if not args.skip_fusion:
        print("Step 7: Running strategy fusion")
        if _run_step(
            project_root,
            ["strategy_regime_fusion.py"],
            "Fusion",
            "Final strategy generated",
            args.verbose,
        ):
            steps_ok += 1
        else:
            steps_failed += 1
        print()
    else:
        print("Step 7: Running strategy fusion (skipped)\n")

    # Summary
    if steps_failed == 0:
        print("Pipeline completed successfully.")
    else:
        print(f"Pipeline finished with {steps_failed} step(s) failed (completed: {steps_ok}).")

    # Final strategy output
    final_path = project_root / "reports" / "final_strategy" / "final_strategy.json"
    if final_path.exists():
        try:
            data = json.loads(final_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                final_strategy = data.get("final_strategy", "—")
                regime = data.get("market_regime", "—")
                confidence = data.get("fusion_confidence")
                if confidence is not None:
                    confidence = f"{float(confidence):.2f}"
                else:
                    confidence = "—"
                print("\nFinal Strategy:")
                print(f"  Final Strategy: {final_strategy}")
                print(f"  Market Regime: {regime}")
                print(f"  Confidence: {confidence}")
            else:
                print("\nFinal Strategy: (invalid JSON structure)")
        except Exception as e:
            print(f"\nFinal Strategy: (could not read: {e})")
    else:
        print(f"\nFinal Strategy: (file not found: {final_path})")

    # Optional: send to Telegram
    if getattr(args, "send_telegram", False):
        print("\nSending to Telegram...")
        try:
            result = subprocess.run(
                [sys.executable, "telegram_reporter.py"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                print("Warning: Telegram reporter exited with non-zero code (message may not have been sent).")
            elif result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        print(f"  {line}")
        except subprocess.TimeoutExpired:
            print("Warning: Telegram reporter timed out.")
        except Exception as e:
            print(f"Warning: Telegram reporter failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
