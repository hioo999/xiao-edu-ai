create table if not exists skills (
    id uuid primary key,
    name text not null,
    version text not null,
    input_schema jsonb not null,
    output_schema jsonb not null,
    approved boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists mcp_servers (
    id uuid primary key,
    organization_id uuid references organizations(id),
    name text not null,
    encrypted_credentials text,
    capabilities text[] not null default '{}',
    approved boolean not null default false,
    created_at timestamptz not null default now()
);
