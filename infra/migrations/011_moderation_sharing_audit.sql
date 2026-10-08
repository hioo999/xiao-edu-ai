create table if not exists moderation_events (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    actor_user_id uuid references users(id),
    target_type text not null,
    target_id uuid,
    decision text not null,
    reason text,
    created_at timestamptz not null default now()
);

create table if not exists share_links (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    project_id uuid not null references projects(id),
    scope text not null,
    expires_at timestamptz,
    revoked_at timestamptz,
    allow_download boolean not null default false,
    created_at timestamptz not null default now()
);
