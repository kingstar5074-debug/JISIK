from __future__ import annotations

from rich.console import Console

from config import load_config
from scanner.strategy_profiles import load_strategy_profiles


def main() -> int:
    console = Console()
    cfg = load_config()

    console.print("전략 프로파일 요약")
    console.print(f"프로파일 파일: {cfg.strategy_profiles_file}")

    try:
        profiles = load_strategy_profiles(cfg.strategy_profiles_file)
    except ValueError as e:
        console.print(str(e))
        return 1

    for key, profile in sorted(profiles.items(), key=lambda kv: kv[0]):
        console.print(f"\n- {profile.name}")

        for session_name in ["premarket", "regular", "afterhours", "closed"]:
            weights = profile.weights_for(session_name)  # type: ignore[arg-type]
            thresholds = profile.thresholds_for(session_name)  # type: ignore[arg-type]

            console.print(f"  {session_name} weights:")
            console.print(
                f"    momentum={weights.momentum_weight}, "
                f"volume={weights.volume_weight}, "
                f"gap={weights.gap_weight}, "
                f"liquidity={weights.liquidity_weight}"
            )

            console.print(f"  {session_name} thresholds:")
            console.print(
                "    "
                f"change>={thresholds.min_change_percent}, "
                f"gap>={thresholds.min_gap_percent}, "
                f"intraday>={thresholds.min_intraday_change_percent}, "
                f"vol_ratio>={thresholds.min_volume_ratio}, "
                f"avg_vol>={thresholds.min_average_volume}, "
                f"dollar_vol>={thresholds.min_dollar_volume}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

