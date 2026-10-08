create table if not exists usage_quotas (
    id uuid primary key,
    scope_type text not null check (scope_type in ('platform', 'organization', 'class', 'student')),
    scope_id uuid not null,
    metric text not null,
    limit_amount bigint not null check (limit_amount >= 0),
    used_amount bigint not null default 0,
    reserved_amount bigint not null default 0,
    period_start timestamptz not null,
    period_end timestamptz not null,
    unique (scope_type, scope_id, metric, period_start)
);

create table if not exists usage_reservations (
    id uuid primary key,
    quota_id uuid not null references usage_quotas(id),
    task_id uuid not null unique,
    amount bigint not null check (amount > 0),
    state text not null check (state in ('reserved', 'finalized', 'released')),
    created_at timestamptz not null default now()
);
