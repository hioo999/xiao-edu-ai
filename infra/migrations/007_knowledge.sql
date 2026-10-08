create table if not exists knowledge_documents (
    id uuid primary key,
    organization_id uuid references organizations(id),
    scope text not null,
    scope_id uuid not null,
    title text not null,
    storage_key text not null,
    indexing_state text not null default 'pending',
    created_at timestamptz not null default now()
);
