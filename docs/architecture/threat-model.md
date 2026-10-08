# Threat Model

## Trust Boundaries

- Browser is untrusted and never receives provider API keys.
- Student content enters moderation before persistence or sharing.
- HTML previews run in a sandboxed iframe with no cookies, platform storage, or top-level navigation.
- Agent tools and MCP servers are allowlisted by administrators and scoped to the organization.
- Teacher assistance is explicit, student-visible, time-bounded, and audited.

## Required Controls

- Enforce organization and class scope from server-side session context.
- Reserve quota before provider execution and finalize only on success.
- Encrypt provider credentials and rotate the encryption key through Tencent Cloud KMS.
- Scan uploaded files before indexing or agent access.
- Keep minors' data private by default; public sharing is opt-in and revocable.
