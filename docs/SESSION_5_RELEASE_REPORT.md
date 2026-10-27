# Session 5 release report

Executed locally on **27 October 2026 (Asia/Kolkata)**. Outcome: an incrementally extended, locally tested portfolio MVP with reviewed ingestion, operational analytics and production configuration. **Not a deployed production release.** No commits, pushes, real data migrations or external messages were performed.

## Audit and prioritized repairs

Read README, BRD, SRS, architecture/API drafts, Session 3/4 handoffs and actual source/tests before editing. The checkout did **not** contain Session 2 website/PDF ingestion despite the session-completion assumption; reviewed-text retrieval already existed. Graphify guidance was consulted; no existing graph was available, so source/contracts/tests supplied the implementation evidence.

1. **P0 — Missing knowledge ingestion:** replaced the Knowledge Base placeholder with authorized bounded HTTPS and text-PDF imports, persisted processing/ready/failed states, review/edit/approval, approved-source search and confirmed removal. Reused the existing workspace-scoped source store and lexical/citation path; no second RAG service or vector dependency. Imports never auto-publish.
2. **P0 — Security/resilience gaps:** added atomic shared PostgreSQL throttles, production startup configuration/schema checks, liveness/readiness, worker heartbeat, database connection/statement bounds and correlation IDs on early failures. Added sanitized receipt/worker logs linking generated request ID to durable receipt ID. Preserved conservative retry/unknown-send rules and human-control versions.
3. **P0 — Subject deletion left minimized receipts:** made deletion admin-only, required paused integrations/drained intake, redacted matched receipt content, cascaded subject history, added audited export/erase and a working export download. Intake takes a key-share integration lock compatible with outbound policy locking and conflicting with explicit deactivation/erasure. A full-regression test caught an initially too-strong lock; the compatible lock and new concurrent deactivation test pass.
4. **P1 — Analytics lacked windows and failures:** implemented UTC cohort controls, current status/source/stage distributions, inbound-source counts, qualification denominator, handoff conversations, receipt/message failures, unknown sends and real measured timing samples. Definitions/exclusions and empty states are visible; no fabricated trends/revenue metrics.
5. **P1 — Deployment/demo evidence:** added compiled-SPA Nginx deployment, constrained non-root API/worker production Compose, Poppler packaging, explicit fictional furnishing seed/policy, evaluation pack, benchmark, backup/restore drill and portfolio/demo docs. Native dialogs are centered and new screens have responsive layouts and accessible form/control states.

## Changed areas

- Backend: `api/{knowledge,operations,channels,crm}.py`, `services/{knowledge,operations,qualification,channels,webhooks}.py`, `core/{config,database,security,telemetry}.py`, `main.py`, `models/entities.py`, resource-limited `pdf_extract.py`, worker/maintenance commands and `seed_portfolio.py`.
- Migration: `backend/alembic/versions/c82d4f7e1a50_session_5_release.py`, parent `01e3724d4b96`. Additive source metadata, nullable intake processing completion, rate counters, worker heartbeat and privacy audit. Existing sources default to ready/text; prior approvals and CRM rows remain intact. Preservation/downgrade/reapply/drift tests pass. Do not downgrade real data without a reviewed plan.
- Frontend: `Knowledge.tsx`, `Analytics.tsx`, navigation, lead export/deletion explanation, source-editor guidance, styling and browser regression.
- Infrastructure: production Compose, Nginx/SPA Dockerfile, runtime Poppler installation, image source copy excluding test launchers, environment sample, Make targets, CI checks and ignored backup paths.
- Evidence/tooling: `tests/test_release.py`, `tests/test_evaluation.py`, JSON evaluation fixtures, `scripts/{evaluate,benchmark}.py`, actual screenshots/JSON under docs/evidence. Earlier screenshot paths were refreshed by the existing browser suite.
- Docs: README, implemented architecture and sequence diagrams, actual API additions, [deployment/operations](DEPLOYMENT.md), [demo recording guide](DEMO_WALKTHROUGH.md), [portfolio summary/resume templates](PORTFOLIO_SUMMARY.md), fictional source text.

## Configuration and startup

Keep `.env` at the application root; no real credentials were added or printed. Existing Gemini/NVIDIA settings/selection persist and remain authoritative for workflows. No Python/npm dependencies changed. Ubuntu local setup additionally requires `poppler-utils`; the backend Dockerfile installs it.

```bash
make migrate
make backend
# Separate terminals at the application root:
make frontend
make channel-worker
# Explicit fictional seed, prompts for a password:
make seed-portfolio
```

