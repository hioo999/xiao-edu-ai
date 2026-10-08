import sys
import types
import pytest
from apps.api.app.reports.service import LearningEvent, PostgresReportService
pytestmark = pytest.mark.unit
def test_postgres_report_service_records_parameterized_events(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*_args): return None
        def execute(self, statement, values=None): executed.append((statement, values))
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    service = PostgresReportService("postgresql://example")
    service.record(LearningEvent("student","lesson.completed","课一"))
    assert any(values == ("student", "lesson.completed", "课一") for _statement, values in executed)
