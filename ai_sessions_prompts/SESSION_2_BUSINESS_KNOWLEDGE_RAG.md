# EasyCRM — Codex Session 2
## Business Knowledge, Website/PDF Ingestion & Grounded AI Answers

### Outcome
An authenticated business admin can define business facts, ingest approved web pages and PDF documents, inspect/manage the knowledge library, and test **grounded, business-specific** AI responses using the model configured under Settings. Another workspace's data must never appear.

## Operating instructions for Codex
1. Read `README.md`, `docs/BRD.md`, `docs/SRS.md`, `docs/ARCHITECTURE.md`, and `docs/API_SPEC.md`, plus the previous session's implementation/handoff notes. Inspect the actual repository before changing anything. If a filename differs, locate its equivalent.
2. **Extend the existing application**. Preserve Session 1's working flows, database migrations, authentication, multi-tenant boundaries, configured Gemini/NVIDIA adapters, model settings, and white-and-blue Attio-inspired UI. Do not rewrite working modules or introduce another application framework.
3. Implement actual backend + frontend functionality; don't mask incomplete features with fabricated success states. Use mock fixtures only in tests and explicitly labeled demo/simulator modes.
4. Keep LLM credentials server-side in environment variables. Model selection is controlled in EasyCRM Settings and persisted in the database; never hardcode a model into a business workflow. Use configured provider/model and return clear errors if missing or unavailable.
5. Apply tenant filtering/authorization to every data read/write and retrieval query. Validate input, restrict uploaded content and network access, keep secrets out of responses/logs, and add tests for cross-tenant isolation.
6. Prefer simple, testable services and explicit state transitions over uncontrolled multi-agent orchestration. Add Alembic migrations for any database changes; avoid destructive migrations and don't mutate real data during tests.
7. Preserve the design system: pure-white canvas, blue accent (`#2563EB`), dark text, restrained borders, accessible controls and responsive layout. Match the attached EasyCRM reference mockup without copying Attio assets.
8. Complete the session within its stated scope. If external credentials/approvals block live verification, implement a truthful test/mocked path, label the limitation, and document exact setup steps.
9. Run relevant tests, lint/type-check/build where available. Fix regressions and provide proof of results. Do not claim tests ran if they did not.
10. End with a concise handoff: changed files, migrations, configuration, startup/test commands, passing/failing checks, known limitations, and readiness for the next session. Update README and relevant docs when implementation differs.

## Build
### A. Business profile
- Edit business name, description, category, country/state/city, service locations, website, contact details, business hours, products/services overview and sales/qualification policies.
- Mark fields optional where appropriate; validate URLs and contact formats. Display last updated and document/source provenance. Do not treat unverified extracted claims as authoritative policies.

### B. Knowledge base ingestion
- Add PDF upload with MIME/content verification, size/page limits, safe filename/storage, parsing failure handling, upload status, and removal/re-index actions.
- Add website ingestion for a user-verified/owned business website: preview target URLs, scope to same approved domain, enforce crawl page/depth/size/time limits, respect robots and rate limits, reject private/internal IPs, localhost, redirects to unsafe hosts and `file://`-style URLs (SSRF protection).
- Strip navigation noise and scripts; extract readable text and track source URL, page title, upload date, checksum, and ingestion status.
- Split into document chunks and store embeddings with workspace_id, source_id, chunk metadata. Use PostgreSQL + pgvector; supply a migration, dimension/config strategy and compatible embedding provider. Clearly separate embedding model configuration from the chat model. If embeddings are unavailable, report incomplete indexing rather than pretending RAG worked.
- Deduplicate by source fingerprint; allow re-ingestion, cancellation/failure state, and deletion of original + chunks.

### C. Retrieval and grounded responses
- Retrieval must filter by workspace_id *before* ranking and return top relevant chunks with citations (document/title/URL/section where available).
- Create a query API/service that uses the **workspace-selected model** from Session 1 to respond only using available business knowledge; explicitly acknowledge missing information instead of inventing prices, warranties, stock or policies.
- Separate retrieved content from system instructions; uploaded pages/PDFs are untrusted data. Add prompt-injection resistance and limit context/token use.
- Include basic retrieval diagnostics (source IDs, scores, response model, processing errors) in development logs without exposing PII/secrets.

### D. Frontend
- Working Business Profile editor, Knowledge Base page with Upload PDF/Add Website, ingestion statuses, source list, source preview, re-index/delete, and a 'Ask about this business' playground.
- Show source citations and 'not found in knowledge' states, progress, errors, skeletons, accessible dialogs, and responsive behavior.

## API and data design
Extend existing conventions, for example: `GET/PATCH /api/v1/business`, `POST/GET/DELETE /api/v1/knowledge/sources`, `POST /api/v1/knowledge/sources/website`, `POST /api/v1/knowledge/query`; choose final endpoint names consistent with existing `API_SPEC.md`. Store document/source/chunk/ingestion-job entities with tenant keys and documented constraints.

## Testing / acceptance gates
- Two business workspaces have different policies. The same question returns **only** the corresponding workspace content and cites its own sources.
- PDF upload → indexed status → grounded answer with citation. Re-ingestion and deletion behave correctly.
- Same-domain website ingestion works on a controlled fixture; private-IP/localhost/unsafe redirects are rejected.
- Missing key, unavailable embedding model, malformed PDF, oversize files, empty extraction and duplicate content produce clear recoverable states.
- Model selected via Settings is actually used for answer generation; no hardcoded Gemini/NVIDIA routing.
- Automated tenant isolation, parsing, retrieval, authorization and failure-path tests pass.

## Explicitly defer
Lead qualification decisions/scoring, WhatsApp, Meta/Instagram integrations, outbound campaigns, billing and voice calling. These belong in later sessions.

## End-of-session handoff
Write `docs/SESSION_2_HANDOFF.md` with architecture decisions, new tables/migrations, knowledge ingestion limits, embedding model requirements, source/citation format, test evidence, and precise Session 3 integration points.
