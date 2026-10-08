from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from apps.api.app.models.registry import ModelProvider, ProviderRegistry

from .jobs import MediaJob


@dataclass(frozen=True)
class MediaGenerationResult:
    state: str
    preview_url: str = ""
    external_task_id: str | None = None


class MediaProviderGateway:
    """Vendor boundary for media generation; credentials never leave the server."""

    def __init__(self, registry: ProviderRegistry, client: httpx.Client | None = None) -> None:
        self._registry = registry
        self._client = client or httpx.Client(timeout=90, trust_env=False)

    def submit(self, provider: ModelProvider, job: MediaJob) -> MediaGenerationResult:
        if provider.provider_kind not in {"doubao", "custom", "openai_compatible", "qwen"}:
            raise ValueError(f"unsupported media provider kind: {provider.provider_kind}")
        if job.kind == "image":
            response = self._client.post(
                self._endpoint(provider, "/images/generations"),
                headers=self._headers(provider),
                json={"model": provider.model_id, "prompt": job.prompt, "response_format": "url", **({"image_url": job.reference_image_url} if job.reference_image_url else {})},
            )
            response.raise_for_status()
            return MediaGenerationResult(state="succeeded", preview_url=self._image_url(response.json()))
        if job.kind == "video":
            response = self._client.post(
                self._endpoint(provider, "/contents/generations/tasks"),
                headers=self._headers(provider),
                json={"model": provider.model_id, "content": [{"type": "text", "text": job.prompt}, *([{"type": "image_url", "image_url": {"url": job.reference_image_url}}] if job.reference_image_url else [])], "ratio": "16:9", "duration": 5},
            )
            response.raise_for_status()
            task_id = self._task_id(response.json())
            return MediaGenerationResult(state="running", external_task_id=task_id)
        if job.kind == "voice":
            response = self._client.post(
                self._endpoint(provider, "/audio/speech"),
                headers=self._headers(provider),
                json={"model": provider.model_id, "input": job.prompt, "voice": "alloy", "response_format": "mp3"},
            )
            response.raise_for_status()
            return MediaGenerationResult(state="succeeded", preview_url=self._audio_url(response.json()))
        if job.kind == "music":
            response = self._client.post(
                self._endpoint(provider, "/audio/music/generations"),
                headers=self._headers(provider),
                json={"model": provider.model_id, "prompt": job.prompt, "response_format": "url"},
            )
            response.raise_for_status()
            return MediaGenerationResult(state="succeeded", preview_url=self._audio_url(response.json()))
        raise ValueError(f"unsupported media kind: {job.kind}")

    def poll(self, provider: ModelProvider, external_task_id: str) -> MediaGenerationResult:
        if provider.provider_kind not in {"doubao", "custom", "openai_compatible", "qwen"}:
            raise ValueError(f"unsupported media provider kind: {provider.provider_kind}")
        response = self._client.get(
            self._endpoint(provider, "/contents/generations/tasks"),
            headers=self._headers(provider),
            params=[("filter.task_ids", external_task_id)],
        )
        response.raise_for_status()
        payload = response.json()
        task = self._task(payload, external_task_id)
        state = str(task.get("status") or task.get("state") or "running").lower()
        if state in {"succeeded", "success", "completed"}:
            return MediaGenerationResult(state="succeeded", preview_url=self._video_url(task))
        if state in {"failed", "error", "cancelled"}:
            raise ValueError(str(task.get("error") or task.get("message") or "provider video generation failed"))
        return MediaGenerationResult(state="running")

    def _headers(self, provider: ModelProvider) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._registry.secret_key(provider.provider_id)}", "Content-Type": "application/json"}

    @staticmethod
    def _endpoint(provider: ModelProvider, path: str) -> str:
        base_url = provider.base_url.rstrip("/")
        if provider.provider_kind == "doubao" and not base_url.endswith("/api/v3"):
            base_url = f"{base_url}/api/v3"
        return f"{base_url}{path}"

    @staticmethod
    def _image_url(payload: dict[str, Any]) -> str:
        try:
            value = payload["data"][0]["url"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("provider returned an invalid image response") from exc
        if not isinstance(value, str) or not value:
            raise ValueError("provider returned an empty image URL")
        return value

    @staticmethod
    def _task_id(payload: dict[str, Any]) -> str:
        for key in ("id", "task_id", "taskId"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        raise ValueError("provider returned no video task ID")

    @staticmethod
    def _video_url(payload: dict[str, Any]) -> str:
        candidates = [
            payload.get("video_url"),
            payload.get("url"),
            payload.get("content", {}).get("video_url") if isinstance(payload.get("content"), dict) else None,
            payload.get("output", {}).get("video_url") if isinstance(payload.get("output"), dict) else None,
        ]
        for value in candidates:
            if isinstance(value, str) and value:
                return value
        raise ValueError("provider returned no video URL")

    @staticmethod
    def _audio_url(payload: dict[str, Any]) -> str:
        candidates = [
            payload.get("audio_url"),
            payload.get("audioUrl"),
            payload.get("url"),
            payload.get("output", {}).get("audio_url") if isinstance(payload.get("output"), dict) else None,
            payload.get("data", [{}])[0].get("url") if isinstance(payload.get("data"), list) and payload.get("data") and isinstance(payload.get("data")[0], dict) else None,
        ]
        for value in candidates:
            if isinstance(value, str) and value:
                return value
        encoded = payload.get("base64") or payload.get("audio") or payload.get("data")
        if isinstance(encoded, str) and encoded:
            return encoded if encoded.startswith("data:") else f"data:audio/mpeg;base64,{encoded}"
        raise ValueError("provider returned no audio URL")

    @staticmethod
    def _task(payload: dict[str, Any], external_task_id: str) -> dict[str, Any]:
        items = payload.get("items") or payload.get("data")
        if not isinstance(items, list):
            raise ValueError("provider returned an invalid video task response")
        for item in items:
            if isinstance(item, dict) and item.get("id") == external_task_id:
                return item
        raise ValueError("provider returned no matching video task")
