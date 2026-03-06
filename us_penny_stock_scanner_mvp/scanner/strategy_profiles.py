from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from scanner.filters import ScanFilters
from scanner.models import MarketSession


@dataclass(frozen=True)
class StrategyWeights:
    momentum_weight: float
    volume_weight: float
    gap_weight: float
    liquidity_weight: float


@dataclass(frozen=True)
class SessionThresholds:
    """
    세션별 필터 오버라이드 값.

    - None 이면 기본 ScanFilters 값을 그대로 사용
    - 값이 있으면 해당 세션에서 그 값을 사용
    """

    min_change_percent: Optional[float] = None
    min_gap_percent: Optional[float] = None
    min_intraday_change_percent: Optional[float] = None
    min_volume_ratio: Optional[float] = None
    min_average_volume: Optional[float] = None
    min_dollar_volume: Optional[float] = None


@dataclass(frozen=True)
class StrategyProfile:
    name: str

    premarket_weights: StrategyWeights
    regular_weights: StrategyWeights
    afterhours_weights: StrategyWeights
    closed_weights: StrategyWeights

    premarket_thresholds: SessionThresholds
    regular_thresholds: SessionThresholds
    afterhours_thresholds: SessionThresholds
    closed_thresholds: SessionThresholds

    def weights_for(self, session: MarketSession) -> StrategyWeights:
        if session == "premarket":
            return self.premarket_weights
        if session == "regular":
            return self.regular_weights
        if session == "afterhours":
            return self.afterhours_weights
        return self.closed_weights

    def thresholds_for(self, session: MarketSession) -> SessionThresholds:
        if session == "premarket":
            return self.premarket_thresholds
        if session == "regular":
            return self.regular_thresholds
        if session == "afterhours":
            return self.afterhours_thresholds
        return self.closed_thresholds


def _inherit() -> SessionThresholds:
    """
    기본 ScanFilters 값을 그대로 쓰는 세션용.
    """

    return SessionThresholds()


def _balanced_profile() -> StrategyProfile:
    """
    balanced:
    - 현재 기본 동작과 거의 동일
    - 필터 값은 .env 기반, 세션별 오버라이드는 없음
    """

    premarket_w = StrategyWeights(0.35, 0.25, 0.40, 0.15)
    regular_w = StrategyWeights(0.45, 0.35, 0.20, 0.15)
    after_w = StrategyWeights(0.35, 0.40, 0.25, 0.15)
    closed_w = regular_w

    inherit = _inherit()

    return StrategyProfile(
        name="balanced",
        premarket_weights=premarket_w,
        regular_weights=regular_w,
        afterhours_weights=after_w,
        closed_weights=closed_w,
        premarket_thresholds=inherit,
        regular_thresholds=inherit,
        afterhours_thresholds=inherit,
        closed_thresholds=inherit,
    )


def _aggressive_profile() -> StrategyProfile:
    """
    aggressive:
    - gap / momentum 비중을 조금 더 높이고
    - 필터 기준을 다소 완화해 더 많은 후보를 잡는 방향
    """

    premarket_w = StrategyWeights(0.40, 0.20, 0.45, 0.10)
    regular_w = StrategyWeights(0.50, 0.30, 0.20, 0.10)
    after_w = StrategyWeights(0.40, 0.40, 0.20, 0.10)
    closed_w = regular_w

    # 기본값(15/5/10/3/100k/500k) 대비 다소 완화
    loose = SessionThresholds(
        min_change_percent=10.0,
        min_gap_percent=3.0,
        min_intraday_change_percent=8.0,
        min_volume_ratio=2.0,
        min_average_volume=80_000.0,
        min_dollar_volume=400_000.0,
    )

    return StrategyProfile(
        name="aggressive",
        premarket_weights=premarket_w,
        regular_weights=regular_w,
        afterhours_weights=after_w,
        closed_weights=closed_w,
        premarket_thresholds=loose,
        regular_thresholds=loose,
        afterhours_thresholds=loose,
        closed_thresholds=loose,
    )


def _conservative_profile() -> StrategyProfile:
    """
    conservative:
    - 유동성과 거래 안정성을 더 중시
    - dollar_volume / average_volume 기준을 올리고
    - volume/liquidity 가중치를 조금 더 줌
    """

    premarket_w = StrategyWeights(0.30, 0.30, 0.30, 0.20)
    regular_w = StrategyWeights(0.35, 0.35, 0.15, 0.25)
    after_w = StrategyWeights(0.30, 0.45, 0.10, 0.25)
    closed_w = regular_w

    strict = SessionThresholds(
        # 모멘텀 기준은 balanced 와 비슷하게 두고
        min_change_percent=15.0,
        min_gap_percent=5.0,
        min_intraday_change_percent=10.0,
        # 유동성 기준을 더 높임
        min_volume_ratio=3.0,
        min_average_volume=150_000.0,
        min_dollar_volume=800_000.0,
    )

    return StrategyProfile(
        name="conservative",
        premarket_weights=premarket_w,
        regular_weights=regular_w,
        afterhours_weights=after_w,
        closed_weights=closed_w,
        premarket_thresholds=strict,
        regular_thresholds=strict,
        afterhours_thresholds=strict,
        closed_thresholds=strict,
    )


_PROFILES: dict[str, StrategyProfile] = {
    "balanced": _balanced_profile(),
    "aggressive": _aggressive_profile(),
    "conservative": _conservative_profile(),
}


def get_strategy_profile(name: str) -> StrategyProfile:
    key = (name or "").strip().lower()
    if key not in _PROFILES:
        supported = ", ".join(sorted(_PROFILES.keys()))
        raise ValueError(
            f"지원하지 않는 STRATEGY_PROFILE 값입니다: '{name}'. "
            f"{supported} 중 하나여야 합니다."
        )
    return _PROFILES[key]


def get_effective_filters(
    base_filters: ScanFilters,
    session: MarketSession,
    profile: StrategyProfile,
) -> ScanFilters:
    """
    기본 ScanFilters + 세션별 오버라이드를 합성한 실제 필터를 계산한다.
    """

    t = profile.thresholds_for(session)

    def v(base: float, override: Optional[float]) -> float:
        return base if override is None else override

    return ScanFilters(
        min_price=base_filters.min_price,
        max_price=base_filters.max_price,
        min_change_percent=v(base_filters.min_change_percent, t.min_change_percent),
        min_volume_ratio=v(base_filters.min_volume_ratio, t.min_volume_ratio),
        min_gap_percent=v(base_filters.min_gap_percent, t.min_gap_percent),
        min_intraday_change_percent=v(
            base_filters.min_intraday_change_percent,
            t.min_intraday_change_percent,
        ),
        min_dollar_volume=v(base_filters.min_dollar_volume, t.min_dollar_volume),
        min_average_volume=v(base_filters.min_average_volume, t.min_average_volume),
    )


def get_session_weights(
    profile: StrategyProfile,
    session: MarketSession,
) -> StrategyWeights:
    return profile.weights_for(session)

