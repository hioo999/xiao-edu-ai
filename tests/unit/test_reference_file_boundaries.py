import pytest

from apps.api.app.media.reference_images import reference_path


pytestmark = pytest.mark.unit


def test_reference_image_cannot_follow_a_symlinked_owner_directory(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "reference-image.png").write_bytes(b"\x89PNG\r\n\x1a\nsecret")
    (root / "references" / "school").mkdir(parents=True)
    (root / "references" / "school" / "student").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(root))
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    with pytest.raises(ValueError):
        reference_path("http://localhost:8000/generated-assets/references/school/student/reference-image.png", "school", "student")


def test_reference_image_rejects_traversal_in_identity_fields(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    owner = root / "references" / "student"
    owner.mkdir(parents=True)
    (root / "references" / "school").mkdir()
    (owner / "reference-image.png").write_bytes(b"\x89PNG\r\n\x1a\nsecret")
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(root))
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    with pytest.raises(ValueError):
        reference_path("http://localhost:8000/generated-assets/references/school/../student/reference-image.png", "school/..", "student")
