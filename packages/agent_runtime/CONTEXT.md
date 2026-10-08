# Agent Runtime Context

## Responsibility

Owns agent dispatch policy, execution contracts, skills, MCP approval boundaries, and expert-team orchestration.

## Rules

- Dispatch policy is separate from vendor API calls.
- Agent capabilities must map to real platform capabilities.
- Unapproved MCP tools must not execute.
- Expert teams are a capability within the agent system, not a replacement for the unified agent center.
