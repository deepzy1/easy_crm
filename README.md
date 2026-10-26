# EasyCRM

**AI-powered lead qualification and CRM** — a portfolio-first, production-minded project.

EasyCRM helps a business capture inbound leads, answer questions using verified company knowledge, qualify interested prospects through structured conversations, and hand off sales-ready opportunities to a human team.

> Status: **Session 1 implemented** — authenticated workspaces, CRM, dashboard, and AI model settings/playground. The broader MVP below remains the roadmap; signed webhook acceptance and production qualification are future work. See [Session 1 implementation](docs/SESSION_1.md) for the precise delivered scope and verification limits.

## Product principles

1. **Qualification first:** inbound lead capture + company-aware qualification are the MVP; autonomous prospect scraping, outbound campaigns, and voice calling are out of scope.
2. **Human control:** salespeople can take over a conversation; AI stops responding in human mode.
3. **Knowledge-grounded:** cite/retrieve business sources internally; do not invent product prices, warranties, or availability.
4. **Secure-by-default:** workspace isolation, authenticated APIs, verified inbound webhooks, auditable actions.
5. **Portfolio quality:** demonstrate robust backend design, integrations, async workflows, tests, evaluation, and a crisp UI.

## MVP user journey

1. Workspace admin creates a business profile: name, industry, website, service areas, products/services, business hours, and policies.
2. Admin adds website pages and PDFs to a company knowledge base; reviews extraction and chooses qualification criteria.
3. Business connects a custom website form through a signed webhook. WhatsApp Cloud API is the next primary messaging channel.
4. A lead arrives, is normalized and deduplicated **within the workspace**, and appears in the CRM.
5. AI drafts/responds within allowed channel constraints, retrieves relevant company information, asks follow-up questions, and extracts structured answers.
6. A deterministic qualification engine evaluates completeness, fit, and readiness. It records the score, evidence, missing fields, and suggested next action.
7. A qualified lead is assigned to a salesperson. Inbox supports manual takeover, notes, and stage updates.

## MVP features (implementation order)

| Release | Scope | Acceptance demonstration |
| --- | --- | --- |
| M1 — Foundation | Authentication, workspaces, membership, business settings, CRM contacts/leads, stage changes, custom webhook ingestion | POST a sample form submission; view deduplicated lead in pipeline |
| M2 — Intelligence | Website/PDF ingestion, retrieval, configurable qualification criteria, AI simulator, structured extraction | Run two industry-specific test conversations; inspect score and supporting evidence |
| M3 — WhatsApp | Official WhatsApp Cloud API receive/send, signature checks, idempotent processing, human takeover, message history | Test WhatsApp message → AI response → qualified CRM lead → human takeover |
| M4 — Polish | Analytics, observability, containerized deployment, tests, seeded demo workspace, portfolio walkthrough | Run documented local demo and CI checks |

**Later (not MVP):** Meta Lead Ads, Instagram DMs, external CRM sync, outbound prospecting, scheduling integrations, AI voice, multi-agent orchestration, subscriptions/billing.

## Proposed stack

- **Frontend:** React, TypeScript, Vite; accessible components; TanStack Query; optional drag-and-drop library.
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- **Data:** PostgreSQL + pgvector; object storage for document files; Redis + Celery for background work.
- **AI:** Provider adapter (Gemini first), structured outputs, scoped retrieval, configurable rule-based scoring.
- **Integration:** Meta WhatsApp Cloud API, signed source webhooks.
- **Quality:** pytest, httpx, Ruff, type checking, Playwright (core flows), Docker Compose, CI.

Versions are proposals; pin exact supported versions when implementation starts.

## UI direction

**Attio-inspired, not copied**: pure white canvas (`#FFFFFF`), near-black typography, **blue** primary accent (`#2563EB`), fine gray borders (`#E5E7EB`), restrained shadows, compact yet readable tables/Kanban, subtle glass only for popovers/AI side panels. Accessible keyboard/focus states, mobile-responsive layout. Avoid orange as a brand color.

Primary screens: Overview, Leads, Pipeline, Inbox, AI Qualification Playground, Knowledge Base, Integrations, Settings. Analytics can begin as small operational summaries.

## Target repository layout

```text
EasyCRM/
├── README.md
├── docs/
│   ├── BRD.md
│   ├── SRS.md
│   ├── ARCHITECTURE.md
│   └── API_SPEC.md
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── integrations/
│   │   ├── ai/
│   │   └── workers/
│   ├── alembic/
│   └── tests/
├── frontend/                # React + TS
├── infrastructure/          # Docker development files
└── .github/workflows/       # CI (to build)
```

## Session 1 — run locally

Run all commands from the application root, the directory containing this README and `compose.yaml`. In the supplied workspace that is `/home/deepak/Music/easy_crm/easy_crm` (the outer directory is a wrapper checkout).

**Requirements:** Ubuntu, Python 3.12+, Node.js 22 LTS (Node 20.19 also verified), npm, and PostgreSQL 16. Docker Compose is optional. Runtime Python dependencies are pinned with hashes in `backend/requirements.lock`; the frontend uses `package-lock.json`.

### Fastest start with Docker Compose

```bash
cp .env.example .env
# Edit .env: choose a local PostgreSQL password. Add optional server-side provider keys.
docker compose up --build
```

Open **http://localhost:5173** and choose **Create a workspace**. Registration creates your user, an admin membership, and the seven pipeline stages. New workspaces are empty. OpenAPI is at **http://localhost:8000/docs**, health at **http://localhost:8000/api/v1/health**. Database data persists in a named volume. The migration service runs before the backend; nothing uses `create_all` at startup.

Optional fictional demo, from another terminal:

```bash
docker compose exec backend python -m app.seed --email demo@example.com
# Choose a password at the prompt, then sign in with that email/password.
```

Compose exposes services only on loopback. Its frontend is a local Vite development server, not a production hosting configuration. The Compose password must be URL-safe because it is interpolated into the connection URI. For a URI containing special characters, URL-encode credentials in `DATABASE_URL` and adapt the Compose override accordingly.

### Ubuntu setup without Docker

Install Python/venv, PostgreSQL 16, and Node.js 22 LTS using your Ubuntu/package-source installation instructions. With PostgreSQL running:

```bash
sudo -u postgres psql
```

In `psql`:

```sql
CREATE ROLE easycrm LOGIN PASSWORD 'choose-a-local-password';
CREATE DATABASE easycrm OWNER easycrm;
CREATE DATABASE easycrm_test OWNER easycrm;
\q
```

Then:

```bash
cp .env.example .env
# Update DATABASE_URL and POSTGRES_PASSWORD to match your local PostgreSQL credentials.
make install
make migrate
make seed  # Optional: asks for a demo password; never runs automatically.
make backend
```

In another terminal at the application root:

```bash
make frontend
```

Open **http://localhost:5173**. Use **Create a workspace**, or sign in with the credentials you supplied to the seed script. The seed script creates 17 fictional records and safely does nothing if its email already exists. Do not reuse real passwords. Both localhost and 127.0.0.1 on port 5173 are allowed by default; consistently use one hostname because cookies are host-specific.

Equivalent direct backend commands:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.seed --email demo@example.com
uvicorn app.main:app --reload --port 8000 --no-access-log
```

### Environment and AI setup

`.env` belongs beside this README, **not** inside frontend or backend. See `.env.example` for all options:

- `DATABASE_URL`: SQLAlchemy PostgreSQL/psycopg URI. All services and Alembic use the same setting.
- `CORS_ORIGINS`: JSON array of exact frontend origins. Browser mutations require a trusted Origin; CLI clients can use a Bearer token.
- `COOKIE_SECURE`: `false` for local HTTP; set `true` behind production HTTPS. Sessions expire after `SESSION_TTL_SECONDS` (default one hour); sign out revokes the token.
- `GEMINI_API_KEY`, `NVIDIA_API_KEY`: optional provider credentials, exclusively server-side. Empty keys leave the CRM functional and produce actionable AI errors.
- Gemini uses Google’s paginated Models API with the configured key. The legacy `GEMINI_MODELS` variable is ignored; it cannot restrict the dropdown. Only discovered `generateContent` models compatible with the text adapter are offered.
- `NVIDIA_MODELS`: JSON array of exact chat-capable model identifiers, retained as an explicit server allowlist because NVIDIA’s generic model list does not reliably declare chat capability. Restart after editing this environment list; **Refresh Models** checks presence against NVIDIA’s `/v1/models`. Listing is not proof of inference access.
- `AI_MODELS_CACHE_SECONDS`: discovery cache TTL in seconds, default 300. **Refresh Models** bypasses it; successful model observations expire after 15 minutes. These bounded caches are per process; workspace preferences are durable in PostgreSQL.
- `AI_TIMEOUT_SECONDS`: timeout per provider request, default 60 seconds. Generation is capped at 2,048 output tokens per request. No automatic retries or provider fallbacks.

To use AI: add a provider key to `.env`, restart the backend, open **Settings → AI models**, select a provider/model, and click **Save as Default**. Changing the saved active model takes effect immediately, without a restart. **Refresh Models** retrieves metadata without generation. Search by name, exact ID, or family. **Test Model** sends one real request capped at 256 output tokens and may consume quota or incur charges. It never tests the entire catalogue. “Available” means listed; “Verified working” means a successful recent generation in this workspace. Rate-limited, access restricted, unavailable, and unknown states describe observations, not pricing. **Free-tier eligibility unverified** remains visible even after a successful test; the Models API does not establish account-specific free-tier eligibility. **AI Qualification** opens the text playground and uses the saved workspace default; it does not score leads or send messages to prospects.

The NVIDIA catalogue includes `nvidia/nemotron-3-ultra-550b-a55b`, confirmed against [NVIDIA’s official API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b-infer). Account access, quota, model retirement, and pricing are provider-controlled. Gemini follows the [generateContent REST contract](https://ai.google.dev/api/generate-content); identifiers can be checked with [models.list](https://ai.google.dev/api/models). Credentials and raw provider errors are never returned or logged. Missing/invalid credentials, restricted access, billing restrictions, unavailable models, quota limits, invalid requests, network errors, timeouts, and empty responses have separate actionable errors. Raw errors are classified internally; only authored messages and numeric upstream HTTP status are exposed. No automatic generation retries or model fallbacks occur. Failed refresh retains a clearly marked stale catalogue, and saved Playground requests do not depend on successful discovery.

The workspace-scoped discovery API is `GET /api/v1/workspaces/{ws}/ai/models?provider=gemini` (or `nvidia`), with `&refresh=true` for admin refresh. It returns exact model IDs/resource names, capabilities, family, availability, observation time, free-tier verification state, cache freshness, and any sanitized discovery error. Saving validates the discovered Gemini catalogue or configured NVIDIA chat allowlist. See [AI model upgrade and diagnostics](docs/AI_MODELS.md) for verification results and provider limitations.

### Tests and builds

Backend tests use **real PostgreSQL**, apply migrations, and clear records in the explicitly supplied test database. Only use a disposable database whose name ends in `_test`:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://easycrm:your-local-password@localhost:5432/easycrm_test'
make test
make build
cd backend
.venv/bin/alembic check
.venv/bin/ruff check app tests alembic
```

