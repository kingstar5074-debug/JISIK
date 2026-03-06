from __future__ import annotations

"""
Telegram Notification Reporter.

최종 연구 결과(final_strategy.json)를 읽어 Telegram Bot API 로 메시지를 전송합니다.

환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (둘 다 필요)
입력: reports/final_strategy/final_strategy.json (필수), market_regime / recommended_strategy (선택)
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = "reports/final_strategy/final_strategy.json"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send final research result to Telegram"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT,
        help=f"Path to final_strategy.json (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print message only, do not send",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed logs",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _build_message(final_data: dict[str, Any], project_root: Path) -> str:
    lines = [
        "US Penny Stock Research Update",
        "",
        f"Final Strategy: {final_data.get('final_strategy') or 'N/A'}",
        f"Market Regime: {final_data.get('market_regime') or 'N/A'}",
    ]
    conf = final_data.get("fusion_confidence")
    if conf is not None:
        try:
            lines.append(f"Confidence: {float(conf):.2f}")
        except (TypeError, ValueError):
            lines.append("Confidence: N/A")
    else:
        lines.append("Confidence: N/A")
    lines.append("")

    sel_rec = final_data.get("selector_recommendation")
    if sel_rec:
        lines.append(f"Selector Recommendation: {sel_rec}")
    reason = final_data.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")
    if sel_rec or reason:
        lines.append("")

    ranking = final_data.get("ranking")
    if isinstance(ranking, list) and ranking:
        lines.append("Top Strategy Ranking:")
        for i, item in enumerate(ranking[:3], start=1):
            if isinstance(item, dict):
                name = item.get("strategy", "N/A")
                score = item.get("score", "N/A")
                if isinstance(score, (int, float)):
                    score = f"{score:.1f}"
                lines.append(f"{i}. {name} ({score})")
        lines.append("")

    return "\n".join(lines).strip()


def main() -> int:
    args = _parse_args()
    verbose = args.verbose

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not args.dry_run and (not token or not chat_id):
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the environment. Exiting.")
        return 0

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    print("Loading final strategy...")
    final_data = _load_json(input_path)
    if not final_data:
        print("final_strategy.json not found or invalid. Exiting.")
        return 0

    # Optional: fill missing fields from supporting files
    if not final_data.get("market_regime"):
        regime_path = PROJECT_ROOT / "reports" / "market_regime" / "market_regime.json"
        regime_data = _load_json(regime_path)
        if regime_data and regime_data.get("regime"):
            final_data = {**final_data, "market_regime": regime_data["regime"]}
    if not final_data.get("selector_recommendation") or not final_data.get("ranking"):
        rec_path = PROJECT_ROOT / "reports" / "strategy_recommendation" / "recommended_strategy.json"
        rec_data = _load_json(rec_path)
        if rec_data:
            if not final_data.get("selector_recommendation") and rec_data.get("recommended_strategy"):
                final_data = {**final_data, "selector_recommendation": rec_data["recommended_strategy"]}
            if not final_data.get("ranking") and rec_data.get("ranking"):
                final_data = {**final_data, "ranking": rec_data["ranking"]}

    message = _build_message(final_data, PROJECT_ROOT)
    if verbose:
        print("Message built successfully.")

    if not args.dry_run:
        print("Telegram configuration loaded.")
        print("Sending Telegram message...")
        url = TELEGRAM_API.format(token=token)
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": message},
                timeout=15,
            )
            resp.raise_for_status()
            print("✓ Telegram message sent successfully.")
        except requests.RequestException as e:
            print(f"Telegram API request failed: {e}")
            if verbose and hasattr(e, "response") and e.response is not None:
                try:
                    print(e.response.text[:500])
                except Exception:
                    pass
            return 0
    else:
        print("Telegram configuration loaded.")
        print("Dry run mode enabled.")
        print("Message preview:")
        print("-" * 40)
        print(message)
        print("-" * 40)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
