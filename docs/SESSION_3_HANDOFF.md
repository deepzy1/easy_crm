# Session 3 — business-aware lead qualification

Implemented and verified locally on **27 October 2026**. Session 1's application, authentication, workspace isolation, provider adapters, model settings and original text playground are preserved. Changes are uncommitted.

## Delivered scope and the Session 2 gap

This checkout contained Session 1 plus the Session 2 prompt, but no Session 2 implementation or handoff. Session 3 therefore adds a small **reviewed-text source store**, rather than claiming website/PDF ingestion or vector RAG exists. Admins explicitly approve business text; lexical retrieval filters workspace and approval before loading text. No network requests, uploads, PDF parsers, embeddings, Redis, workers or new dependencies were added.

Delivered: editable qualification templates; immutable rule versions and explicit activation; opt-in generic B2B/furniture examples; controlled model extraction; supported-field persistence; deterministic assessments; citations; audit events; state/control actions; simulator; Lead Detail evidence/timeline/override; score badges in CRM list/Kanban; immediate dashboard status updates when refetched. No channel messages are dispatched.

The original Knowledge Base/Inbox/Integrations destinations remain future pages. The reviewed-text editor lives under **AI Qualification → Business sources**.

## Startup, migration and configuration

From the application root, `/home/deepak/Music/easy_crm/easy_crm`:

```bash
make migrate
make backend
# In another terminal:
make frontend
```

Migration **`57002a21df59`**, after `be78ada7931e`, adds `qualification_templates`, `qualification_knowledge`, `qualification_conversations`, `qualification_events`, and nullable `leads.qualification_score`. Existing records receive no invented scores. Composite foreign keys bind conversations to same-workspace leads/templates and events to same-workspace conversations. Lead deletion cascades through its qualification history. Template history is retained.

No new environment variables or packages. Use the existing root `.env` and saved **Settings → AI models** preference. `GEMINI_API_KEY` / `NVIDIA_API_KEY` remain exclusively server-side. The application database was **not migrated during this development run**; verification used new disposable databases. Run `make migrate` on your selected local database before using the updated app.

## Rules and version semantics

Admins load an example, edit and save it; no examples or sample leads are installed automatically. Every save creates a new immutable workspace version, optionally active. Prior versions can be reactivated. A workspace lock serializes version allocation/activation; normal API operations maintain a single active version. Existing conversations remain pinned to the exact template ID/version used at creation, even after another version is activated.

Each of 1–15 ordered criteria has a unique field key, question, text/number type, required flag, nonnegative integer weight, matching rule, optional disqualifier and optional human-review-on-match rule. Questions are asked in configured order, skipping collected required facts. The UI can reorder, add and remove fields. Supported rules:

- `present`: points for a supported value.
- `one_of`: case-insensitive exact match against configured text choices.
- `minimum`: numeric value at or above the configured nonnegative minimum.

Weights must total **exactly 100**; there is no changing denominator when facts are missing. `0 <= review_threshold < qualified_threshold <= 100`. Confidence threshold is 0.5–1, default 0.8. Optional fields can contribute points but do not block completeness. Rule priority is deterministic:

1. A known mismatched disqualifier → `disqualified`.
2. A matched human-handoff criterion → `needs_human`.
3. All required fields known and score at/above qualified threshold → `qualified`.
4. All required fields known and score in the review band → `needs_human`.
5. All required fields known and score below review threshold → `disqualified`.
6. Otherwise → `qualifying`, with the next missing required question.

Opt-out, human requests, uncertainty and conversation controls take priority over the computed decision. The score always remains the calculated points, including when a human overrides the decision. Qualified leads pause AI by default; admins may disable that rule. A score is **rubric points, not purchase probability**.

The generic B2B example asks for product, USD budget (minimum 1,000), timeline and buyer role, worth 25 points each. The furniture example asks for product (20), Bengaluru/Bangalore location (25, outside-area disqualifier), INR budget (30, minimum 50,000) and timeline (25). Currency is explicit in each question; no conversion occurs. CRM opportunity monetary values still use USD.

## Conversation state and CRM relationship

Core state names are `new`, `qualifying`, `qualified`, `needs_human`, `disqualified`, `closed`. Existing CRM status spelling `needs-human` is preserved at the boundary. Repeating the same state is permitted; other transitions are:

- `new` → qualifying, qualified, needs_human, disqualified, closed.
- `qualifying` → qualified, needs_human, disqualified, closed.
- `qualified` → qualifying, needs_human, disqualified, closed.
- `needs_human` → qualifying, qualified, disqualified, closed.
- `disqualified` → closed only.
- `closed` → no other state.

Human takeover records an actor/reason and moves to `needs_human`/human mode. Resume requires an explicit reason and a nonterminal, non-opted-out conversation; it moves to `qualifying`/AI mode. A human override records its reason, prior/next state, actual score and assessment snapshot, and keeps human control. Closing is terminal. Opt-out also sets a sticky flag that cannot be cleared or overridden through these APIs.

