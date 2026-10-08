from datetime import date, datetime, time

import pytest

from apps.api.app.auth.schedules import AccessSchedule, DailyWindow, SHANGHAI
from apps.api.app.classrooms.assistance import AssistanceManager


pytestmark = pytest.mark.unit


def test_classroom_schedule_allows_only_open_classroom_inside_window() -> None:
    manager = AssistanceManager()
    manager.create("class-a", "org-001")
    manager.set_schedule(
        "class-a",
        AccessSchedule(date(2026, 9, 1), date(2026, 9, 30), {1}, (DailyWindow(time(14), time(18)),)),
    )
    manager.open("class-a")

    assert manager.student_creative_access_allowed("class-a", now=datetime(2026, 9, 22, 14, 0, tzinfo=SHANGHAI))
    assert not manager.student_creative_access_allowed("class-a", now=datetime(2026, 9, 22, 18, 0, tzinfo=SHANGHAI))
    assert not manager.student_creative_access_allowed("class-a", now=datetime(2026, 9, 23, 15, 0, tzinfo=SHANGHAI))


def test_classroom_schedule_persists_to_sqlite(tmp_path) -> None:
    path = tmp_path / "platform.db"
    manager = AssistanceManager(path)
    manager.create("class-a", "org-001")
    manager.set_schedule("class-a", AccessSchedule(date(2026, 9, 1), date(2026, 9, 30), {1}, (DailyWindow(time(14), time(18)),)))

    reloaded = AssistanceManager(path)

    assert reloaded.classrooms["class-a"].schedule is not None
    assert reloaded.classrooms["class-a"].schedule.weekdays == {1}
