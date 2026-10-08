import base64

import pytest

from apps.api.app.media.storage import GeneratedAssetStore, TencentCosAssetStore, build_asset_store


pytestmark = pytest.mark.unit


def test_generated_asset_store_persists_base64_audio_as_platform_url(tmp_path) -> None:
    store = GeneratedAssetStore(tmp_path, "http://localhost:8000")
    source = "data:audio/mpeg;base64," + base64.b64encode(b"audio-bytes").decode()

    url = store.persist("job-001", source)

    assert url == "http://localhost:8000/generated-assets/job-001.mp3"
    assert (tmp_path / "job-001.mp3").read_bytes() == b"audio-bytes"


@pytest.mark.parametrize("source", ["data:audio/mpeg;base64,not-base64", "data:audio/mpeg,plain-text"])
def test_generated_asset_store_rejects_invalid_data_uri(tmp_path, source: str) -> None:
    with pytest.raises(ValueError):
        GeneratedAssetStore(tmp_path, "http://localhost:8000").persist("job-001", source)


class FakeCosClient:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

    def put_object(self, **kwargs: object) -> None:
        self.arguments = kwargs


def test_tencent_cos_store_uploads_base64_media_with_platform_url() -> None:
    client = FakeCosClient()

    url = TencentCosAssetStore(client, "edu-1250000000", "https://media.example.com", "student-work").persist("job-002", "data:image/png;base64,aGVsbG8=")

    assert url == "https://media.example.com/student-work/job-002.png"
    assert client.arguments == {"Bucket": "edu-1250000000", "Key": "student-work/job-002.png", "Body": b"hello", "ContentType": "image/png"}


def test_build_asset_store_defaults_to_local_disk(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TENCENT_COS_BUCKET", raising=False)
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(tmp_path))

    assert isinstance(build_asset_store(), GeneratedAssetStore)
