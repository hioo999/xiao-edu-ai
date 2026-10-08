create table if not exists inspiration_cases (
    id uuid primary key,
    title text not null,
    grade_min smallint not null,
    grade_max smallint not null,
    interests text[] not null default '{}',
    difficulty text not null,
    duration_minutes integer not null,
    steps jsonb not null default '[]',
    prompts jsonb not null default '[]',
    approved boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists projects (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    owner_user_id uuid not null references users(id),
    title text not null,
    current_version_id uuid,
    created_at timestamptz not null default now()
);

create table if not exists project_assets (
    id uuid primary key,
    project_id uuid not null references projects(id),
    owner_user_id uuid not null references users(id),
    kind text not null,
    storage_key text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);
