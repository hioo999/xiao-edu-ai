create table if not exists media_jobs (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    owner_user_id uuid not null references users(id),
    kind text not null,
    state text not null,
    provider_key text,
    progress smallint not null default 0,
    attempts smallint not null default 0,
    error text,
    asset_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
