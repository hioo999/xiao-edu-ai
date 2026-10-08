create table if not exists model_providers (
    id uuid primary key,
    organization_id uuid references organizations(id),
    provider_key text not null,
    capability text not null,
    region text not null check (region in ('domestic', 'foreign')),
    encrypted_api_key text not null,
    key_suffix text not null,
    priority integer not null default 100,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    unique (organization_id, provider_key, capability)
);

create index if not exists model_providers_route_idx
    on model_providers (organization_id, capability, region, enabled, priority);
