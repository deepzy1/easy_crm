# EasyCRM — Business Requirements Document (BRD)

**Version:** 0.1 · **Status:** Draft · **Product:** EasyCRM · **Audience:** Product owner, developers, reviewers

## 1. Problem and opportunity

Businesses receive inquiries from website forms and messaging channels but lose time triaging repetitive questions, discovering budget/timing/fit, and transferring context to salespeople. Generic chatbots answer FAQs; conventional CRMs store leads. EasyCRM joins **company-specific answers**, **conversational qualification**, and **CRM handoff** in one workflow.

This is primarily a **portfolio/learning build** with potential to evolve into SaaS. Success is reliable, demonstrable workflows — **not** claims of actual sales uplift without pilot evidence.

## 2. Objectives and measurable success criteria

| ID | Business objective | MVP measurable proof |
| --- | --- | --- |
| BO-01 | Reduce manual lead triage | Demo from inbound webhook to structured lead without manual reentry |
| BO-02 | Give accurate business-aware answers | Evaluation set measures grounded/unsupported responses; unsafe unknowns are escalated |
| BO-03 | Identify sales-ready prospects | Configurable rubric records score, matched criteria, missing requirements, and explanation |
| BO-04 | Preserve human salesperson control | Human takeover immediately prevents subsequent automated outbound replies |
| BO-05 | Integrate common inbound sources | Custom webhook in M1; WhatsApp test integration in M3 |
| BO-06 | Prove backend skills | Versioned API, migrations, unit/integration tests, job retries, telemetry, docs |

**Initial quality targets (proposed, validate through testing):** 100% pass on tenant-isolation and webhook-auth test cases; 100% duplicate-retry prevention in replay tests; at least 90% accuracy on a small labeled structured-field extraction evaluation set. Do not advertise these as achieved until measured.

## 3. Personas

- **Workspace admin:** configures company identity, service regions, knowledge documents, lead criteria, connectors, and staff access.
- **Salesperson:** reviews leads, takes over conversations, records notes, changes stages, and follows up.
- **Prospect/customer:** submits a form or messages the company's WhatsApp number; may receive AI assistance with clear identification as an automated assistant.
- **Developer/reviewer:** configures test inputs, views sanitized execution logs, runs evaluation tests, and reproduces the end-to-end workflow.

## 4. Scope

### In scope (MVP)

- Workspace account and membership (admin, salesperson); independent business configuration.
- Business profile, policy and service/product content via controlled website URLs and PDF upload.
- Configurable qualification schema/rubric (industry-specific questions, required fields, scores and thresholds).
- Signed generic inbound lead webhook, normalization, per-workspace deduplication, lead creation and source attribution.
- CRM lists, Kanban pipeline, contact/lead detail, timeline, notes, assignment, stage edits.
- AI qualification simulator plus knowledge-grounded answers, structured extraction, and deterministic scoring.
- WhatsApp Cloud API inbound/outbound messaging, user consent/opt-out metadata, human takeover, audit trail.
- Operational analytics: incoming leads by source, qualifying/qualified counts, response and handoff measures.

### Out of scope (initial)

- Searching/scraping arbitrary social profiles, bulk unsolicited outreach, marketing campaign generation.
- Instagram DMs, Facebook Lead Ads ingestion, paid advertisements, enterprise CRM marketplace.
- Autonomous pricing commitments, unsupervised calendar bookings, AI voice calling.
- Subscriptions/paid billing, full ERP/marketing automation, mobile native apps.

## 5. Key user journeys and rules

1. **Workspace onboarding:** admin creates workspace and profile; configures service areas/products, uploads source documents, reviews parsed output, and publishes a qualification rubric.
2. **Capture:** a configured site posts lead data to a signed webhook; source is identified securely; valid data creates or merges contact/lead within that workspace.
3. **Qualify:** AI uses only that workspace's approved knowledge sources; asks prioritized missing questions; extraction outputs structured fields + evidence; deterministic rules calculate score/status.
4. **Handoff:** lead reaches qualified threshold or triggers an escalation (e.g., explicit human request, pricing uncertainty); sales owner notified in UI; status and reason visible.
5. **Conversation ownership:** salesperson toggles a conversation to human. Automated responses cease until explicit re-enable and business policy permits it.

### Core business constraints

- A lead can be **new, qualifying, qualified, needs-human, disqualified, or closed**, separately from editable sales pipeline stages.
- A lead score is a **rubric score** (0–100), not a promise of purchase probability.
- Do not invent quotes, guarantees, discounts, service availability, or policy exceptions.
- Every message/action is associated with a workspace and source; record provenance and timestamps.
- External outreach must comply with provider rules, consent, opt-out and applicable jurisdiction requirements.
- Do not let the system auto-contact a form submitter unless appropriate permission and channel rules are satisfied.

## 6. High-level feature priorities

| Priority | Requirements |
| --- | --- |
| P0 | Workspaces; leads/contacts/CRM; inbound signed webhooks; document knowledge; configurable AI qualification; human takeover; WhatsApp demo path; robust security/tests |
| P1 | Analytics dashboard; reusable industry templates; richer source attribution; evaluation suite; optional salesperson notifications |
| P2 | Meta lead forms, Instagram messaging, third-party CRM export, appointment sync, advanced campaigns |

## 7. Dependencies, assumptions, and risks

- Meta WhatsApp Cloud API requires supported app/account configuration, webhook verification, tokens and compliance; a test number may be used for development. External approval may affect demo availability.
- AI model inference costs and rate limits vary; never assume unlimited free usage.
- Company sites can contain stale, conflicting or adversarial content. Require review, source metadata, prompt-injection defenses and clear uncertainty handling.
- Customer records contain personal data: minimization, retention, deletion, encryption in transit and access controls are required.
- Social-network data and marketing permissions are jurisdiction-specific; limit MVP to authorized sources.

## 8. Acceptance milestones

- **M1:** A signed custom lead event appears exactly once in the right workspace's pipeline and is visible to the correct staff.
- **M2:** Two mock businesses have isolated knowledge and distinct rubrics; AI simulator produces evidence-linked extraction and repeatable scores.
- **M3:** Test WhatsApp inbound message is recorded, valid AI reply is sent when permitted, and salesperson takeover stops AI replies.
- **M4:** Documented Docker demo, CI tests, security/tenant checks, observable failures, and demonstration video/script.

## 9. Open business decisions

- Default qualified threshold and industry templates; human review rules.
- Workspace retention period and prospect erasure workflow by jurisdiction.
- Whether web-form inquiries are handled only as CRM records or include consented follow-ups.
- Which employee assignment strategy to use (manual in MVP, rules later).
