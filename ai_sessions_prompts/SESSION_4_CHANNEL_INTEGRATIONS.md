# EasyCRM — Codex Session 4
## WhatsApp Cloud API, Universal Webhooks & Meta Lead Capture

### Outcome
Authorized incoming website and WhatsApp events enter a shared lead ingestion pipeline, create/update the correct workspace lead, invoke the Session 3 qualification engine when appropriate, and record message history. A human can take over without the AI continuing to reply. Meta leads and Instagram are introduced within permission/test-mode limits.

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

## Implementation priority (do not invert)
**P0:** Universal website lead webhook and official WhatsApp Cloud API end-to-end. **P1:** Facebook Lead Ads retrieval and Instagram inbound messaging if the necessary app permissions and test setup exist. Do not risk the P0 deliverable to chase permissions unavailable to this repository.

### A. Unified inbound event pipeline
- Normalize events into one internal envelope (`workspace_id`, `source`, `external_event_id`, `external_contact_id`, `contact`, `text`, `payload_ref`, `received_at`). Keep raw payloads only as necessary, with safe retention and PII controls.
- Resolve integration credentials to workspace **server-side**; never accept arbitrary workspace_id from a public payload as authority.
- Create/update contacts and leads with deduplication rules; preserve channel source and consent/contact preferences. Queue qualification processing, track status, failures and retry attempts.
- Guarantee event deduplication/idempotency (database uniqueness) and concurrency-safe processing.

### B. Universal website webhooks
- Create one generated webhook endpoint/key per workspace or integration, with key rotation and revocation.
- Verify signed requests (HMAC or equivalent), enforce replay protection, timestamps, size limits and rate limits. Specify event schema, example cURL, HTML form integration sample and delivery log page.
- Do **not** expose the webhook signing secret in client-side JavaScript; sample public forms submit to a trusted website backend or use a separate appropriately secured public form endpoint.
- Map arbitrary website form fields to a canonical lead schema; allow test event and display accepted/rejected results.

### C. Official WhatsApp Cloud API
- Configure Meta app credentials, phone-number ID, webhook verify token, app secret and access token via backend environment or encrypted server-side storage; don't leak them to the frontend.
- Implement Meta webhook challenge verification, signature validation, message/status parsing and immediate webhook acknowledgment followed by queued processing.
- Send messages through the official API only; implement retries with appropriate backoff, deduplication of outbound requests and message status tracking.
- Enforce WhatsApp's current customer-service window and approved-template requirements for outside-window outreach, as verified against current official Meta docs. Never send an unsolicited or unapproved template.
- AI reply is controlled by a persisted `ai_enabled`/human-takeover state, explicit qualification policy, and approved contact permissions. Human reply cancels queued AI responses where possible; re-check mode immediately before sending.
- Support text messages first. Other media is out of MVP scope.

### D. Facebook Lead Ads / Instagram (conditional P1)
- For Facebook lead forms, validate webhook event, fetch form details by lead ID through Graph API with correct permissions, normalize into lead records and attribute campaign/source where provided.
- For Instagram inbound messaging, integrate only an approved and documented API path. If app review or access prevents live tests, provide authentic API adapters with fixture-based contract tests and clearly mark as not live-verified. Never scrape private messages.

### E. UI
- Integrations page: connection/config status, safe setup steps, webhook URLs, secrets rotation (display newly generated secret once), test connectivity, delivery logs and errors.
- Unified Inbox: conversation list, message history, lead detail context, AI/Human mode switch, send manual message, delivery status and channel badges. Gracefully handle unavailable channels.

## Acceptance gates
- Valid signed website webhook creates exactly one lead; invalid signature/replay and duplicates are safely rejected/ignored.
- Incoming WhatsApp message from a configured test number appears in Inbox, triggers the existing qualification engine, saves its response, and sends only if permitted.
- Human takeover during queued AI work prevents the AI response from being sent.
- Failed Meta/WhatsApp API calls retry safely without duplicate records or duplicate sends.
- External tokens are hidden; credentials and event payloads can't cross workspaces.
- Demonstrate Facebook Lead Ads and Instagram only to the level credentials permit; distinguish live pass, sandbox/fixture pass, and blocked.

## Explicitly defer
Cold prospect scraping, voice bots, mass broadcasts, campaign automation, omnichannel marketing attribution platform, billing.

## End-of-session handoff
Write `docs/SESSION_4_HANDOFF.md`: exact Meta app setup/permissions, env vars, webhook URLs and callback steps, template/window rules, test numbers, live vs mocked verification, failure/retry semantics and Session 5 hardening gaps.
