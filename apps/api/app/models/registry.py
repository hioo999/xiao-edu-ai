from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import sqlite3

from cryptography.fernet import Fernet


class ModelCapability(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    MUSIC = "music"
    VIDEO = "video"
    EMBEDDING = "embedding"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    MODERATION = "moderation"


@dataclass(frozen=True)
class ModelProvider:
    provider_id: str
    organization_id: str | None
    capability: ModelCapability
    region: str
    priority: int
    api_key: str
    provider_kind: str = "custom"
    model_id: str = ""
    base_url: str = "https://api.deepseek.com"
    enabled: bool = True
    model_catalog: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicModelProvider:
    provider_id: str
    organization_id: str | None
    capability: ModelCapability
    region: str
    priority: int
    enabled: bool
    api_key: str
    provider_kind: str
    model_id: str
    base_url: str
    model_catalog: tuple[str, ...]


class SecretVault:
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()


class ProviderRegistry:
    def __init__(self, vault: SecretVault, storage_path: str | Path | None = None) -> None:
        self._vault = vault
        self._providers: dict[str, tuple[ModelProvider, str]] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("provider persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                create table if not exists model_providers (
                    provider_id text primary key,
                    organization_id text,
                    capability text not null,
                    region text not null,
                    priority integer not null,
                    encrypted_api_key text not null,
                    provider_kind text not null,
                    model_id text not null,
                    base_url text not null,
                    enabled integer not null,
                    model_catalog text not null default '[]'
                )
            """)
            columns = {row[1] for row in connection.execute("pragma table_info(model_providers)")}
            if "model_catalog" not in columns:
                connection.execute("alter table model_providers add column model_catalog text not null default '[]'")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from model_providers").fetchall()
        for row in rows:
            provider = ModelProvider(
                provider_id=row["provider_id"],
                organization_id=row["organization_id"],
                capability=ModelCapability(row["capability"]),
                region=row["region"],
                priority=row["priority"],
                api_key=self._vault.decrypt(row["encrypted_api_key"]),
                provider_kind=row["provider_kind"],
                model_id=row["model_id"],
                base_url=row["base_url"],
                enabled=bool(row["enabled"]),
                model_catalog=tuple(self._parse_model_catalog(row["model_catalog"])),
            )
            self._providers[provider.provider_id] = (provider, row["encrypted_api_key"])

    def register(self, provider: ModelProvider) -> None:
        encrypted = self._vault.encrypt(provider.api_key)
        self._providers[provider.provider_id] = (provider, encrypted)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute(
                    """
                    insert into model_providers
                    (provider_id, organization_id, capability, region, priority, encrypted_api_key, provider_kind, model_id, base_url, enabled, model_catalog)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(provider_id) do update set
                      organization_id=excluded.organization_id,
                      capability=excluded.capability,
                      region=excluded.region,
                      priority=excluded.priority,
                      encrypted_api_key=excluded.encrypted_api_key,
                      provider_kind=excluded.provider_kind,
                      model_id=excluded.model_id,
                      base_url=excluded.base_url,
                      enabled=excluded.enabled,
                      model_catalog=excluded.model_catalog
                    """,
                    (provider.provider_id, provider.organization_id, provider.capability.value, provider.region, provider.priority, encrypted, provider.provider_kind, provider.model_id, provider.base_url, int(provider.enabled), json.dumps(list(dict.fromkeys(model for model in provider.model_catalog if model.strip())))),
                )

    @staticmethod
    def _parse_model_catalog(value: str | None) -> list[str]:
        try:
            items = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return [item.strip() for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []

    def encrypted_key(self, provider_id: str) -> str:
        return self._providers[provider_id][1]

    def provider(self, provider_id: str) -> ModelProvider:
        return self._providers[provider_id][0]

    def secret_key(self, provider_id: str) -> str:
        return self._vault.decrypt(self.encrypted_key(provider_id))

    def delete(self, provider_id: str, organization_id: str | None = None) -> None:
        provider, _ = self._providers[provider_id]
        if organization_id is not None and provider.organization_id not in (None, organization_id):
            raise PermissionError("provider access denied")
        del self._providers[provider_id]
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from model_providers where provider_id = ?", (provider_id,))

    def public_providers(self, organization_id: str | None = None) -> list[PublicModelProvider]:
        return [
            PublicModelProvider(
                provider_id=provider.provider_id,
                organization_id=provider.organization_id,
                capability=provider.capability,
                region=provider.region,
                priority=provider.priority,
                enabled=provider.enabled,
                api_key=f"••••{provider.api_key[-4:]}",
                provider_kind=provider.provider_kind,
                model_id=provider.model_id,
                base_url=provider.base_url,
                model_catalog=provider.model_catalog,
            )
            for provider, _ in self._providers.values()
            if organization_id is None or provider.organization_id in (None, organization_id)
        ]

    def resolve(
        self,
        organization_id: str,
        capability: ModelCapability,
        *,
        allow_foreign: bool = False,
    ) -> ModelProvider:
        eligible = self.resolve_candidates(organization_id, capability, allow_foreign=allow_foreign)
        if not eligible:
            raise LookupError("no eligible model provider")
        return eligible[0]

    def resolve_candidates(
        self,
        organization_id: str,
        capability: ModelCapability,
        *,
        allow_foreign: bool = False,
    ) -> list[ModelProvider]:
        eligible = []
        for provider, _ in self._providers.values():
            if not provider.enabled or provider.capability != capability:
                continue
            if provider.region == "foreign" and not allow_foreign:
                continue
            if provider.organization_id not in (None, organization_id):
                continue
            eligible.append(provider)
        eligible.sort(key=lambda provider: (provider.organization_id is None, provider.priority))
        return eligible


class PostgresProviderRegistry(ProviderRegistry):
    """PostgreSQL-backed provider configuration shared by API and workers."""

    def __init__(self, vault: SecretVault, database_url: str) -> None:
        super().__init__(vault)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL provider registry requires psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""create table if not exists runtime_model_providers (
                provider_id text primary key, organization_id text, capability text not null, region text not null,
                priority integer not null, encrypted_api_key text not null, provider_kind text not null,
                model_id text not null, base_url text not null, enabled boolean not null, model_catalog text not null default '[]')""")
        self._refresh()

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select provider_id, organization_id, capability, region, priority, encrypted_api_key, provider_kind, model_id, base_url, enabled, model_catalog from runtime_model_providers")
            rows = cursor.fetchall()
        self._providers = {}
        for row in rows:
            provider = ModelProvider(str(row[0]), row[1], ModelCapability(row[2]), str(row[3]), int(row[4]), self._vault.decrypt(row[5]), str(row[6]), str(row[7]), str(row[8]), bool(row[9]), tuple(self._parse_model_catalog(row[10])))
            self._providers[provider.provider_id] = (provider, row[5])

    def register(self, provider: ModelProvider) -> None:
        encrypted = self._vault.encrypt(provider.api_key)
        catalog = json.dumps(list(dict.fromkeys(model for model in provider.model_catalog if model.strip())))
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_model_providers values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(provider_id) do update set organization_id=excluded.organization_id, capability=excluded.capability,
                region=excluded.region, priority=excluded.priority, encrypted_api_key=excluded.encrypted_api_key,
                provider_kind=excluded.provider_kind, model_id=excluded.model_id, base_url=excluded.base_url,
                enabled=excluded.enabled, model_catalog=excluded.model_catalog""", (provider.provider_id, provider.organization_id, provider.capability.value, provider.region, provider.priority, encrypted, provider.provider_kind, provider.model_id, provider.base_url, provider.enabled, catalog))
        self._providers[provider.provider_id] = (provider, encrypted)

    def delete(self, provider_id: str, organization_id: str | None = None) -> None:
        self._refresh()
        super().delete(provider_id, organization_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_model_providers where provider_id = %s", (provider_id,))

    def public_providers(self, organization_id: str | None = None) -> list[PublicModelProvider]:
        self._refresh()
        return super().public_providers(organization_id)

    def resolve_candidates(self, organization_id: str, capability: ModelCapability, *, allow_foreign: bool = False) -> list[ModelProvider]:
        self._refresh()
        return super().resolve_candidates(organization_id, capability, allow_foreign=allow_foreign)
