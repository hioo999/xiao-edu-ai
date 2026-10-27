from __future__ import annotations

from dataclasses import dataclass

import httpx

from .registry import ModelCapability, ModelProvider, ProviderRegistry
from .calls import ModelCallLog
from apps.api.app.usage.credits import MAX_TEXT_OUTPUT_TOKENS, current_credit_meter


@dataclass(frozen=True)
class TextGeneration:
    provider_id: str
    model_id: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class AvailableModel:
    model_id: str
    display_name: str


@dataclass(frozen=True)
class ConnectionCheck:
    status: str
    message: str


class ModelGateway:
    """The only application boundary allowed to send provider credentials."""

    def __init__(self, registry: ProviderRegistry, client: httpx.Client | None = None, call_log: ModelCallLog | None = None) -> None:
        self._registry = registry
        self._client = client or httpx.Client(timeout=60, trust_env=False)
        self._call_log = call_log

    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False, provider_id: str | None = None) -> TextGeneration:
        if provider_id:
            try:
                provider = self._registry.provider(provider_id)
            except KeyError as exc:
                raise LookupError("selected model provider is unavailable") from exc
            if (
                not provider.enabled
                or provider.capability != ModelCapability.TEXT
                or provider.organization_id not in (None, organization_id)
                or (provider.region == "foreign" and not allow_foreign)
            ):
                raise LookupError("selected model provider is unavailable")
            candidates = [provider]
        else:
            candidates = self._registry.resolve_candidates(organization_id, ModelCapability.TEXT, allow_foreign=allow_foreign)
        if not candidates:
            raise LookupError("no eligible model provider")
        last_error: Exception | None = None
        unsupported_error: ValueError | None = None
        for provider in candidates:
            try:
                if provider.provider_kind in {"deepseek", "doubao", "custom", "qwen", "zhipu"}:
                    generated = self._openai_compatible(provider, prompt)
                    if self._call_log:
                        self._call_log.record(organization_id, provider.provider_id, "text", "succeeded")
                    return generated
                raise ValueError(f"unsupported provider kind: {provider.provider_kind}")
            except (httpx.HTTPError, ValueError) as exc:
                if self._call_log:
                    self._call_log.record(organization_id, provider.provider_id, "text", "failed")
                last_error = exc
                if isinstance(exc, ValueError) and str(exc).startswith("unsupported provider"):
                    unsupported_error = exc
        if unsupported_error is not None and all(provider.provider_kind not in {"deepseek", "doubao", "custom", "qwen", "zhipu"} for provider in candidates):
            raise unsupported_error
        raise ValueError("all text model providers are unavailable") from last_error

    def discover_models(self, provider_id: str) -> list[AvailableModel]:
        provider = self._registry.provider(provider_id)
        response = self._client.get(
            provider.base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {self._registry.secret_key(provider_id)}"},
        )
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            raise ValueError("provider returned an invalid model list")
        models = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                continue
            model_id = entry["id"].strip()
            if model_id:
                display_name = entry.get("name") if isinstance(entry.get("name"), str) else model_id
                models.append(AvailableModel(model_id=model_id, display_name=display_name))
        return models

    def test_connection(self, provider_id: str) -> ConnectionCheck:
        provider = self._registry.provider(provider_id)
        if provider.capability == ModelCapability.TEXT and provider.provider_kind in {"deepseek", "doubao", "custom", "qwen", "zhipu"}:
            self._openai_compatible(provider, "请仅回复 OK。", max_tokens=1)
            return ConnectionCheck("connected", "已成功完成最小生成测试，API Key、模型和接口地址可用。")
        if provider.provider_kind == "doubao" and provider.capability in {ModelCapability.IMAGE, ModelCapability.VIDEO}:
            return ConnectionCheck(
                "verification_required",
                "该图像或视频接口没有零消耗的连通检测方式。请保存配置后进行一次实际生成验证；系统不会将它误标为连接成功。",
            )
        response = self._client.get(
            provider.base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {self._registry.secret_key(provider_id)}"},
        )
        response.raise_for_status()
        return ConnectionCheck("connected", "已成功连接服务商，API Key 与接口地址可用。")

    def _openai_compatible(self, provider: ModelProvider, prompt: str, *, max_tokens: int | None = None) -> TextGeneration:
        meter = current_credit_meter()
        effective_max_tokens = max_tokens if max_tokens is not None else (MAX_TEXT_OUTPUT_TOKENS if meter else None)
        payload = {
            "model": provider.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if effective_max_tokens is not None:
            payload["max_tokens"] = effective_max_tokens
        reservation_id = meter.reserve_text(prompt, effective_max_tokens) if meter else None
        try:
            response = self._client.post(
                provider.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self._registry.secret_key(provider.provider_id)}"},
                json=payload,
            )
            response.raise_for_status()
            payload = response.json()
            try:
                content = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError("provider returned an invalid text response") from exc
            if not isinstance(content, str) or not content.strip():
                raise ValueError("provider returned empty text")
            input_tokens, output_tokens = meter.settle_text(reservation_id, prompt, content, payload.get("usage")) if meter and reservation_id else (0, 0)
            return TextGeneration(provider.provider_id, provider.model_id, content, input_tokens, output_tokens)
        except BaseException:
            if meter and reservation_id:
                meter.ledger.release(reservation_id)
            raise
