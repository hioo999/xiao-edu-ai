# Infrastructure Context

## Responsibility

Owns environment variables, process startup, Tencent Cloud deployment, SQLite and file-storage paths, backups, health checks, and operational runbooks.

## Rules

- Keep `PROVIDER_ENCRYPTION_KEY` stable across restarts and deployments.
- Back up the SQLite database and generated/course-material directories together.
- Never put real API keys into tracked files.
- Production configuration must have a documented rollback path.
