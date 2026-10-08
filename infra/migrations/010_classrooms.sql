create table if not exists classroom_sessions (
    id uuid primary key,
    class_id uuid not null references classes(id),
    state text not null check (state in ('paused', 'open', 'closed')),
    opened_at timestamptz,
    closed_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists assistance_grants (
    id uuid primary key,
    class_id uuid not null references classes(id),
    teacher_id uuid not null references users(id),
    student_id uuid not null references users(id),
    revoked_at timestamptz,
    created_at timestamptz not null default now()
);
