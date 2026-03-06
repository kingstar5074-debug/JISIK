from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple


class JsonTTLCache:
    """
    심볼 단위의 간단한 JSON 파일 TTL 캐시.

    구조:
    {
      "SYMBOL": {
        "value": ...,
        "updated_at": <epoch_seconds>
      },
      ...
    }
    """

    def __init__(self, path: Path, ttl_hours: int) -> None:
        self.path = path
        self.ttl_seconds = max(ttl_hours, 0) * 3600
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            obj = json.loads(raw)
            if isinstance(obj, dict):
                self._data = obj
        except Exception:
            # 깨진 캐시는 무시하고 새로 시작
            self._data = {}

    def get(self, key: str) -> Tuple[bool, Any]:
        """
        반환: (hit 여부, 값 또는 None)
        """

        if key not in self._data:
            return False, None

        entry = self._data.get(key, {})
        ts = entry.get("updated_at")
        now = time.time()
        try:
            ts_f = float(ts)
        except Exception:
            # 잘못된 타임스탬프는 캐시 무효
            self._data.pop(key, None)
            return False, None

        if self.ttl_seconds > 0 and now - ts_f > self.ttl_seconds:
            # TTL 초과
            self._data.pop(key, None)
            return False, None

        return True, entry.get("value")

    def set(self, key: str, value: Any) -> None:
        self._data[key] = {"value": value, "updated_at": time.time()}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except Exception:
            # 캐시 저장 실패는 전체 흐름에 영향 주지 않음
            pass

