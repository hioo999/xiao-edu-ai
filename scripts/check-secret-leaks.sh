#!/usr/bin/env bash
set -euo pipefail

if rg -n --hidden --glob '!.git/**' --glob '!**/node_modules/**' --glob '!pnpm-lock.yaml' \
  --glob '!apps/api/tests/**' --glob '!apps/web/.next/**' --glob '!apps/web/.next-dev/**' --glob '!apps/web/.next-stale-*/**' --glob '!**/__pycache__/**' \
  '(sk-[A-Za-z0-9_-]{12,}|AKID[A-Za-z0-9]{10,}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)' .; then
  echo "Potential secret detected" >&2
  exit 1
fi

echo "No obvious provider secrets detected"
