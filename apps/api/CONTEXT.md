# API Context

## Responsibility

Owns authentication, authorization, domain services, SQLite persistence, provider credentials, model/media gateways, quotas, audit records, and API contracts.

## Rules

- Secrets are encrypted at rest and never returned to clients.
- Role and organization boundaries are enforced server-side.
- Student and teacher actions must be attributable to a user and organization.
- Provider failures must produce safe, user-facing errors without leaking credentials.
- SQLite remains the current production database; file storage and backups must be explicit.
