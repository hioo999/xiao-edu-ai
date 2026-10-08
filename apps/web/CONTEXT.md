# Web Context

## Responsibility

Owns student, teacher, and platform-admin interfaces, route composition, user-facing states, and calls to the API client.

## Rules

- Do not store provider secrets in the browser.
- Keep student experiences natural-language-first; do not require code editing.
- Every async action needs loading, success, empty, and failure states.
- Admin screens must use persisted API data rather than hard-coded success states.
- Keep the visual language friendly for primary-school learners while preserving dense operational views for staff.
