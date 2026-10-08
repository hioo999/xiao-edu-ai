from __future__ import annotations

from pathlib import Path
import base64
import binascii
import os
import re
from typing import Protocol
from urllib.parse import urlparse

import httpx


class AssetStore(Protocol):
    def persist(self, job_id: str, source_url: str) -> str: ...


class GeneratedAssetStore:
    """Copies expiring provider output URLs into platform-managed storage."""

    def __init__(self, root: str | Path, public_base_url: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._public_base_url = public_base_url.rstrip("/")

    def persist(self, job_id: str, source_url: str) -> str:
        if source_url.startswith("data:"):
            return self._persist_data_uri(job_id, source_url)
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("provider asset URL must use http or https")
        suffix = Path(parsed.path).suffix.lower() or ".bin"
        destination = self._root / f"{job_id}{suffix}"
        with httpx.stream("GET", source_url, timeout=180, follow_redirects=True, trust_env=False) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
        return f"{self._public_base_url}/generated-assets/{destination.name}"

    def _persist_data_uri(self, job_id: str, source: str) -> str:
        match = re.fullmatch(r"data:([^;,]+)(;base64)?,(.*)", source, re.DOTALL)
        if match is None or match.group(2) != ";base64":
            raise ValueError("provider data URI must be base64 encoded")
        try:
            payload = base64.b64decode(match.group(3), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("provider returned invalid base64 media data") from exc
        if not payload:
            raise ValueError("provider returned empty media data")
        if len(payload) > 50 * 1024 * 1024:
            raise ValueError("provider media data exceeds the 50 MB limit")
        suffix = {
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/wave": ".wav",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "video/mp4": ".mp4",
        }.get(match.group(1).lower(), ".bin")
        destination = self._root / f"{job_id}{suffix}"
        destination.write_bytes(payload)
        return f"{self._public_base_url}/generated-assets/{destination.name}"


class TencentCosAssetStore:
    """Stores generated work in a deployment-owned Tencent COS bucket."""

    def __init__(self, client: object, bucket: str, public_base_url: str, prefix: str = "generated-assets") -> None:
        self._client = client
        self._bucket = bucket
        self._public_base_url = public_base_url.rstrip("/")
        self._prefix = prefix.strip("/")

    def persist(self, job_id: str, source_url: str) -> str:
        content, suffix, content_type = self._download(source_url)
        key = f"{self._prefix}/{job_id}{suffix}"
        put_object = getattr(self._client, "put_object", None)
        if not callable(put_object):
            raise ValueError("Tencent COS client does not expose put_object")
        put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        return f"{self._public_base_url}/{key}"

    @staticmethod
    def _download(source_url: str) -> tuple[bytes, str, str]:
        if source_url.startswith("data:"):
            match = re.fullmatch(r"data:([^;,]+);base64,(.*)", source_url, re.DOTALL)
            if match is None:
                raise ValueError("provider data URI must be base64 encoded")
            try:
                content = base64.b64decode(match.group(2), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("provider returned invalid base64 media data") from exc
            if not content or len(content) > 50 * 1024 * 1024:
                raise ValueError("provider media data is empty or exceeds the 50 MB limit")
            content_type = match.group(1).lower()
            return content, TencentCosAssetStore._suffix(content_type), content_type
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("provider asset URL must use http or https")
        with httpx.Client(timeout=180, follow_redirects=True, trust_env=False) as client:
            response = client.get(source_url)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].lower()
        if not content or len(content) > 50 * 1024 * 1024:
            raise ValueError("provider media data is empty or exceeds the 50 MB limit")
        return content, Path(parsed.path).suffix.lower() or TencentCosAssetStore._suffix(content_type), content_type

    @staticmethod
    def _suffix(content_type: str) -> str:
        return {
            "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/wave": ".wav",
            "image/png": ".png", "image/jpeg": ".jpg", "video/mp4": ".mp4",
        }.get(content_type, ".bin")


def build_asset_store() -> AssetStore:
    """Build local storage by default, or Tencent COS when fully configured."""

    bucket = os.getenv("TENCENT_COS_BUCKET", "").strip()
    if not bucket:
        return GeneratedAssetStore(
            os.getenv("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets"),
            os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000"),
        )
    region = os.getenv("TENCENT_COS_REGION", "").strip()
    secret_id = os.getenv("TENCENT_COS_SECRET_ID", "").strip()
    secret_key = os.getenv("TENCENT_COS_SECRET_KEY", "").strip()
    public_base_url = os.getenv("TENCENT_COS_PUBLIC_BASE_URL", "").strip()
    if not all((region, secret_id, secret_key, public_base_url)):
        raise RuntimeError("Tencent COS requires region, secret id, secret key, and public base URL")
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise RuntimeError("Tencent COS support requires cos-python-sdk-v5") from exc
    client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))
    return TencentCosAssetStore(client, bucket, public_base_url, os.getenv("TENCENT_COS_PREFIX", "generated-assets"))
