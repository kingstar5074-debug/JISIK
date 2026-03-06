from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .models import MarketSession


NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketClock:
    """
    US market session classifier (Eastern Time).

    Sessions (typical):
    - premarket: 04:00 - 09:30 ET
    - regular:   09:30 - 16:00 ET
    - afterhours:16:00 - 20:00 ET
    - closed:    otherwise (also weekends)
    """

    pre_open: time = time(4, 0)
    regular_open: time = time(9, 30)
    regular_close: time = time(16, 0)
    after_close: time = time(20, 0)

    def now_et(self) -> datetime:
        return datetime.now(tz=NY_TZ)

    def session_of(self, dt_et: datetime) -> MarketSession:
        # Weekend check (NYSE/Nasdaq typical)
        if dt_et.weekday() >= 5:
            return "closed"

        t = dt_et.timetz().replace(tzinfo=None)
        if self.pre_open <= t < self.regular_open:
            return "premarket"
        if self.regular_open <= t < self.regular_close:
            return "regular"
        if self.regular_close <= t < self.after_close:
            return "afterhours"
        return "closed"

    def current_session(self) -> MarketSession:
        return self.session_of(self.now_et())