Browser tests start local servers automatically unless they are already running. The backend virtual environment and migrated `DATABASE_URL` must exist. Use an empty-key development environment for the missing-key scenarios:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
npm run format:check
```

If Chrome is installed locally, the tests also accept `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/opt/google/chrome/chrome`. Test-created accounts are fictional and remain in the selected development database; use a disposable database for QA. CI uses its own PostgreSQL service. CI configuration is provided but remote CI execution is not claimed.

### What is working

- Responsive white-and-blue React/TypeScript interface, nine navigation destinations, accessible native dialogs, empty/error/loading states, and notifications.
- Registration, login/logout, hashed opaque sessions, Argon2id passwords, workspace creation/switching, admin membership, and editable business profile.
- Lead create/view/edit/delete with confirmation, notes, search, source/stage/status filters, cursor pagination, List/Kanban switch, persistent drag-and-drop and keyboard/touch stage menus.
- PostgreSQL-backed dashboard metrics, recent leads, stage totals/values, source distribution, and basic Analytics. No invented growth rates or AI scores.
- Configurable Gemini/NVIDIA adapters, credential-presence flags, per-workspace model preferences, connection testing, real-call playground, usage/latency where supplied, and sanitized failure states.
- Alembic migrations, explicit demo seed, Docker development configuration, dependency locks, backend/browser tests, and CI workflow.

### Future sessions and current limits

Inbox, Knowledge Base, and Integrations are clearly labeled future pages. Signed form webhooks, separate contacts, assignment/invitations, durable timelines, knowledge ingestion/RAG, deterministic lead scoring, WhatsApp, automation, billing, and voice are not implemented. Source labels on leads are attribution only; they do not activate connectors. Pipeline stage and qualification status are independent fields. Values currently use USD; metrics cover all time.

This is a tested local foundation, not a production-readiness claim. Production deployment still requires HTTPS, secure cookies, a production SPA/reverse proxy, shared rate limiting, backups/retention, monitoring, and deployment-specific review. Authentication and AI request throttling are per process. There is no password reset, email verification, or membership-invitation UI yet.

For verified results, screenshot evidence, and exact API differences from the draft specification, see [Session 1 delivery notes](docs/SESSION_1.md). Product requirements and the original architecture documents are preserved.

## Document map

- [Business Requirements (BRD)](docs/BRD.md) — who needs EasyCRM and why.
- [Software Requirements (SRS)](docs/SRS.md) — verifiable functional/nonfunctional requirements.
- [Architecture](docs/ARCHITECTURE.md) — services, data boundaries, processing, trust model.
- [API & Technical Specification](docs/API_SPEC.md) — endpoints, payload contracts, webhook semantics.

## License

**Not yet selected.** Choose a license before publishing and verify the licenses of all dependencies and templates. Do not copy proprietary UI assets from Attio.
