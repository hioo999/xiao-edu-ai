create table if not exists organizations (
    id uuid primary key,
    name text not null,
    created_at timestamptz not null default now()
);

create table if not exists users (
    id uuid primary key,
    organization_id uuid references organizations(id),
    username text not null unique,
    role text not null check (role in ('platform_admin', 'organization_admin', 'teacher', 'student')),
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists classes (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    name text not null,
    created_at timestamptz not null default now()
);

create table if not exists memberships (
    user_id uuid not null references users(id),
    class_id uuid not null references classes(id),
    primary key (user_id, class_id)
);

create table if not exists audit_logs (
    id uuid primary key,
    organization_id uuid references organizations(id),
    actor_user_id uuid references users(id),
    action text not null,
    target_type text,
    target_id uuid,
    created_at timestamptz not null default now()
);
