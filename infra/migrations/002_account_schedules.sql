create table if not exists account_access_schedules (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    user_id uuid not null references users(id),
    start_date date not null,
    end_date date not null,
    weekdays smallint[] not null,
    daily_windows jsonb not null,
    holiday_exceptions date[] not null default '{}',
    temporary_open_until timestamptz,
    created_at timestamptz not null default now(),
    check (end_date >= start_date)
);

create index if not exists account_access_schedules_user_idx
    on account_access_schedules (user_id, start_date, end_date);
