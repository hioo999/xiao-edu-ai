# Domain Documentation

This repository uses a multi-context layout because it contains a web application, an API, agent runtime packages, and deployment infrastructure.

## Contexts

- Root map: `CONTEXT-MAP.md`
- Web application: `apps/web/CONTEXT.md`
- API and persistence: `apps/api/CONTEXT.md`
- Agent Runtime: `packages/agent_runtime/CONTEXT.md`
- Infrastructure and deployment: `infra/CONTEXT.md`
- Cross-cutting architecture decisions: `docs/adr/`

## Consumer rules

1. Read `CONTEXT-MAP.md` first.
2. Read the context file for every area being changed.
3. Follow deeper `AGENTS.md` instructions when present.
4. Record cross-context decisions in `docs/adr/`.
5. Keep context files focused on stable boundaries, contracts, ownership, and operational constraints.
