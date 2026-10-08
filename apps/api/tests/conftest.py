from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_platform_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep test-created application services out of the local development database."""
    monkeypatch.setenv("PLATFORM_DB_PATH", str(tmp_path / "platform.db"))
    monkeypatch.setenv("COURSE_STORAGE_PATH", str(tmp_path / "course-materials"))
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(tmp_path / "generated-assets"))
    monkeypatch.setenv("WORK_ARTIFACT_STORAGE_PATH", str(tmp_path / "work-artifacts"))
    monkeypatch.setenv("DEPLOYMENT_STORAGE_PATH", str(tmp_path / "deployments"))
    monkeypatch.setenv("WORK_INTERACTION_STORAGE_PATH", str(tmp_path / "work-interactions"))
    monkeypatch.setenv("LEARNING_STORAGE_PATH", str(tmp_path / "learning"))
