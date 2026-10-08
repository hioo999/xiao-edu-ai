## 2026-09-22 — Task 1: Bootstrap the Modular Monorepo

- [skill:harness-execution] [outcome:success] Git and Harness were initialized in the independent project directory.
- [skill:harness-execution] [outcome:decision] AgentScope remains an external runtime boundary; the first scaffold keeps frontend and backend package boundaries explicit.
- [skill:harness-execution] [outcome:gotcha] Harness initialization generated an unavailable local CLI dependency version; the project uses the already-installed global Harness CLI instead.
- [skill:test-driven-development] [outcome:success] The backend health and frontend title tests were observed failing before the minimal implementations were added, then passed.

## 2026-09-22 — Task 2: Define Shared Contracts and Errors

- [skill:harness-execution] [outcome:success] Added stable Python and TypeScript task states, roles, agent kinds, model capabilities, project asset kinds, lesson blocks, and error codes.
- [skill:test-driven-development] [outcome:success] The contract test failed before the Python error module existed, then passed after the minimal enums were added.

## 2026-09-22 — Task 3: Tenant-Aware Identity and Roles

- [skill:harness-execution] [outcome:success] Added an application factory, short-lived opaque Bearer sessions, organization routing, and role guards.
- [skill:test-driven-development] [outcome:success] Added failing coverage first for invalid login, missing sessions, cross-organization access, and teacher role denial; all seven auth tests now pass.
- [skill:architecture] [outcome:decision] Session resolution is kept behind `AuthService`, so the later Redis-backed session store can replace the in-memory implementation without changing route contracts.

## 2026-09-22 — Task 4: Batch Provisioning and Schedules

- [skill:harness-execution] [outcome:success] Added collision-safe batch usernames, all-or-nothing CSV validation, teacher provisioning routes, Argon2id storage, and schedule migration scaffolding.
- [skill:test-driven-development] [outcome:success] Locked exact start-inclusive/end-exclusive windows, Shanghai timezone conversion, holiday exceptions, and paused/closed classroom denial with focused tests.
- [skill:architecture] [outcome:decision] Provisioning returns initial credentials only from the explicit batch operation; persisted user records retain only password hashes.

## 2026-09-22 — Task 5: Secure Model Provider Registry

- [skill:harness-execution] [outcome:success] Added capability-aware provider registration, Fernet-encrypted API keys, masked admin views, tenant filtering, and domestic-first fallback routing.
- [skill:test-driven-development] [outcome:success] Added coverage for ciphertext storage, secret redaction, foreign-provider opt-in, tenant mismatch, and protected provider routes.
- [skill:security] [outcome:decision] Provider secrets remain server-side; the browser receives provider metadata and a four-character suffix only.

## 2026-09-22 — Task 6: Quotas and Usage Metering

- [skill:harness-execution] [outcome:success] Added quota reservations, finalization, release, and migration scaffolding for platform, organization, class, and student metrics.
- [skill:test-driven-development] [outcome:success] Verified over-limit rejection, idempotent retries, and failure release behavior before broader integration work.
- [skill:architecture] [outcome:decision] Usage is reserved before provider execution and finalized only after success, preventing provider retries from double-charging.

## 2026-09-23 — Task 7: Student Shell Start

- [skill:harness-execution] [outcome:success] Added a data-driven student feature registry and a responsive 3D-style entrance shell for text, HTML, image, music, video, agents, courses, and projects.
- [skill:test-driven-development] [outcome:success] Added feature-gate tests so disabled classroom features cannot be entered.
- [skill:gotcha] [outcome:note] The first Next production build reached type checking but the local pnpm store/network could not install Next's optional TypeScript type packages; the project was restored to its original dependency set and all repository tests remain green.

## 2026-09-23 — Tasks 7/7B: Student Shell and Inspiration Projects

- [skill:harness-execution] [outcome:success] Added grade/interest-scored inspiration cases, organization approval filtering, unified project assets, and controlled cross-modal transitions.
- [skill:test-driven-development] [outcome:success] Verified approved-case recommendation, tenant filtering, asset ownership, and transition rules with four focused backend tests.
- [skill:product] [outcome:decision] The first student experience starts from examples and projects rather than dropping students into a blank chat screen.

## 2026-09-23 — Task 9: HTML Vibe Coding Workspace Start

- [skill:harness-execution] [outcome:success] Added sanitized HTML version history, restoration, HTML/ZIP download helpers, preview CSP/sandbox policy, and the left-chat/right-tutorial-preview workspace.
- [skill:test-driven-development] [outcome:success] Verified version restoration preserves newer versions, downloads contain the current artifact, and scripts/event handlers/javascript URLs are removed.
- [skill:architecture] [outcome:decision] The current workspace uses a local demo artifact only as a UI seam; real generation will enter through the AgentScope/model-gateway boundary and must return the same version manifest.

## 2026-09-23 — Task 8: Agent Runtime Boundary

- [skill:harness-execution] [outcome:success] Added policy-gated agent dispatch and an executor protocol that keeps AgentScope behind a replaceable runtime boundary.
- [skill:test-driven-development] [outcome:success] Covered classroom closure, feature flags, quota, model health, MCP approval, foreign-model denial, and executor handoff.
- [skill:architecture] [outcome:decision] HTML generation now follows policy evaluation → runtime execution → sanitized version persistence; the UI does not own safety decisions.

## 2026-09-23 — MVP Foundation Completion

- [skill:harness-execution] [outcome:success] Completed the planned MVP foundation across course export, media lifecycle, knowledge scopes, MCP/Skills policy, expert teams, classroom assistance, moderation, sharing, reports, CI, secret scanning, containers, and Tencent Cloud operations guidance.
- [skill:verification] [outcome:success] Direct verification passes: 58 backend tests, 3 frontend tests, secret scan, and Harness validation. Full pnpm install/build remains dependent on network access to the configured mirror.
- [skill:architecture] [outcome:decision] AgentScope is isolated behind `AgentScopeExecutor`; real provider credentials and runtime deployment are intentionally external configuration, not hardcoded into the MVP.

## 2026-09-24 — Navigation Surface Completion

- [skill:harness-execution] [outcome:success] Completed the planned student, teacher, and administrator page surfaces with shared navigation metadata and responsive visual language.
- [skill:test-driven-development] [outcome:success] Added route coverage tests; all 12 student, 9 teacher, and 10 admin navigation entries resolve to actual page files or intentional dynamic routes.
- [skill:verification] [outcome:success] Next production build generated 17 routes; direct frontend tests, 58 backend tests, secret scan, and Harness validation pass.

## 2026-09-24 — Live Login Integration

- [skill:harness-execution] [outcome:success] Replaced the demonstration login action with a real `/auth/login` API client and role-based destination routing.
- [skill:security] [outcome:decision] Browser session state contains only platform identity and opaque access token; provider keys remain absent from frontend types and storage.
- [skill:test-driven-development] [outcome:success] Added API URL/session tests and CORS allowlist coverage; 59 backend and 8 frontend tests pass.
