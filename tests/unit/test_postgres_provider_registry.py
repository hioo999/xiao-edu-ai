import sys
import types

import pytest
from cryptography.fernet import Fernet

from apps.api.app.models.registry import ModelCapability, ModelProvider, PostgresProviderRegistry, SecretVault


pytestmark = pytest.mark.unit


def test_postgres_registry_persists_encrypted_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[tuple[str, object]] = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append((statement, values))
        def fetchall(self): return []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    registry = PostgresProviderRegistry(SecretVault(Fernet.generate_key()), "postgresql://example")
    registry.register(ModelProvider("p-1", "org-1", ModelCapability.IMAGE, "domestic", 1, "secret-key"))

    persisted = next(values for statement, values in statements if "insert into runtime_model_providers" in statement.lower())
    assert persisted is not None
    assert "secret-key" not in persisted
