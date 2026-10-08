from datetime import date, time

from apps.api.app.auth.schedules import AccessSchedule, DailyWindow, is_access_allowed


def test_schedule_uses_shanghai_timezone_and_half_open_daily_window() -> None:
    schedule = AccessSchedule(
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 30),
        weekdays={1},
        daily_windows=(DailyWindow(start=time(14, 0), end=time(18, 0)),),
        holiday_exceptions={date(2026, 9, 29)},
    )

    assert is_access_allowed(schedule, "2026-09-22T14:00:00+08:00", class_state="open")
    assert not is_access_allowed(schedule, "2026-09-22T18:00:00+08:00", class_state="open")
    assert not is_access_allowed(schedule, "2026-09-29T15:00:00+08:00", class_state="open")


def test_schedule_rejects_paused_or_closed_class() -> None:
    schedule = AccessSchedule(
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 30),
        weekdays={1},
        daily_windows=(DailyWindow(start=time(14, 0), end=time(18, 0)),),
    )

    assert not is_access_allowed(schedule, "2026-09-22T15:00:00+08:00", class_state="paused")
    assert not is_access_allowed(schedule, "2026-09-22T15:00:00+08:00", class_state="closed")
