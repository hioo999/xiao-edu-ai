from pathlib import Path

from cryptography.fernet import Fernet

from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


def test_provider_registry_reloads_encrypted_provider_from_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "platform.db"
    vault_key = Fernet.generate_key()
    first = ProviderRegistry(SecretVault(vault_key), database)
    first.register(ModelProvider("provider-001", None, ModelCapability.TEXT, "domestic", 10, "sk-secret-1234", model_id="deepseek-chat", model_catalog=("deepseek-chat", "deepseek-reasoner")))

    second = ProviderRegistry(SecretVault(vault_key), database)

    assert second.secret_key("provider-001") == "sk-secret-1234"
    assert second.public_providers()[0].api_key == "••••1234"
    assert second.public_providers()[0].model_catalog == ("deepseek-chat", "deepseek-reasoner")
