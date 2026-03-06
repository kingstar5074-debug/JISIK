from __future__ import annotations

from typing import List


def detect_theme_tags(symbol: str) -> List[str]:
    """
    심볼 문자열을 기반으로 섹터/테마 태그를 간단히 추론한다.

    현재 구현은 순수 규칙 기반이며 뉴스/재무/주문과는 무관하다.
    """

    s = (symbol or "").upper()
    tags: list[str] = []

    oil_keywords = ["OIL", "PET", "ENER", "DRILL", "GAS"]
    ai_keywords = ["AI", "DATA", "TECH", "ROBOT", "ML"]
    biotech_keywords = ["BIO", "PHAR", "MED", "THERA"]
    shipping_keywords = ["SHIP", "TANK", "SEA", "MARINE"]

    if any(k in s for k in oil_keywords):
        tags.append("oil")
    if any(k in s for k in ai_keywords):
        tags.append("ai")
    if any(k in s for k in biotech_keywords):
        tags.append("biotech")
    if any(k in s for k in shipping_keywords):
        tags.append("shipping")

    if not tags:
        return ["unknown"]

    # 중복 제거 (이론상 없지만 방어 코드)
    seen: set[str] = set()
    unique: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique

