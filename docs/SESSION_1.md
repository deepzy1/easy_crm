# Session 1 — delivered foundation

Verified locally on 26 October 2026. This document supplements the original product requirements and draft API; BRD, SRS, ARCHITECTURE, and API_SPEC remain unchanged. Session 1 follows `ai_sessions_prompts/s1.md`, including AI model settings/playground and deferring live integrations. It does not claim completion of the broader M1 signed-webhook milestone.

## Delivered behavior

React 19 / TypeScript / Vite / Tailwind and FastAPI / SQLAlchemy / Alembic form one modular application backed by PostgreSQL. Registration atomically creates a user, workspace, admin membership, seven stages, and provider-configuration records. A person can create and switch between workspaces. Each workspace starts empty unless the explicit demo script is run.

Lead management includes create, detail/edit, confirmed permanent deletion, notes, case-insensitive search, stage/status/source filtering, stable cursor pagination, Kanban/List switching, drag-and-drop persistence, and keyboard/touch stage selection. Qualification status is independent of pipeline stage; moving to Qualified does not run an AI scorer or modify qualification status. Contact details are stored on leads for Session 1; contacts, owners, scoring, assignment, and durable event history are future domains.

Dashboard and Analytics aggregate the current workspace’s records: total leads, qualified status count, active count excluding closed/disqualified, qualification rate, recent records, stage counts/values, and source distribution. Metrics cover all time; monetary values use USD. Small bar marks use actual aggregate counts, not invented historical trends. Lead source tags are manual provenance, not live channel connections.

Settings supports the business profile and per-workspace Gemini/NVIDIA model preference. Gemini discovery now uses Google’s paginated Models API; NVIDIA retains a configurable chat allowlist with provider presence refresh. See [AI model upgrade](AI_MODELS.md) for the subsequent focused improvement and current verification. Saving another model immediately affects later calls. Connection tests make a real small generation request through the selected adapter; the playground uses the saved preference. Normalized output includes provider, exact model, final text, latency, and optional token counts. There are no automatic retries, fallback calls, or simulated successes. Missing credentials, stale catalogue selection, denied model access, provider errors, timeouts, and unusable output produce sanitized errors. The response budget is 2,048 tokens; reasoning models can exhaust that budget and return an explicit unusable-output error.

Inbox, Knowledge Base, and Integrations explain their future purpose. No signed webhooks, scraping, PDF ingestion, retrieval, qualification engine, WhatsApp, outbound messaging, billing, or autonomous agents are enabled.

## Security boundaries

- Passwords use Argon2id; password whitespace is preserved. Tokens are opaque random values; only SHA-256 token hashes and expirations are stored in PostgreSQL.
- The SPA uses an HttpOnly, SameSite=Strict cookie with a one-hour default expiry. It does not store credentials in localStorage. API clients can use the returned Bearer token. Logout deletes the corresponding session.
- Browser mutations require an allowed Origin; CORS allows only configured exact origins. Request bodies are bounded at 64 KiB, prompts at 8,000 characters, generation at 2,048 output tokens. Single-process sliding-window limits cover authentication and AI calls.
- Every workspace route checks membership. All lead, note, aggregate, stage, and preference operations scope their queries to that workspace. Composite foreign keys additionally prevent cross-workspace stage/note associations.
- Admin checks protect business-profile changes, preference changes, and connection tests. Members can manage leads and use the playground. Invitation and membership-management UIs are deferred.
- API keys remain in environment configuration. Settings returns presence flags and catalogue identifiers, never secrets. Raw provider errors, request bodies, query values, passwords, and headers are omitted from structured logs. Validation errors contain field locations/types only.
- Local HTTP requires `COOKIE_SECURE=false`. Production requires TLS and secure cookies. The Compose database is bound to loopback and retains data in a volume. Secrets and build/runtime output are excluded from Git and the Docker build context.

## Implemented API

OpenAPI at `/docs` describes the actual schemas. All endpoints below are under `/api/v1`.

