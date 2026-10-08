create table if not exists courses (
    id uuid primary key,
    organization_id uuid not null references organizations(id),
    title text not null,
    created_by uuid not null references users(id),
    created_at timestamptz not null default now()
);

create table if not exists course_lesson_blocks (
    id uuid primary key,
    course_id uuid not null references courses(id),
    block_order integer not null,
    kind text not null,
    content jsonb not null,
    authored_by text not null check (authored_by in ('teacher', 'ai'))
);
