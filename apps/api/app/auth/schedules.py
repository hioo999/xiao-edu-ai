from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class DailyWindow:
    start: time
    end: time


@dataclass(frozen=True)
class AccessSchedule:
    start_date: date
    end_date: date
    weekdays: set[int]
    daily_windows: tuple[DailyWindow, ...]
    holiday_exceptions: set[date] = frozenset()


def is_access_allowed(schedule: AccessSchedule, timestamp: str, *, class_state: str) -> bool:
    if class_state != "open":
        return False
    current = datetime.fromisoformat(timestamp).astimezone(SHANGHAI)
    current_date = current.date()
    if current_date < schedule.start_date or current_date > schedule.end_date:
        return False
    if current_date in schedule.holiday_exceptions or current_date.weekday() not in schedule.weekdays:
        return False
    return any(window.start <= current.time() < window.end for window in schedule.daily_windows)
