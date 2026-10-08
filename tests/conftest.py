from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolate_platform_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATFORM_DB_PATH", str(tmp_path / "platform.db"))
    monkeypatch.setenv("COURSE_STORAGE_PATH", str(tmp_path / "course-materials"))
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(tmp_path / "generated-assets"))