New flags: `ENVIRONMENT=development|production`, `REQUIRE_WORKER_READY=false|true`. Production Compose sets production/secure-cookie/worker-readiness flags and requires operator HTTPS CORS origins plus a stable 32+ character webhook master key. AI timeout is 1–120 seconds (default 60); provider failure never silently switches a model or fabricates a response. Existing provider keys remain server-side.

The existing development runtime is separate from this test execution. To see source updates in code-baked containers, rebuild them after migration; restarting old images is insufficient. See [DEPLOYMENT.md](DEPLOYMENT.md) before using the separate production Compose file/volume.

## Executed checks

PostgreSQL 16 was initialized under `/tmp/easycrm-session5-pg`, bound to loopback port **55435**, with separate disposable `easycrm_session5_test`, `easycrm_session5_browser_test` and `easycrm_session5_restore_test` databases. No application `.env` or real database was changed. Python **3.12.3**, installed Chrome `/opt/google/chrome/chrome`, repository virtualenv/npm dependencies and host Poppler/Nginx were used.

From backend, the full final suite:

```bash
TEST_DATABASE_URL=postgresql+psycopg://deepak@127.0.0.1:55435/easycrm_session5_test .venv/bin/pytest -q
```

**161 passed in 30.76 seconds.** Includes original CRM/auth/RBAC/tenant/channel/qualification tests and new SSRF/DNS/redirect checks, actual Poppler extraction, review isolation, shared concurrent limits, date analytics, export/erase, migration preservation, deactivation serialization and 11 fixture evaluation cases. One pre-existing Starlette/httpx TestClient deprecation warning remains. No assertion failure remains in this final full run.

From frontend:

```bash
DATABASE_URL=postgresql+psycopg://deepak@127.0.0.1:55435/easycrm_session5_browser_test \
PLAYWRIGHT_QUALIFICATION_FIXTURE=1 \
PLAYWRIGHT_FRONTEND_PORT=15175 PLAYWRIGHT_BACKEND_PORT=18005 \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/opt/google/chrome/chrome npm run test:e2e
```

**11 passed in 50.2 seconds.** Real local API/SQL for registration, CRM/notes/stage persistence, settings, simulator, signed website queue/worker/Inbox and PDF review/search/removal/analytics/mobile. Qualification generation is an explicit fixture; external calls in model-management UI tests use their existing fixtures. Provider missing-key scenarios use real error paths. The final affected PDF/knowledge/mobile browser case passed again in 11.7 seconds after the PDF process limits were added. It waits for the mobile sidebar transition before capturing the Session 5 image.

Other passing executed checks:

```bash
# backend
.venv/bin/ruff check app tests alembic ../scripts
.venv/bin/ruff format --check app tests alembic ../scripts
DATABASE_URL=postgresql+psycopg://deepak@127.0.0.1:55435/easycrm_session5_test .venv/bin/alembic check
# frontend
npm run build
npm run format:check
git diff --check
# application root
docker compose config --quiet
docker compose -f compose.production.yaml config --quiet
```

TypeScript/Vite production build passed. Alembic reports “No new upgrade operations detected.” Both Compose files validate. Remote CI was updated but not executed.

### Evaluation and measured performance

```bash
TEST_DATABASE_URL=postgresql+psycopg://deepak@127.0.0.1:55435/easycrm_session5_test make evaluate
TEST_DATABASE_URL=postgresql+psycopg://deepak@127.0.0.1:55435/easycrm_session5_test backend/.venv/bin/python scripts/benchmark.py
```

**11/11 fixture evaluation cases pass:** supported/partial extraction, grounded delivery, unknown warranty, fabricated citation, low confidence, unsupported field evidence, malformed JSON, prompt injection, human request and opt-out. Cases also verify receipt replay without a second inference. [Evaluation evidence](evidence/session-5-evaluation.json) includes each result/duration. This measures deterministic application guardrails with supplied model output, **not live model extraction accuracy**. Live outputs/latency are nondeterministic and remain unmeasured here.

The final [benchmark evidence](evidence/session-5-benchmark.json) records **30 sequential requests per operation**, one workspace/one lead, warm real PostgreSQL, FastAPI TestClient: CRUD-list mean **13.44 ms**, p95 **15.69 ms**, approximately **74.39 serial requests/s**; signed acceptance mean **16.92 ms**, p95 **18.83 ms**, approximately **59.11 serial requests/s**. These exclude network/TLS/proxy/concurrency/AI and external delivery. They are local measurements, not production throughput or an SLA. Machine contention changes results between runs.

### Runtime and backup proof