- Health: `GET /health` checks database connectivity and returns 503 on failure.
- Identity: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`.
- Workspaces: `GET/POST /workspaces`, `GET/PATCH /workspaces/{ws}/business-profile`.
- Pipeline: `GET /workspaces/{ws}/stages`.
- CRM: `GET/POST /workspaces/{ws}/leads`, `GET/PATCH/DELETE /workspaces/{ws}/leads/{lead_id}`, `POST /workspaces/{ws}/leads/{lead_id}/stage`.
- Notes: `GET/POST /workspaces/{ws}/leads/{lead_id}/notes`.
- Metrics: `GET /workspaces/{ws}/analytics/overview`.
- AI: `GET /workspaces/{ws}/ai/models?provider=gemini|nvidia[&refresh=true]`, `GET/PUT /workspaces/{ws}/ai/settings`, `POST /workspaces/{ws}/ai/test`, `POST /workspaces/{ws}/ai/generate`.

Lead collections return `{items, next_cursor}` with `limit`, `cursor`, `q`, `stage_id`, `status`, and `source` parameters. IDs are UUID strings and timestamps UTC. Lead PATCH currently accepts the complete editable lead form; partial patch semantics are deferred. The stage endpoint accepts only `{stage_id}`.

The draft API’s contact-based payloads and `pipeline_stage/source_type/qualification_status` aliases have not been implemented. Session 1 uses flattened `name/company/email/phone/title`, `stage_id`, `source`, and `status`, as documented by generated OpenAPI. The UI groups leads by stage from these two endpoints rather than a separate `/pipeline` response. Error envelopes follow the draft `{error: {code, message, request_id, details}}` convention for user APIs; health intentionally has a compact readiness response.

## Validation evidence

- **Passed:** 37 pytest cases against isolated PostgreSQL 16, using Alembic migrations. Covers auth/hash/expiry/revocation, cookie/origin checks, password whitespace, bounded requests, lead CRUD/validation/search/filters/pagination/notes, metrics, stage persistence, negative tenant checks, composite FK isolation, admin permissions, AI settings, exact provider payloads, normalization, missing credentials, invalid models, timeouts, sanitized errors, and no retries.
- **Passed:** 4 Playwright browser scenarios in installed Chrome 154: registration and CRM CRUD/notes/drag-and-drop/reload/search/delete confirmation; model preference reload and missing-key errors in connection test/playground; workspace isolation/logout; mobile navigation/dialogs and 390px overflow check.
- **Passed:** TypeScript check and production Vite build; Ruff checks and formatting; Prettier formatting check.
- **Passed:** fresh migration, `alembic check` with no model drift, disposable database downgrade to base and reapply to `be78ada7931e`, and repeated migration/seed with record preservation and no duplicate seed records.
- **Passed:** live local backend health and database-backed UI reads. Native PostgreSQL and the local dev server were used for browser verification. Playwright also verified automatic backend/frontend startup with the final configuration.
- **Passed:** `docker compose --env-file .env.example config --no-env-resolution --quiet` validated the Compose structure/interpolation. `.env` loading is documented for actual startup.
- **Passed:** npm audit of the full frontend tree and pip-audit of all 38 resolved runtime Python packages reported zero known vulnerabilities at verification time. The Python audit resolution exactly matched `requirements.lock`. Dependency advisories can change.
- **Not executed:** Docker image builds and container startup; the Docker daemon socket denied access in this environment (the initial sandboxed launcher also could not create its runtime directory). The native application path was tested instead.
- **Not executed:** live Gemini/NVIDIA generation. No real credentials were supplied. Adapters have mocked contract/error tests and real missing-key browser/API tests; account access, model availability, quota, latency, and successful upstream inference remain unverified.
- **Not executed:** remote GitHub Actions, production deployment/load, formal WCAG audit, or backup/restore exercises. One upstream Starlette TestClient deprecation warning about httpx is present; assertions pass.

Screenshots use **fictional, explicitly seeded** records:

- [Desktop dashboard](evidence/dashboard-desktop.png)
- [AI model settings](evidence/ai-settings-desktop.png)
- [Mobile dashboard](evidence/dashboard-mobile.png)
- [Machine-readable verification summary](evidence/verification.json)

## Files and operations

Backend domains live in `backend/app/{api,core,models,schemas,services,ai}`. The immutable initial migration is in `backend/alembic/versions`. Runtime/dev dependency lockfiles contain package hashes. Tests require an explicitly named disposable `_test` database and refuse the default application database.

Frontend state and requests use TanStack Query with no automatic request retries. All values originate from APIs; the seed records only exist in `backend/app/seed.py`. Reusable UI primitives cover buttons, inputs, selects, textareas, cards, tables, tabs, the sidebar, badges, dialogs, and notifications. Native dialogs provide focus containment; provider choice supports arrow keys; stage menus provide an alternative to dragging. Mobile Kanban scrolls horizontally within its own container, and lead lists scroll inside their table wrapper.

Run commands and environment setup are in the [README](../README.md). `make install`, `make migrate`, `make seed`, `make backend`, `make frontend`, `make test`, and `make build` wrap the direct commands. Docker definitions are local development configuration, not a production deployment. Redis/Celery are intentionally absent because Session 1 has no background work.

Project licensing remains unselected. See [direct dependency inventory](THIRD_PARTY.md). No commits or pushes were made.
