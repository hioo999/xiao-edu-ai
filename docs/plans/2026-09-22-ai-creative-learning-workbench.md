# AI 创造力学习工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or **superpowers:executing-plans** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a commercial-ready, multi-tenant AI learning workbench for primary-school students with a 3D entrance, Vibe Coding HTML generation, multimodal agents, classroom controls, and configurable model providers.

**Architecture:** Use the GitHub AgentScope source as the agent runtime base, with a Next.js/React frontend and FastAPI/Python backend around it. AgentScope runs behind a provider-agnostic model gateway; PostgreSQL stores tenant and learning data, Redis handles sessions, queues, and limits, and Tencent Cloud COS stores assets. Implement a modular monolith first, with explicit boundaries for the model gateway, sandbox, and workers.

**Tech Stack:** Next.js, React, TypeScript, React Three Fiber, Three.js, Drei, FastAPI, Python, AgentScope, PostgreSQL, Redis, Celery or Arq, Tencent Cloud COS, Docker, Playwright, Pytest, Vitest.

---

## Scope Decomposition

Implement these independently testable subsystems in order:

1. Platform foundation and tenant-aware identity.
2. Model provider registry and secure gateway.
3. Student schedules, classroom sessions, and quotas.
4. 3D student shell.
5. Inspiration library, unified projects, and cross-modal asset flow.
6. HTML Vibe Coding and sandboxed preview.
7. Course editor, knowledge bases, and offline export.
8. Image, music, video, voice, and file jobs.
8. Teacher monitoring, assistance mode, moderation, and reports.
9. AgentScope agents, Skills, MCP, and expert teams.
10. Commercial hardening, observability, licensing, and release validation.

## Planned Repository Structure

```text
apps/web/{app,components,features,lib,tests}
apps/api/app/{auth,tenants,classrooms,agents,models,projects,courses,knowledge,media,moderation,reports,audit}
apps/api/tests
packages/{contracts,ui,agent-runtime,model-gateway,sandbox}
infra/{docker,migrations,scripts}
docs/{architecture,operations}
```