New messages in human/terminal mode are recorded without inference or an AI reply. Explicit unsubscribe/opt-out requests close the thread without inference. Human requests and detected unsafe instructions route to human review without inference. Existing CRM records already marked qualified/needs-human/closed/disqualified start under human control.

Qualification changes update `Lead.status`, `qualification_score`, deterministic `summary` and `updated_at`. They **never move pipeline stages**, change opportunity value, assign an owner or notify a salesperson externally. Ordinary lead PATCH cannot forge points or bypass a running conversation's decision; use the audited qualification override. Leads without qualification conversations retain Session 1 manual status editing.

There is one canonical qualification thread per lead. A second channel cannot create an independent thread for that lead; it receives 409 pending an explicit Session 4 channel/thread mapping design.

## Extraction, grounding and failures

Every AI turn reads the current saved workspace provider/model and calls the existing adapter exactly once. Catalogue discovery is not a prerequisite for generation with an already saved preference. No workflow model is hardcoded. Provider/model/latency/token metadata is saved with the event. Prompts include business name/industry, pinned rules, collected values, the last 20 message/reply turns, current inbound text and up to three relevant reviewed-source excerpts.

The model returns schema-validated JSON candidate fields, exact source quotes and an uncertainty flag. It cannot set scores, states, database actions or arbitrary reply text. Unknown keys, duplicate candidate keys, invalid JSON/extra fields, unsupported values/evidence, low confidence and contradictions trigger review. Missing facts remain missing. Text values must occur in an evidence substring of the current message; numeric values must occur as a matching numeric literal, with no currency conversion or inferred city. Repeated identical values are ignored. Changing a prior value requires both a correction flag and an explicit correction phrase; old/new evidence is preserved in the event's change list.

Business answers contain only exact quoted substrings of approved, retrieved workspace sources, followed by one backend-selected missing question. The model's free-form reply is never used. Unknown policy questions, requested uncertainty or invalid/unsafe source references route to human review. Citations retain source ID, title and quote in historical events even after source removal. Source removal excludes future retrieval.

This is conservative evidence validation, **not a complete semantic proof or a universal prompt-injection defense**. Confidence is model-reported, not calibrated. Multilingual opt-out/requests, paraphrase/negation interpretation, numeric shorthand such as `50k`, currency ambiguity, retrieval quality and broader adversarial cases require further evaluation before channel deployment. Reviewed-source publication is a trust decision; no automated freshness/conflicting-policy resolver exists.

Missing model/key and sanitized provider failures return actionable errors with no fabricated success and no automatic retry or fallback. The request transaction rolls back, leaving no receipt/field/status mutation from that failed turn. Invalid structured model output instead persists an explicit `needs_human` assessment. The UI retains message text and its receipt ID for a manual retry; editing text creates a new receipt ID.

## Internal message contract and Session 4 integration

Entry point in `backend/app/services/qualification.py`:

```python
plan = await process_incoming_message(
    db, workspace_id, lead_id, channel,
    external_message_id, text, timestamp, actor_id=None,
)
db.commit()
```

`db` is the caller-owned SQLAlchemy session. IDs must reference the same workspace. The caller must authenticate/authorize a workspace or verify a channel's signed integration mapping **before** calling the core. Text is 1–4,000 characters; timestamp must be timezone-aware; channel is a lowercase identifier up to 30 characters. The returned Pydantic `ActionPlan` contains conversation/lead IDs, state, mode, optional reply, assessment, supported fields, citations, model metadata, duplicate flag and **`dispatch: "none"`**.

The receipt uniqueness key is `(workspace_id, channel, external_message_id)`. A SHA-256 digest binds it to lead ID and stripped text. Same receipt/content replays the saved plan with `duplicate=true` and no inference/write. Same ID with another lead/text returns 409. The first received timestamp is retained as metadata; timestamp changes alone do not conflict. Different external IDs represent different turns even if their text is identical.

A nonblocking `SELECT ... FOR UPDATE` on the scoped lead serializes generation, corrections and control changes. In-flight contention returns 409 and does not call a provider; retry manually with the same receipt. The unique receipt constraint also handles cross-lead races. A transaction holds its lead lock through inference. This is a simple synchronous request architecture, not durable asynchronous webhook intake. History is capped at 200 existing events when processing messages; the last 20 message turns are sent to the model. Approved-text retrieval considers the newest 100 workspace sources and at most three 1,500-character excerpts.

Session 4 must add verified signed intake and a durable inbox **before acknowledgment**, preserve stable external IDs, define channel-to-canonical-thread mapping, manage failed jobs explicitly, enforce consent/opt-out and messaging-window/template policies, and recheck current AI/human state immediately before any dispatch. A replayed plan can describe a past AI state; **never dispatch its old reply just because it was replayed**. Add a durable outbox/delivery reconciliation rather than claiming exactly-once external sends. Provider failures can consume upstream quota even if the local transaction rolls back; do not silently retry paid inference.

