# EasyCRM — Software Requirements Specification (SRS)

**Version:** 0.1 · **Status:** Draft. Requirement IDs are stable for test traceability.

## 1. Roles and entities

**Roles:** admin and salesperson. Only admins can manage integrations, knowledge, scoring rules and membership. Salespeople manage assigned/accessible leads and conversations according to workspace policy.

**Entities:** Workspace, User, Membership, BusinessProfile, KnowledgeSource, DocumentChunk, QualificationTemplate, QualificationCriterion, Contact, Lead, LeadEvent, Conversation, Message, Assignment, Note, IntegrationSource, WebhookDelivery, AIExecution, AuditEvent.

## 2. Functional requirements

| ID | Requirement | Priority | Acceptance test |
| --- | --- | --- | --- |
| FR-001 | Register/login and manage workspace membership with roles | P0 | Unauthorized access to another workspace returns 403 or 404 without data |
| FR-002 | Admin edits business name, industry, URL, address/service regions, products, policies, working hours | P0 | Valid updates persist; invalid fields rejected |
| FR-003 | Admin adds bounded website URLs and PDFs; ingestion tracks pending/processing/ready/failed and sources | P0 | Parsing completes or shows actionable failure |
| FR-004 | Knowledge retrieval strictly scopes chunks by workspace and active source | P0 | Cross-workspace test cannot retrieve other tenant's text |
| FR-005 | Admin configures required qualification fields, questions, weights, thresholds | P0 | A business A rubric differs from business B |
| FR-006 | Generic lead webhook supports per-source secret verification, replay/idempotency and normalized payloads | P0 | Duplicate event creates one logical lead event |
| FR-007 | Normalize phone/email; search duplicates only within same workspace; preserve source event history | P0 | Same phone in two workspaces remains separate |
| FR-008 | Contact/lead create/read/update, Kanban stage movement, notes, assignments | P0 | Staff can view lead and authorized edits persist |
| FR-009 | Conversation timeline stores inbound/outbound status and source | P0 | Messages sorted by timestamp; retries don't duplicate |
| FR-010 | AI identifies missing fields and extracts structured qualification values with confidence/evidence | P0 | Invalid JSON is rejected/retried safely; unknowns remain null |
| FR-011 | Answers to business questions are grounded in current retrieved knowledge; unsupported claims escalate | P0 | Unknown-policy test never fabricates a warranty/price |
| FR-012 | Deterministic score computes from configured criteria and records reasons, template version | P0 | Same structured fields and rubric produce same score |
| FR-013 | Qualification status and pipeline stage are stored separately; threshold or human trigger creates handoff | P0 | Qualified lead appears in review queue and audit event |
| FR-014 | Human takeover disables automatic replies for that conversation | P0 | New inbound in human mode does not trigger outbound AI send |
| FR-015 | WhatsApp Cloud API webhook verifies Meta signature/challenge; manages inbound/replies/delivery status | P0 (M3) | Valid test webhook processes; invalid signature rejected |
| FR-016 | WhatsApp send gate checks messaging window/template and opt-out status | P0 (M3) | Send outside allowed window blocked unless permitted template |
| FR-017 | Basic metrics by source and qualification status for a date range | P1 | Metrics reconcile against workspace-scoped lead records |
| FR-018 | AI Playground supports synthetic conversations without contacting real recipients | P0 (M2) | Test conversation saves simulator trace, sends no external message |
| FR-019 | Admin may deactivate integration and rotate webhook signing key | P0 | Old key stops working according to documented rotation policy |
| FR-020 | Workspace can export/delete subject-associated personal records and apply retention policy | P1 | Erasure/export request is audited and scoped |

## 3. Non-functional requirements