## Task 1: Bootstrap the Modular Monorepo

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`
- Create: `apps/web/package.json`, `apps/api/pyproject.toml`
- Create: `packages/contracts/README.md`, `packages/ui/README.md`
- Create: `docker-compose.yml`, `.env.example`, `README.md`
- Test: `apps/web/tests/smoke.test.ts`, `apps/api/tests/test_health.py`

- [ ] Define root commands for frontend, backend, tests, lint, typecheck, and local infrastructure.
- [ ] Add `GET /health` returning `{"status":"ok"}` and a frontend smoke page titled “AI 创造力学习工作台”.
- [ ] Start PostgreSQL, Redis, and local object storage through Docker Compose; keep real provider keys out of compose.
- [ ] Run `pnpm install && pnpm test && pnpm lint && pytest apps/api/tests/test_health.py -q`; expect all checks to pass.

## Task 2: Define Shared Contracts and Errors

**Files:**
- Create: `packages/contracts/src/{auth,agents,models,projects,courses,tasks,errors}.ts`
- Create: `apps/api/app/core/errors.py`
- Test: `apps/api/tests/test_contracts.py`

- [ ] Define UUID identifiers for platform, organization, user, class, workspace, and project.
- [ ] Define task states `pending`, `queued`, `running`, `succeeded`, `failed`, and `retrying`.
- [ ] Define stable errors: `AUTH_EXPIRED`, `CLASSROOM_CLOSED`, `QUOTA_EXCEEDED`, `MODEL_UNAVAILABLE`, `MODERATION_BLOCKED`, `FILE_REJECTED`, and `PREVIEW_BLOCKED`.
- [ ] Test valid parsing and rejection of invalid identifiers, states, and errors.

## Task 3: Tenant-Aware Identity and Roles

**Files:**
- Create: `apps/api/app/auth/{models,service,routes,dependencies}.py`
- Create: `apps/api/app/tenants/{models,routes}.py`
- Create: `infra/migrations/001_identity.sql`
- Create: `apps/web/app/login/page.tsx`, `apps/web/lib/auth-client.ts`
- Test: `apps/api/tests/auth/{test_login,test_tenant_isolation}.py`

- [ ] Add platform, organization, admin, teacher, class, student, membership, session, and audit tables.
- [ ] Hash passwords with Argon2id; never retain a shared initial password in plaintext after provisioning.
- [ ] Implement username/password login with short-lived access tokens and refresh tokens.
- [ ] Resolve role and organization from database membership, not browser input.
- [ ] Enforce platform-admin, organization-admin, teacher, and student guards.
- [ ] Test that students, teachers, and organization admins cannot cross tenant or class boundaries.

## Task 4: Batch Student Provisioning and Schedules

**Files:**
- Create: `apps/api/app/auth/{provisioning,schedules,provisioning_routes}.py`
- Create: `infra/migrations/002_account_schedules.sql`
- Create: `apps/web/app/admin/students/page.tsx`
- Create: `apps/web/components/students/batch-provision-form.tsx`
- Test: `apps/api/tests/auth/{test_batch_provisioning,test_schedule_rules}.py`

- [ ] Generate collision-checked usernames from prefix, count, class, and initial password; return CSV credentials.
- [ ] Import CSV names and classes with pre-validation and row-level errors; do not partially create invalid batches.
- [ ] Support start/end dates, weekdays, daily windows, lesson periods, holiday exceptions, temporary opening, and extension in `Asia/Shanghai`.
- [ ] Re-check account schedule, classroom state, feature permission, and quota on every AI request.
- [ ] Test exact boundary times, holidays, paused classrooms, expired accounts, and extensions.

## Task 5: Secure Model Provider Registry

**Files:**
- Create: `packages/model-gateway/src/{types,provider-registry,router}.ts`
- Create: `apps/api/app/models/{models,routes,credentials}.py`
- Create: `infra/migrations/003_model_providers.sql`
- Test: `apps/api/tests/models/{test_provider_registry,test_credential_redaction}.py`

- [ ] Define adapters for text, image, video, embedding, speech-to-text, text-to-speech, and moderation.
- [ ] Encrypt API keys with a server-side key or Tencent Cloud KMS; expose only masked suffixes.
- [ ] Resolve organization credentials when enabled, otherwise use the platform pool.
- [ ] Route by capability, task, region, permission, health, cost priority, and quota; retry transient failures once and then use the next eligible provider.
- [ ] Test key redaction, foreign-model denial by default, tenant isolation, and fallback behavior.

## Task 6: Quotas and Usage Metering

**Files:**
- Create: `apps/api/app/usage/{models,service,routes}.py`
- Create: `infra/migrations/004_usage_quotas.sql`
- Test: `apps/api/tests/usage/test_quota_enforcement.py`

- [ ] Track daily/monthly text, image, video, speech seconds, storage, project count, file size, and concurrent tasks at platform, organization, class, and student levels.
- [ ] Reserve quota before provider calls, release on hard failure, and finalize on success.
- [ ] Ensure provider retries do not double-charge usage.
- [ ] Expose teacher/admin summaries without secrets or raw provider payloads.

## Task 7: 3D Student Shell

**Files:**
- Create: `apps/web/app/(student)/home/page.tsx`
- Create: `apps/web/components/scene/{ai-world,feature-gate,agent-avatars,low-performance-mode}.tsx`
- Test: `apps/web/tests/home/feature-gates.spec.ts`

- [ ] Render a data-driven fixed 3D environment for chat, web, image, video, expert team, courses, and projects.
- [ ] Provide keyboard and accessible button navigation for every 3D entrance.
- [ ] Replace animated 3D objects with static cards on low-performance devices.
- [ ] Provide desktop and tablet layouts; keep mobile to management/read-only flows in the first release.
- [ ] Test that disabled class features cannot be entered and closed classrooms show a clear explanation.

## Task 7B: Inspiration Library and Unified Projects

**Files:**
- Create: `apps/api/app/inspiration/{models,routes,recommender}.py`
- Create: `apps/api/app/projects/{assets,transitions}.py`
- Create: `apps/web/app/(student)/inspiration/page.tsx`
- Create: `apps/web/app/(student)/projects/[projectId]/page.tsx`
- Create: `apps/web/components/inspiration/{case-card,case-filters,start-case-dialog}.tsx`
- Create: `infra/migrations/005_inspiration_projects.sql`
- Test: `apps/api/tests/inspiration/test_case_recommendation.py`
- Test: `apps/api/tests/projects/test_cross_modal_assets.py`
- Test: `apps/web/tests/inspiration/inspiration-flow.spec.ts`

- [ ] Seed 20–30 cases covering text, image, music, video, HTML, and integrated projects. Each case stores grade, interests, difficulty, duration, goals, steps, prompts, assets, and next-modal suggestions.
- [ ] Implement “直接开始”, “换一个主题”, “跟着步骤做”, “复制提示” and “收藏案例”. Starting a case must create a tenant-scoped project.
- [ ] Model a unified project that can hold text, image, music, video, webpage, lesson, review, and report assets.
- [ ] Implement controlled transitions: text to image prompt, image to video, music to video/webpage, video to webpage, and multi-asset showcase page.
- [ ] Test that students can only see their own projects and approved class cases, and that a cross-modal action preserves project ownership and audit context.

## Task 8: Agent Runtime Boundary

**Files:**
- Create: `packages/agent-runtime/src/{agent-types,session,dispatcher}.py`
- Create: `apps/api/app/agents/{routes,policy}.py`
- Test: `apps/api/tests/agents/test_dispatch_policy.py`

- [ ] Define agent input as tenant-scoped request, conversation, course, allowed capabilities, knowledge scopes, quota, and moderation policy.
- [ ] Keep AgentScope imports inside the runtime package and expose an application-neutral adapter.
- [ ] Deny disallowed tools, models, foreign calls, quota-exceeded tasks, closed classrooms, and unapproved MCP before execution.
- [ ] Test task routing and structured errors.

## Task 9: HTML Vibe Coding Workspace

**Files:**
- Create: `apps/api/app/projects/{models,routes,versioning}.py`
- Create: `apps/api/app/agents/html_agent.py`
- Create: `packages/sandbox/src/{preview-policy}.ts`, `packages/sandbox/src/html-sanitizer.py`
- Create: `infra/migrations/005_projects_versions.sql`
- Create: `apps/web/app/(student)/workspace/html/page.tsx`
- Create: `apps/web/components/html-workspace/{chat-panel,lesson-panel,preview-panel}.tsx`
- Test: `apps/api/tests/projects/test_versioning.py`, `apps/api/tests/sandbox/test_preview_policy.py`, `apps/web/tests/html-workspace/html-generation.spec.ts`

- [ ] Store project owner, class, current version, visibility, moderation state, and download metadata.
- [ ] Make the HTML agent return a sanitized artifact manifest, preview assets, teaching steps, challenges, and a summary; do not expose source in the student UI.
- [ ] Run previews on an isolated origin or sandboxed iframe with CSP, no cookies/platform storage, allowlisted network, resource limits, and blocked top-level navigation.
- [ ] Build a left natural-language chat panel and right `教程`/`预览` tabs. Generated source is not displayed; students can request changes, use teacher-provided read-only code blocks when a lesson includes them, and download artifacts but cannot edit source.
- [ ] Save every generation as a version and allow restoration without deleting later versions.
- [ ] Playwright-test create, modify, preview, restore, HTML download, and ZIP download.

## Task 10: Courses and Offline Exports

**Files:**
- Create: `apps/api/app/courses/{models,routes,exporter}.py`
- Create: `apps/web/app/(teacher)/courses/page.tsx`
- Create: `apps/web/components/courses/{block-editor,course-export-dialog}.tsx`
- Create: `infra/migrations/006_courses_lessons.sql`
- Test: `apps/api/tests/courses/test_export.py`, `apps/web/tests/courses/course-editor.spec.ts`

- [ ] Support text, image, video, read-only code, attachment, interaction, step, challenge, and knowledge-reference blocks.
- [ ] Let teachers attach courses to classes and approved agents.
- [ ] Add AI-generated supplemental steps marked as generated while teacher-authored blocks remain authoritative.
- [ ] Export PDF, offline HTML, and ZIP containing permitted text, media, examples, and non-AI interactions; label AI features online-only.

## Task 11: Knowledge Bases

**Files:**
- Create: `apps/api/app/knowledge/{models,routes,indexing,retrieval}.py`
- Create: `infra/migrations/007_knowledge.sql`
- Test: `apps/api/tests/knowledge/test_scope_inheritance.py`

- [ ] Support platform, organization, course, teacher, and student scopes with explicit inheritance policy.
- [ ] Asynchronously parse approved text, office, PDF, image, audio, and video files.
- [ ] Resolve documents by membership, enrollment, and inheritance; never trust client-provided scope.
- [ ] Pass only authorized documents to agents.
- [ ] Test inheritance, override, supplement, and cross-tenant denial.

## Task 12: Image, Music, Video, Voice, and File Jobs

**Files:**
- Create: `apps/api/app/media/{jobs,routes,providers}.py`
- Create: `apps/api/app/files/{upload,scanning}.py`
- Create: `apps/web/app/(student)/workspace/{image,video}/page.tsx`
- Create: `apps/web/components/media/task-status.tsx`
- Create: `infra/migrations/008_media_jobs.sql`
- Test: `apps/api/tests/media/test_job_lifecycle.py`

- [ ] Persist task type, owner, provider, quota reservation, moderation state, progress, retries, errors, and asset IDs.
- [ ] Implement image moderation, routing, COS storage, thumbnails, and project attachment.
- [ ] Implement music generation with song title, lyrics, style, emotion, preview player, download, favorite, and project attachment.
- [ ] Implement video queue priority, progress, callbacks, timeout, and output metadata.
- [ ] Implement speech-to-text, text-to-speech, course narration, webpage explanation, and video voiceover.
- [ ] Validate MIME and size, scan files, store originals, create metadata, and pass only approved content to agents.

## Task 13: Skills, MCP, and Expert Teams

**Files:**
- Create: `packages/agent-runtime/src/{skills,mcp_registry}.py`
- Create: `apps/api/app/agents/{expert_teams,tool_policy}.py`
- Create: `infra/migrations/009_tools_agents.sql`
- Test: `apps/api/tests/agents/{test_tool_policy,test_expert_team}.py`

- [ ] Store versioned platform-managed Skills with allowed inputs, output schemas, grade scope, and safety classification.
- [ ] Register only admin-approved MCP servers, encrypt credentials, and assign explicit capabilities and tenant scope.
- [ ] Implement fixed expert-team templates with coordinator, roles, handoffs, aggregation, timeout, and fallback.
- [ ] Test that students cannot register MCP, cross tenant credentials, or invoke unavailable tools.

## Task 14: Classroom Monitoring and Assistance

**Files:**
- Create: `apps/api/app/classrooms/{models,routes,assistance}.py`
- Create: `apps/web/app/(teacher)/classroom/[classId]/page.tsx`
- Create: `apps/web/components/classroom/{student-grid,assistance-banner}.tsx`
- Create: `infra/migrations/010_classrooms.sql`
- Test: `apps/api/tests/classrooms/test_assistance_mode.py`, `apps/web/tests/classroom/live-monitor.spec.ts`

- [ ] Support open, pause, resume, close, extension, and class-wide generation lock.
- [ ] Report online state, active feature, task state, lesson step, and help-needed flag.
- [ ] Default teacher view-as to read-only; explicit assistance grants scoped actions for one student.
- [ ] Show the student assistance banner and audit every view and action.
- [ ] Add class-wide and individual guidance messages without remote device control.

## Task 15: Moderation, Sharing, and Audit

**Files:**
- Create: `apps/api/app/moderation/service.py`, `apps/api/app/sharing/routes.py`, `apps/api/app/audit/service.py`
- Create: `infra/migrations/011_moderation_sharing_audit.sql`
- Test: `apps/api/tests/moderation/test_policy_modes.py`, `apps/api/tests/sharing/test_share_links.py`

- [ ] Apply classroom/free-creation policy to input, output, images, video, HTML, files, and external links.
- [ ] Blocked results must not become student-visible artifacts.
- [ ] Implement self, teacher, class, organization, public, and parent-view links with expiration, download/copy permissions, and revocation.
- [ ] Audit login, provider and credential changes, assistance, moderation, sharing, exports, deletions, and protected data access.

## Task 16: Learning Events and Reports

**Files:**
- Create: `apps/api/app/reports/{events,service,routes}.py`
- Create: `apps/web/app/(teacher)/reports/page.tsx`, `apps/web/app/(student)/reports/page.tsx`
- Create: `infra/migrations/012_learning_reports.sql`
- Test: `apps/api/tests/reports/test_report_scope.py`

- [ ] Capture login, course access, lesson completion, prompts, versions, assistance, and submissions.
- [ ] Generate reports from verified events only, with growth-oriented language and an “AI generated” label.
- [ ] Show reports to the student and assigned teacher; exclude the parent account from the first release.

## Task 17: Tencent Cloud Operations

**Files:**
- Create: `infra/docker/{api,web,worker}.Dockerfile`, `infra/docker/nginx.conf`
- Create: `infra/operations/{tencent-cloud,backup-policy,incident-runbook}.md`
- Create: `.github/workflows/ci.yml`

- [ ] Build separate non-root web, API, and worker images with secrets supplied by deployment configuration.
- [ ] Document CVM or TKE, TencentDB PostgreSQL, Redis, COS, CDN, CLS, monitoring, HTTPS, backups, and domains.
- [ ] Run frontend lint/typecheck/tests, backend format/type/unit tests, contract tests, and container builds in CI.
- [ ] Document backup retention, COS versioning, credential rotation, queue recovery, provider outage, and rollback.

## Task 18: Commercial and Security Readiness

**Files:**
- Create: `docs/architecture/license-inventory.md`
- Create: `docs/architecture/threat-model.md`
- Create: `docs/operations/privacy-and-minor-data.md`
- Create: `docs/operations/release-checklist.md`
- Create: `scripts/check-license-inventory.ts`, `scripts/check-secret-leaks.sh`
- Test: `apps/api/tests/security/test_tenant_boundaries.py`

- [ ] Record every dependency’s license, version, attribution, modification status, model-weight terms, and trademark restrictions. Flag GPL, AGPL, SSPL, BUSL, non-commercial, and research-only terms.
- [ ] Review tenant escape, credential exposure, prompt injection, malicious files, unsafe HTML, MCP privilege, teacher impersonation, and foreign routing.
- [ ] Fail CI when provider keys appear in tracked files or logs; test protected endpoints with cross-organization roles.
- [ ] Validate PRD acceptance criteria, 100-user load, classroom interruption recovery, provider fallback, export, deletion, and backup restore in staging.

## Definition of Done

- [ ] Student logs in with a platform account and reaches the 3D home.
- [ ] Student can browse inspiration cases and start a project from a case.
- [ ] A project can connect text, image, music, video, and webpage assets.
- [ ] Teacher batch-provisions students and configures schedule rules.
- [ ] Teacher opens and closes a classroom.
- [ ] Student creates and revises HTML through natural language only.
- [ ] Student previews and downloads HTML/ZIP without source in the UI.
- [ ] Teacher creates rich courses and exports them.
- [ ] Platform routes text, image, video, voice, embedding, and moderation providers.
- [ ] API keys never reach browser, student, or teacher.
- [ ] Foreign calls are denied by default and auditable when enabled.
- [ ] Teacher inspects a student and enters explicit assistance mode.
- [ ] Image, music, video, voice, file, and report jobs are asynchronous and observable.
- [ ] Skills, MCP, and expert teams are allowlisted and tenant-scoped.
- [ ] Reports are visible only to the student and assigned teacher.
- [ ] Tencent Cloud deployment, backup, restore, monitoring, and rollback are documented.
- [ ] License inventory and security review pass before commercial pilot.