## Implemented HTTP contracts

All paths below are relative to `/api/v1/workspaces/{ws}` and require authenticated workspace membership. Admin is additionally required for template/source mutations; members can simulate and use human controls.

- `GET /qualification/templates` → `{items, examples, can_manage}`.
- `POST /qualification/templates` → immutable version; body includes name, criteria, qualified/review/confidence thresholds, `handoff_when_qualified`, `activate`.
- `POST /qualification/templates/{id}/activate` → activate an existing workspace version for new conversations.
- `GET/POST /qualification/knowledge` → list/add bounded text sources; create body `{title, text, approved}`. Approval is explicit, false by default.
- `DELETE /qualification/knowledge/{id}` → remove source from future retrieval; historical quotations are retained.
- `POST /qualification/simulate` → one simulator turn; body `{lead_id, external_message_id, text, timestamp}`. It returns the validated action plan and sends nothing externally.
- `GET /leads/{id}/qualification` → `{conversation, events}` or `{conversation: null, events: []}`.
- `POST /leads/{id}/qualification/control` → `{action, reason, state?}`; actions `takeover`, `resume`, `close`, `override`. Only override accepts/requires `state`.

The CRM LeadOut contract adds nullable, read-only `qualification_score`. LeadUpdate tolerates a round-tripped unchanged score; a forged non-null score is rejected. Generated `/docs` is the current schema reference. The stateless conversation-array simulator in the original draft API is not implemented.

## Verification and evaluation

Tests use disposable PostgreSQL 16 clusters/databases created under `/tmp`; no real application records or provider credentials were used. Browser success uses real auth/API/SQL/retrieval/scoring with an explicitly selected, fictional provider fixture. The fixture launcher is under **tests**, is not imported by production, and only substitutes qualification inference. Ordinary model test/playground calls still show real missing-key errors.

Verified behaviors include two isolated templates giving different scores for the same input, missing budget, ambiguous location, low confidence, unsupported numeric evidence, corrections and contradictory values, duplicate receipts, unsafe instructions, explicit human request, opt-out, takeover/resume, terminal transitions, exact/missing/forged citations, version pinning, missing credentials, provider failures without retries, Gemini/NVIDIA routing and model changes, tenant/role authorization, compound-FK isolation, concurrent lead locking, human overrides and CRM/dashboard reconciliation.

The cross-template fixture yields **100/qualified** for generic B2B and **70/needs_human** for furniture because its 5,000 budget meets the B2B minimum and misses the furniture minimum. The furniture location disqualifier is separately tested with Mumbai. These are synthetic deterministic evaluation examples, not measured live-model extraction accuracy.

Validation results are recorded in [evidence/session-3-verification.json](evidence/session-3-verification.json). Screenshots show fictional data: [desktop simulator](evidence/session-3-desktop.png), [mobile opt-out](evidence/session-3-mobile.png). No manual live-provider conversations are claimed.

To repeat checks with your own explicitly disposable database ending in `_test`:

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/easycrm_test'
.venv/bin/pytest -q
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic check
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
cd ../frontend
npm run build
npm run format:check
# Point DATABASE_URL at a separate migrated disposable browser database.
# This explicit switch uses only fictional qualification inference fixtures:
PLAYWRIGHT_QUALIFICATION_FIXTURE=1 npm run test:e2e
```

Without `PLAYWRIGHT_QUALIFICATION_FIXTURE=1`, the full successful-chat browser case is explicitly skipped; the opt-out and missing-key browser cases still exercise real services. CI now enables the fixture for complete local-provider-free coverage; remote CI has not been executed. Use `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/opt/google/chrome/chrome` if using an installed Chrome. Port overrides are supported by the existing Playwright configuration.

## Files changed and next-session readiness

Backend: new qualification schemas, service and API; additive entity/migration changes; CRM update guards/score response; router registration. Frontend: `Qualification.tsx`, Lead Detail panel, CRM scores, App navigation/help, API types and responsive styles. Tests: qualification integration/migration cases, isolated browser provider launcher, two simulator browser cases and existing playground fixture adjustments. CI enables the test-only provider launcher. README, API/architecture notes and this handoff document the actual contract.

Session 4 can call the implemented core but **live channels are not ready to enable** until signed/durable intake, channel mapping, dispatch policy and outbox checks are implemented. Website/PDF ingestion still requires Session 2 work. Live Gemini/NVIDIA model quality, account access, production deployment, shared rate limits, backups/retention, formal accessibility/security review and load testing remain unverified. The existing upstream Starlette/httpx deprecation warning does not affect current assertions. No commits or pushes were made.
