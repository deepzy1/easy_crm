# EasyCRM — Codex Session 3
## Business-Aware AI Lead Qualification Engine

### Outcome
A business can configure qualification criteria, simulate an AI conversation with a prospective customer, and produce a **traceable, structured qualification** stored on the CRM lead: extracted requirements, missing information, rules-based score, decision, citations, summary and recommended next action.

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
### A. Configurable qualification profiles
- Per-workspace qualification templates with configurable questions/fields (e.g. product, location, budget, timeline, buyer role, contact preference), required/optional flags, score weights, thresholds, disqualifiers and human-handoff rules.
- Provide a sensible furniture/furnishing example as *opt-in seed data*, plus a neutral generic B2B template. Let admins edit and activate a template without source-code changes.
- Validate scoring configurations (no negative weights, predictable normalization, unambiguous thresholds). Version/persist rules so past evaluations remain explainable.

### B. Controlled AI conversation
- Use Session 2 workspace-isolated knowledge retrieval for product/policy questions; answer with grounded information and avoid inventing prices or promises.
- Use the active workspace AI model in Settings (Gemini or NVIDIA) through the existing adapter abstraction. Prompt it to ask one relevant question at a time, skip facts already collected and respect the conversation transcript.
- Extract structured candidate fields (field, value, evidence/message, confidence/unknown), validate via schemas, and store only supported values. Do not let LLM output execute arbitrary database actions.
- Maintain explicit conversation states: `new`, `qualifying`, `qualified`, `needs_human`, `disqualified`, `closed`; clearly define allowed transitions and the relationship to CRM pipeline stages.
- Support user opt-out, uncertainty escalation, AI pause/human takeover and resumption. Do not automatically contact leads or send external messages in this session.

### C. Deterministic assessment
- Run qualification scoring in normal backend code from persisted business rules, *not* a free-form LLM probability.
- Persist scores, matched criteria, missing fields, exclusion reasons, rule version, timestamps, evidence and decision explanation.
- Record lead summary and recommended next action; route `needs_human` for policy-sensitive or low-confidence cases.
- Avoid duplicate or contradictory field updates; provide structured audit events/history.

### D. UI
- Implement a polished `AI Qualification` page with rule-builder/editor, selected model display, sample lead selection and **interactive simulator** that uses real services without sending WhatsApp messages.
- Show chat transcript, extracted fields, source citations, live assessment/explanations, score breakdown, AI vs Human control, and link to the persisted CRM lead.
- Update Lead Detail view with qualifications, timeline, evidence and human override. Keep Kanban/list accurate after qualifying.

### E. Service contracts
Define internal entry point like `process_incoming_message(workspace_id, lead_id, channel, external_message_id, text, timestamp)` returning a validated response/action plan; Session 4 will call it from channel adapters. Ensure idempotency strategy and no external dispatch inside the core engine.

## Tests / acceptance gates
- Same message under two different business templates yields different, explainable qualification outcomes without cross-tenant leakage.
- Test missing budget, ambiguous location, correction of previously stated value, repeated message, malicious prompt injection, contradictory facts, opt-out and forced human handoff.
- A full simulator chat persists conversation + lead fields, shows source references, and consistently computes deterministic scores.
- Changing selected AI model in Settings routes subsequent inference through the new model and surfaces failure truthfully.
- Unauthorized users cannot change criteria or read other tenants' messages/scores.
- Mock provider calls for automated tests; document evaluation examples and manually verified flows.

## Explicitly defer
Live WhatsApp sending/receiving, Facebook/Instagram connectors, external prospect discovery, voice, mass outreach, billing. **Do not attempt all integrations in Session 3.**

## End-of-session handoff
Write `docs/SESSION_3_HANDOFF.md` with qualification state machine, scoring rules, internal message contract, model-routing behavior, simulator usage, test evidence, and instructions to connect channel adapters in Session 4.