| ID | Category | Proposed measurable target / control |
| --- | --- | --- |
| NFR-001 | Isolation | Workspace ID enforced in queries, vector retrieval, queues and object storage; automated negative tests |
| NFR-002 | Authentication | Secure password hashing or OIDC; short-lived access tokens; no plaintext credentials |
| NFR-003 | Webhook integrity | Constant-time HMAC/signature verification on raw body; replay/idempotency keys; rate limiting |
| NFR-004 | Reliability | Webhooks acknowledge after durable event acceptance, async processing retries with backoff and DLQ/failed state |
| NFR-005 | Performance | Local benchmark targets: p95 CRUD reads <300ms, webhook acceptance <500ms (excluding AI), under defined fixture/load; AI latency measured separately |
| NFR-006 | Observability | Correlation ID, request/worker structured logs, error metrics and auditable AI action outcomes; redact PII/secrets |
| NFR-007 | AI correctness | JSON-schema outputs, retrieval grounding checks, refusal/escalation on unsupported claims, prompt injection hardening |
| NFR-008 | Accessibility | Keyboard-operable controls, visible focus, suitable contrast, WCAG 2.2 AA as a design goal |
| NFR-009 | Maintainability | Typed API schemas, migrations, services separated from transport, CI unit/integration tests |
| NFR-010 | Data protection | TLS in production, encryption at rest via provider, secrets manager/env, documented retention and deletion path |
| NFR-011 | Responsiveness | Desktop-first CRM and usable tablet/mobile views; no horizontal overflow on core screens unless Kanban explicitly scrolls |
| NFR-012 | AI costs | Token budgets, concurrency limits, timeout/fallback responses and logging of usage by workspace |

**These are implementation targets, not service guarantees.** Benchmark in an explicitly documented environment.

## 4. UI/UX requirements

- Pure white background, blue primary (`#2563EB`), near-black text, neutral borders. Attio-inspired layout without copying proprietary visuals.
- Sidebar: Overview, Leads, Pipeline, Inbox, AI Qualification, Knowledge Base, Integrations, Analytics, Settings.
- Lead details: source, identity, message timeline, extracted qualification fields, score/explanation, missing data, notes, owner, AI/human state.
- AI decisions always explain **why** a lead is qualified. Include source document references for answers where applicable.
- Clear loading/error/empty states and confirmation for destructive actions.

## 5. Example qualification algorithm

1. Retrieve published rubric by workspace and version.
2. AI extracts structured fields (`product_interest`, `location`, `budget`, `timeline`, `intent`, etc.) from messages, with evidence references. Missing fields remain null.
3. Rule engine checks each criterion; assign configured weight only when verified and matched; sum weights to a 0–100 score (rubric weights must total 100).
4. Apply blockers/escalations (outside region, explicit human request, prohibited unsupported policy answer, opt-out).
5. Record score, reasons, missing fields, rubric version and decision timestamps; never label score as conversion probability.
6. Ask the next highest-priority unanswered question or route to a salesperson.

## 6. Test scenarios

- **T-01:** Same email/phone in two different workspaces -> separate contacts.
- **T-02:** Same webhook event delivered three times -> one persisted event, no duplicate lead.
- **T-03:** Invalid HMAC and stale/deactivated source -> no ingestion.
- **T-04:** Business A's uploaded PDF must never appear in business B's AI retrieval.
- **T-05:** Unknown price question -> explicit uncertainty/handoff, not invented figure.
- **T-06:** AI takeover disabled -> no outbound AI replies after incoming WhatsApp message.
- **T-07:** Rule score re-runs identically against same extracted fields/template version.
- **T-08:** Expired messaging session with no approved template -> outbound blocked.
- **T-09:** Prompt injection inside scraped page -> no credential disclosure or role override.
- **T-10:** Worker crash after durable ingest -> retry safe, no duplicate external send.

## 7. Definition of done per milestone

Code, migrations, validation, role checks, tests, OpenAPI updates, demo fixture, run instructions, error states, and short demonstration evidence are mandatory. Features are not complete merely because the UI renders.
