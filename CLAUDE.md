# CLAUDE.md

## Communication
- Always reply in French, even if the user writes in English.
- Explain things simply: the user is not a developer. Avoid jargon, or explain it in plain words when it is needed.

## Code conventions
- Keep code, file names, and technical comments in English.

## Project engineering rules (NEWTON)
- Pricing is deterministic: an LLM never produces a price. Every AI-extracted value cites document + page and stays "to validate" until a human approves it.
- No simulated or assumed external integration. Never report a test as passing without running it.
- Multi-tenant isolation: every new table gets `company_id`, ENABLE + FORCE RLS, policies, and explicit grants to `newton_app` in its migration. `tests/test_schema_guard.py` enforces this.
- The API runs as `newton_app` (no BYPASSRLS, owns nothing). Migrations/admin commands use the owner role.
- Audit every business change via `newton.core.audit.record` in the same transaction.
- Demo data only via `newton.cli seed-demo` (companies flagged `is_demo`).
- Secrets only via environment variables (`.env`, never committed).
- Run tests: `docker compose --profile tools run --rm test`. Lint API: ruff (check + format). Web: `npm run lint`, `npm run typecheck`, `npm run build` (run ESLint in Docker/node 22 on this Windows machine: host Node runs out of memory).
- Money: `NUMERIC(14,4)` / `Decimal`, never float.

## Safety
- Before any significant action (deleting files, installing packages, running risky commands), ask the user for approval first.
