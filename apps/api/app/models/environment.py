from __future__ import annotations

import os

from dotenv import load_dotenv

from .registry import ModelCapability, ModelProvider, ProviderRegistry


def register_environment_providers(registry: ProviderRegistry) -> None:
    """Register platform-owned providers without persisting environment secrets."""
    load_dotenv()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        registry.register(
            ModelProvider(
                provider_id="platform-deepseek-text",
                organization_id=None,
                capability=ModelCapability.TEXT,
                region="domestic",
                priority=20,
                api_key=deepseek_key,
                provider_kind="deepseek",
                model_id=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
        )

    ark_key = os.getenv("VOLCENGINE_ARK_API_KEY")
    ark_text_model = os.getenv("VOLCENGINE_ARK_TEXT_MODEL_ID")
    if ark_key and ark_text_model:
        registry.register(
            ModelProvider(
                provider_id="platform-doubao-text",
                organization_id=None,
                capability=ModelCapability.TEXT,
                region="domestic",
                priority=10,
                api_key=ark_key,
                provider_kind="doubao",
                model_id=ark_text_model,
                base_url=os.getenv("VOLCENGINE_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
            )
        )
