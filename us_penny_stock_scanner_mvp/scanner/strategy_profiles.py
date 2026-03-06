from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

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


def _parse_weights(data: dict, key_path: str) -> StrategyWeights:
    try:
        w = StrategyWeights(
            momentum_weight=float(data["momentum_weight"]),
            volume_weight=float(data["volume_weight"]),
            gap_weight=float(data["gap_weight"]),
            liquidity_weight=float(data["liquidity_weight"]),
        )
    except KeyError as e:  # pragma: no cover - 방어적 검증
        raise ValueError(
            f"전략 프로파일 파일의 '{key_path}' 에 필요한 키가 없습니다: {e}"
        ) from e
    except Exception as e:  # pragma: no cover - 방어적 검증
        raise ValueError(
            f"전략 프로파일 파일의 '{key_path}' 값이 잘못되었습니다: {e}"
        ) from e

    # 값 검증: 음수 금지, 합이 너무 크지 않도록 제한
    for field_name, value in [
        ("momentum_weight", w.momentum_weight),
        ("volume_weight", w.volume_weight),
        ("gap_weight", w.gap_weight),
        ("liquidity_weight", w.liquidity_weight),
    ]:
        if value < 0:
            raise ValueError(
                f"전략 프로파일 파일의 '{key_path}.{field_name}' 값은 0 이상이어야 합니다."
            )

    total = (
        w.momentum_weight
        + w.volume_weight
        + w.gap_weight
        + w.liquidity_weight
    )
    if total <= 0:
        raise ValueError(
            f"전략 프로파일 파일의 '{key_path}' 가중치 합이 0 이하여서는 안 됩니다."
        )
    if total > 10:
        raise ValueError(
            f"전략 프로파일 파일의 '{key_path}' 가중치 합이 너무 큽니다 (합={total}). "
            "가중치 합은 0보다 크고 10 이하가 되도록 설정하는 것을 권장합니다."
        )

    return w


def _parse_thresholds(data: Optional[dict], key_prefix: str) -> SessionThresholds:
    if not isinstance(data, dict):
        return SessionThresholds()
    t = SessionThresholds(
        min_change_percent=data.get("min_change_percent"),
        min_gap_percent=data.get("min_gap_percent"),
        min_intraday_change_percent=data.get("min_intraday_change_percent"),
        min_volume_ratio=data.get("min_volume_ratio"),
        min_average_volume=data.get("min_average_volume"),
        min_dollar_volume=data.get("min_dollar_volume"),
    )

    # threshold 값 검증 (있으면 0 이상)
    for field_name, value in [
        ("min_change_percent", t.min_change_percent),
        ("min_gap_percent", t.min_gap_percent),
        ("min_intraday_change_percent", t.min_intraday_change_percent),
        ("min_volume_ratio", t.min_volume_ratio),
        ("min_average_volume", t.min_average_volume),
        ("min_dollar_volume", t.min_dollar_volume),
    ]:
        if value is not None and value < 0:
            raise ValueError(
                f"전략 프로파일 파일의 '{key_prefix}.{field_name}' 값은 0 이상이어야 합니다."
            )

    return t


def load_strategy_profiles(path: Path) -> Dict[str, StrategyProfile]:
    """
    strategy_profiles.json 을 읽어 StrategyProfile 딕셔너리로 변환한다.
    """

    if not path.exists():
        raise ValueError(
            f"전략 프로파일 파일을 찾을 수 없습니다: {path}. "
            "STRATEGY_PROFILES_FILE 경로를 확인해 주세요."
        )

    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
    except Exception as e:  # pragma: no cover - 방어적 검증
        raise ValueError(
            f"전략 프로파일 파일을 읽을 수 없습니다: {path} ({e})"
        ) from e

    if not isinstance(obj, dict):
        raise ValueError(
            f"전략 프로파일 파일의 최상위 구조는 JSON object 여야 합니다: {path}"
        )

    profiles: Dict[str, StrategyProfile] = {}

    required_sections = [
        "premarket_weights",
        "regular_weights",
        "afterhours_weights",
        "closed_weights",
        "premarket_thresholds",
        "regular_thresholds",
        "afterhours_thresholds",
        "closed_thresholds",
    ]

    for name, p in obj.items():
        if not isinstance(p, dict):
            raise ValueError(
                f"전략 프로파일 '{name}' 의 값이 JSON object 가 아닙니다."
            )

        # 필수 섹션 존재 여부 검증
        for sec in required_sections:
            if sec not in p:
                raise ValueError(
                    f"전략 프로파일 파일의 '{name}.{sec}' 섹션이 누락되었습니다."
                )

        pw = _parse_weights(
            p.get("premarket_weights") or {},
            f"{name}.premarket_weights",
        )
        rw = _parse_weights(
            p.get("regular_weights") or {},
            f"{name}.regular_weights",
        )
        aw = _parse_weights(
            p.get("afterhours_weights") or {},
            f"{name}.afterhours_weights",
        )
        cw = _parse_weights(
            p.get("closed_weights") or {},
            f"{name}.closed_weights",
        )

        pt = _parse_thresholds(p.get("premarket_thresholds"), f"{name}.premarket_thresholds")
        rt = _parse_thresholds(p.get("regular_thresholds"), f"{name}.regular_thresholds")
        at = _parse_thresholds(p.get("afterhours_thresholds"), f"{name}.afterhours_thresholds")
        ct = _parse_thresholds(p.get("closed_thresholds"), f"{name}.closed_thresholds")

        profiles[name.strip().lower()] = StrategyProfile(
            name=name,
            premarket_weights=pw,
            regular_weights=rw,
            afterhours_weights=aw,
            closed_weights=cw,
            premarket_thresholds=pt,
            regular_thresholds=rt,
            afterhours_thresholds=at,
            closed_thresholds=ct,
        )

    if not profiles:
        raise ValueError(
            f"전략 프로파일 파일에 유효한 프로파일이 없습니다: {path}"
        )

    return profiles


def get_strategy_profile(name: str, path: Path | None = None) -> StrategyProfile:
    """
    이름과 파일 경로를 기준으로 StrategyProfile 을 반환한다.
    """

    if path is None:
        # 기본값: 프로젝트 루트의 strategy_profiles.json
        base = Path(__file__).resolve().parent.parent
        path = base / "strategy_profiles.json"

    profiles = load_strategy_profiles(path)
    key = (name or "").strip().lower()
    if key not in profiles:
        supported = ", ".join(sorted(profiles.keys()))
        raise ValueError(
            f"지원하지 않는 STRATEGY_PROFILE 값입니다: '{name}'. "
            f"{supported} 중 하나여야 합니다. (파일: {path.name})"
        )
    return profiles[key]


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


