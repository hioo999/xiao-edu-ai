import pytest

from apps.api.app.projects.assets import Project, ProjectAsset, add_asset, allowed_transition


def test_project_can_connect_text_image_video_and_webpage_assets() -> None:
    project = Project(project_id="project-001", organization_id="org-001", owner_user_id="student-001")
    add_asset(project, ProjectAsset(asset_id="text-001", kind="text", owner_user_id="student-001"))
    add_asset(project, ProjectAsset(asset_id="image-001", kind="image", owner_user_id="student-001"))

    assert allowed_transition("text", "image")
    assert allowed_transition("image", "video")
    assert allowed_transition("video", "webpage")
    assert [asset.kind for asset in project.assets] == ["text", "image"]


def test_project_rejects_asset_from_another_user() -> None:
    project = Project(project_id="project-001", organization_id="org-001", owner_user_id="student-001")

    with pytest.raises(PermissionError):
        add_asset(project, ProjectAsset(asset_id="image-001", kind="image", owner_user_id="student-002"))
