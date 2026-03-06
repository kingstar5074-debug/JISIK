from __future__ import annotations

"""
Strategy + Regime Fusion.

Auto Strategy Selector(recommended_strategy.json)와 Market Regime Detector(market_regime.json)를
합쳐 최종 추천 전략과 설명을 출력하는 결정 엔진입니다.

- Selector 추천을 시장 regime(VOLATILE/TRENDING/WEAK/RANGE)에 따라 조정
- override 시 fusion_confidence = selector_confidence * 0.85
- reports/final_strategy/final_strategy.json 생성

기존 스캐너 로직을 수정하지 않으며 독립적으로 동작합니다.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

DEFAULT_STRATEGY_INPUT = "reports/strategy_recommendation/recommended_strategy.json"
DEFAULT_REGIME_INPUT = "reports/market_regime/market_regime.json"
DEFAULT_OUTPUT_DIR = "reports/final_strategy"
OUTPUT_FILENAME = "final_strategy.json"

SUPPORTED_STRATEGIES = frozenset({"aggressive", "balanced", "conservative"})
SUPPORTED_REGIMES = frozenset({"VOLATILE", "TRENDING", "WEAK", "RANGE"})
FUSION_DOWNGRADE_FACTOR = 0.85


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fuse strategy recommendation with market regime into final strategy"
    )
    parser.add_argument(
        "--strategy-input",
        type=str,
        default=DEFAULT_STRATEGY_INPUT,
        help=f"Path to recommended_strategy.json (default: {DEFAULT_STRATEGY_INPUT})",
    )
    parser.add_argument(
        "--regime-input",
        type=str,
        default=DEFAULT_REGIME_INPUT,
        help=f"Path to market_regime.json (default: {DEFAULT_REGIME_INPUT})",
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
        console.print(f"파일을 찾을 수 없습니다: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError as e:
        console.print(f"JSON 파싱 실패 ({path}): {e}")
        return None
    except Exception as e:
        console.print(f"읽기 실패 ({path}): {e}")
        return None


def _apply_fusion(
    selector_recommendation: str,
    regime: str,
    ranking: list[dict[str, Any]],
) -> tuple[str, bool]:
    """
    Apply regime adjustment rules. Returns (final_strategy, override_applied).
    """
    rec = selector_recommendation.strip().lower()
    ranking_names = {r.get("strategy", "").strip().lower() for r in ranking if isinstance(r, dict)}
    ranking_names = {s for s in ranking_names if s in SUPPORTED_STRATEGIES}

    if regime == "VOLATILE":
        preferred = "balanced"
        if rec == "balanced":
            return ("balanced", False)
        if rec == "aggressive":
            return ("balanced", True)
        return ("balanced", True)  # conservative -> balanced

    if regime == "TRENDING":
        preferred = "aggressive"
        if rec == "aggressive":
            return ("aggressive", False)
        if "aggressive" in ranking_names:
            return ("aggressive", rec != "aggressive")
        return (rec, False)

    if regime == "WEAK":
        preferred = "conservative"
        if rec == "conservative":
            return ("conservative", False)
        return ("conservative", True)

    if regime == "RANGE":
        preferred = "balanced"
        if rec == "balanced":
            return ("balanced", False)
        return ("balanced", True)  # aggressive or conservative -> balanced

    return (rec, False)


def _build_reason(
    selector_recommendation: str,
    regime: str,
    final_strategy: str,
    override_applied: bool,
) -> str:
    if not override_applied:
        return (
            f"Selector recommended {selector_recommendation}, and market regime is {regime}, "
            f"so {final_strategy} remains the preferred strategy."
        )
    return (
        f"Selector recommended {selector_recommendation}, but market regime is {regime} "
        f"so {final_strategy} is preferred."
    )


def main() -> int:
    args = _parse_args()
    console = Console()

    project_root = Path(__file__).resolve().parent
    strategy_path = Path(args.strategy_input)
    if not strategy_path.is_absolute():
        strategy_path = project_root / strategy_path
    regime_path = Path(args.regime_input)
    if not regime_path.is_absolute():
        regime_path = project_root / regime_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    strategy_data = _load_json(strategy_path, console)
    if not strategy_data:
        return 0

    regime_data = _load_json(regime_path, console)
    if not regime_data:
        return 0

    selector_rec = strategy_data.get("recommended_strategy")
    if selector_rec is None or not str(selector_rec).strip():
        console.print("recommended_strategy 가 없거나 비어 있습니다.")
        return 0
    selector_rec = str(selector_rec).strip().lower()
    if selector_rec not in SUPPORTED_STRATEGIES:
        console.print(f"지원하지 않는 전략입니다: {selector_rec}")
        return 0

    regime = regime_data.get("regime")
    if regime is None or not str(regime).strip():
        console.print("regime 이 없거나 비어 있습니다.")
        return 0
    regime = str(regime).strip().upper()
    if regime not in SUPPORTED_REGIMES:
        console.print(f"지원하지 않는 regime 입니다: {regime}")
        return 0

    ranking = strategy_data.get("ranking")
    if not isinstance(ranking, list):
        ranking = []
    ranking = [r for r in ranking if isinstance(r, dict)]

    selector_confidence = strategy_data.get("confidence")
    try:
        selector_confidence = float(selector_confidence) if selector_confidence is not None else 0.0
    except (TypeError, ValueError):
        selector_confidence = 0.0
    selector_confidence = max(0.0, min(1.0, round(selector_confidence, 2)))

    final_strategy, override_applied = _apply_fusion(selector_rec, regime, ranking)
    if override_applied:
        fusion_confidence = round(selector_confidence * FUSION_DOWNGRADE_FACTOR, 2)
    else:
        fusion_confidence = selector_confidence

    reason = _build_reason(selector_rec, regime, final_strategy, override_applied)

    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selector_input_file": str(strategy_path),
        "regime_input_file": str(regime_path),
        "selector_recommendation": selector_rec,
        "selector_confidence": selector_confidence,
        "market_regime": regime,
        "final_strategy": final_strategy,
        "fusion_confidence": fusion_confidence,
        "regime_override_applied": override_applied,
        "reason": reason,
        "ranking": ranking,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / OUTPUT_FILENAME

    try:
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        console.print(f"저장 실패: {e}")
        return 0

    console.print("\nSelector recommendation: " + selector_rec)
    console.print("Market regime: " + regime)
    console.print("Final strategy: " + final_strategy)
    console.print(f"Fusion confidence: {fusion_confidence}")
    console.print("Override applied: " + ("yes" if override_applied else "no"))
    console.print("Saved: " + str(out_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
