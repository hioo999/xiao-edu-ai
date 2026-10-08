from cryptography.fernet import Fernet

from apps.api.app.models.environment import register_environment_providers
from apps.api.app.models.registry import ProviderRegistry, SecretVault


def test_registers_only_configured_environment_providers(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")
    monkeypatch.setenv("DEEPSEEK_MODEL_ID", "deepseek-chat")
    monkeypatch.setenv("VOLCENGINE_ARK_API_KEY", "ark-secret")
    monkeypatch.setenv("VOLCENGINE_ARK_TEXT_MODEL_ID", "doubao-seed-text")
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))

    register_environment_providers(registry)

    providers = {provider.provider_id: provider for provider in registry.public_providers()}
    assert set(providers) == {"platform-deepseek-text", "platform-doubao-text"}
    assert providers["platform-deepseek-text"].api_key == "••••cret"
    assert providers["platform-doubao-text"].api_key == "••••cret"
