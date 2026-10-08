# Xiao Edu AI Context Map

## Product boundary

`xiao-edu-ai` is a multimodal AI learning platform for primary-school students. It provides teacher-managed accounts, guided courses, a unified agent center, webpage creation, image and video creation, student works, and operational administration.

## Contexts

| Context | Path | Responsibility |
| --- | --- | --- |
| Web | `apps/web/CONTEXT.md` | Student, teacher, and admin user interfaces. |
| API | `apps/api/CONTEXT.md` | Authentication, business APIs, persistence, quotas, audit, and provider gateways. |
| Agent Runtime | `packages/agent_runtime/CONTEXT.md` | Agent dispatch policy, agent execution contracts, skills, MCP, and expert-team orchestration. |
| Infrastructure | `infra/CONTEXT.md` | Local development, SQLite storage, Tencent Cloud deployment, backups, and operations. |

## Dependency direction

`apps/web` calls `apps/api` through typed client functions. `apps/api` owns persistence and provider credentials. `packages/agent_runtime` supplies execution policies and contracts to the API. `infra` configures runtime services but does not own product behavior.

## Current delivery priority

1. Make every admin page perform real CRUD or a clearly reported unavailable action.
2. Complete provider routing, quotas, logging, and media generation.
3. Complete student and teacher workflows against persisted data.
4. Add production safety, backups, monitoring, and deployment verification.
