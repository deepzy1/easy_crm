# EasyCRM

**AI-powered lead qualification and CRM** — a portfolio-first, production-minded project.

EasyCRM helps a business capture inbound leads, answer questions using verified company knowledge, qualify interested prospects through structured conversations, and hand off sales-ready opportunities to a human team.

> Status: **Planning / repository bootstrap**. This document describes intended scope, not completed functionality.

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
├── backend/                 # FastAPI application (to build)
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
├── frontend/                # React + TS (to build)
├── infrastructure/          # Docker and deployment (to build)
└── .github/workflows/       # CI (to build)
```

## Getting started with Codex

1. Create the new Git repository and copy these files to its root.
2. Ask Codex to read **all five files**, restate milestone M1 scope and implementation assumptions, and implement **only M1** with tests.
3. Require working migrations, sample seed data, `.env.example`, Docker Compose, API OpenAPI docs and basic frontend navigation before starting M2.
4. Do not paste real API keys, WhatsApp tokens, or customer personal data into prompts/repo.

### Suggested first Codex prompt

> Read README.md and docs/{BRD,SRS,ARCHITECTURE,API_SPEC}.md. Implement milestone M1 only: FastAPI/PostgreSQL backend with Alembic, workspace-isolated authentication and membership, business profiles, contacts/leads, pipeline stages, and authenticated custom form-webhook ingestion with idempotent deduplication; minimal React/TypeScript Attio-inspired white-and-blue CRM shell (Leads + Pipeline + Settings); Docker Compose, .env.example, seed demo data, tests, and run instructions. Follow documented API conventions. Do not build AI or WhatsApp yet. Report implemented endpoints, tests run, and remaining gaps; do not claim untested functionality.

## Document map

- [Business Requirements (BRD)](docs/BRD.md) — who needs EasyCRM and why.
- [Software Requirements (SRS)](docs/SRS.md) — verifiable functional/nonfunctional requirements.
- [Architecture](docs/ARCHITECTURE.md) — services, data boundaries, processing, trust model.
- [API & Technical Specification](docs/API_SPEC.md) — endpoints, payload contracts, webhook semantics.

## License

**Not yet selected.** Choose a license before publishing and verify the licenses of all dependencies and templates. Do not copy proprietary UI assets from Attio.
