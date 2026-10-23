import pytest
from cryptography.fernet import Fernet

from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


def test_provider_key_is_encrypted_and_public_view_is_masked() -> None:
    vault = SecretVault(Fernet.generate_key())
    registry = ProviderRegistry(vault)
    registry.register(
        ModelProvider(
            provider_id="domestic-text",
            organization_id="org-001",
            capability=ModelCapability.TEXT,
            region="domestic",
            priority=10,
            api_key="sk-secret-key-1234",
        )
    )

    public_provider = registry.public_providers()[0]

    assert public_provider.api_key == "••••1234"
    assert registry.encrypted_key("domestic-text") != "sk-secret-key-1234"
    assert registry.secret_key("domestic-text") == "sk-secret-key-1234"


def test_unreadable_persisted_provider_does_not_block_registry_startup(tmp_path) -> None:
    storage_path = tmp_path / "platform.db"
    first_registry = ProviderRegistry(SecretVault(Fernet.generate_key()), storage_path=storage_path)
    first_registry.register(
        ModelProvider(
            provider_id="stale-provider",
            organization_id="org-001",
            capability=ModelCapability.TEXT,
            region="domestic",
            priority=10,
            api_key="old-secret",
        )
    )

    second_registry = ProviderRegistry(SecretVault(Fernet.generate_key()), storage_path=storage_path)

    assert second_registry.public_providers() == []

    second_registry.register(
        ModelProvider(
            provider_id="stale-provider",
            organization_id="org-001",
            capability=ModelCapability.TEXT,
            region="domestic",
            priority=10,
            api_key="new-secret",
        )
    )
    assert second_registry.secret_key("stale-provider") == "new-secret"


def test_foreign_provider_is_denied_by_default_and_domestic_fallback_is_selected() -> None:
    vault = SecretVault(Fernet.generate_key())
    registry = ProviderRegistry(vault)
    registry.register(
        ModelProvider(
            provider_id="foreign-text",
            organization_id="org-001",
            capability=ModelCapability.TEXT,
            region="foreign",
            priority=1,
            api_key="foreign-secret",
        )
    )
    registry.register(
        ModelProvider(
            provider_id="platform-text",
            organization_id=None,
            capability=ModelCapability.TEXT,
            region="domestic",
            priority=5,
            api_key="platform-secret",
        )
    )

    selected = registry.resolve("org-001", ModelCapability.TEXT)

    assert selected.provider_id == "platform-text"


def test_foreign_provider_requires_explicit_opt_in_and_tenant_match() -> None:
    vault = SecretVault(Fernet.generate_key())
    registry = ProviderRegistry(vault)
    registry.register(
        ModelProvider(
            provider_id="foreign-text",
            organization_id="org-001",
            capability=ModelCapability.TEXT,
            region="foreign",
            priority=1,
            api_key="foreign-secret",
        )
    )

    assert registry.resolve("org-001", ModelCapability.TEXT, allow_foreign=True).provider_id == "foreign-text"
    with pytest.raises(LookupError):
        registry.resolve("org-002", ModelCapability.TEXT, allow_foreign=True)