- `python -m app.seed_portfolio --email session5-demo@example.com` executed on the browser-test DB with a fictional test password; created the furnishing workspace, three leads, source and rubric. Repeating it reported “Account already exists. Nothing was changed.” No model/provider request occurred.
- `python -m app.channel_worker --once` and `python -m app.channel_maintenance` executed successfully on the test DB. Heartbeat/readiness state and receipt timing are tested.
- Host **Nginx syntax and HTTP smoke passed** with the production server block, substituting test loopback upstream/port and built asset directory. A production-mode API started with secure-cookie/HTTPS-origin configuration against the test DB. Root, deep SPA link and proxied readiness returned 200 with security headers; readiness included a correlation ID. [Smoke evidence](evidence/session-5-production-smoke.json). This did not exercise container images or real TLS.
- A temporary **controlled HTTPS fixture** also passed actual socket/TLS/HTTP extraction with hostname certificate verification and a `Connection: close` response. The fixture substituted the public target's transport to a local server and generated an ephemeral certificate/key; it did not contact a public business website or weaken the deployed target validation. PDF extraction now applies POSIX child-process memory/CPU/output/core limits before running Poppler; the oversized-output test exercises the actual child.
- Executed `pg_dump -Fc` from the fictional browser-test DB and `pg_restore --exit-on-error --no-owner --no-privileges` into a **fresh** restore DB using the isolated PostgreSQL socket/port. Restored revision: `c82d4f7e1a50`; snapshot contained **12 workspaces, 8 leads, 4 knowledge sources**. Restored Alembic drift check passed. The backup stays under `/tmp`, outside the repository. Remote storage/encryption/schedules and host recovery are unverified.
- `docker info` returned daemon socket permission denied; `sudo -n docker info` returned **“sudo: a password is required.”** Therefore Docker builds/Compose startup were **not executed**, and no existing containers were replaced. The host smoke is useful separate evidence, not a substitute for the container runtime gate.

## Integration verification matrix

- Auth, CRM, stage changes, SQL/migrations, knowledge review/retrieval, Poppler PDF parsing: **real local API/database/browser execution**.
- Public website fetch: **fixture transport + actual safety/parser/API path**; public live-site/network/TLS fetch not verified in this session.
- AI provider/model settings and deterministic qualification: **real persistence/core, fixture inference success and real missing-key errors**. Gemini/NVIDIA live success/quality/entitlement not verified.
- Website intake: **actual HMAC, replay/durable acceptance, worker, CRM/Inbox/control**, with explicit fictional events. No external recipient is contacted.
- WhatsApp/Meta Lead Ads/Instagram: **fixture adapter/signature/asset/window/idempotency/send/control tests**. Live account/app review, public HTTPS callbacks, receive/send/status and provider permissions remain **unavailable/unverified**. Instagram remains receive-only; no template outreach.
- Production SPA/proxy/API mode: **host HTTP smoke**. Compose syntax valid; images/containers/HTTPS deployment not executed.
- Backup/restore: **real isolated local PostgreSQL drill**, no off-host production recovery claim.

## Remaining limits and release gates

1. Run the production images/Compose with authorized Docker access; configure TLS, edge trust/rate fairness, secret provisioning, image digests/dependency update policy, monitoring/alerts and scheduled encrypted backups with expiry. A stale successful worker heartbeat is not per-message delivery proof.
2. Verify live configured inference with representative multilingual inquiries; the fixture pack does not establish the BRD’s proposed 90% extraction accuracy. Verify official WhatsApp receive/send/status/takeover with authorized test assets before enabling real customers. No live external calls were made in Session 5.
3. Ingestion is synchronous/bounded: no crawling/OCR/embeddings, first 30 PDF pages, 2 MiB, 12,000 text characters, newest 100 approved sources and at most three excerpts. A crash can leave an import processing; delete/reimport. Approved-source publication remains a human trust decision. No comprehensive hostile-PDF or semantic injection guarantee is claimed.
4. Admin erasure/export is an operational tool, not a legal/compliance certification. Minimal actor/subject/receipt identifiers and hashes are pseudonymous metadata, not anonymous data. Unrelated knowledge, prior backups and provider-side records require separate review. No automated active-subject retention policy is enabled. Pending intake blocks deletion; disable integrations and drain/recover it.
5. General contact-management/assignment/invitation UI, password reset/email verification, external alerting, full accessibility/security review and sustained/concurrent production load testing remain product/deployment gaps. Large-history analytics currently reads qualification payloads and is intended for bounded MVP workspaces, not enterprise-scale reporting.
6. Existing license selection is unresolved; no public release was made. Monetary CRM values remain USD; the furniture rubric uses INR with no conversion. Stage snapshots and rubric points are not sales probability/revenue outcomes.

Readiness: suitable for a clearly labeled **local portfolio demo**. External-provider/Meta verification and actual production-host release remain gated as above. Use [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) for a 3–5 minute recording and [PORTFOLIO_SUMMARY.md](PORTFOLIO_SUMMARY.md) for factual resume bullets without invented metrics.
