# A 3–5 minute EasyCRM interview demo

Say which mode you are showing before starting: **local real API/database**, **fixture inference**, or **live external inference**. Fictional data and a signed test event are never a real WhatsApp conversation.

## Prepare

Run migrations, API, frontend and worker as documented in README. Set a stable signing master key. Run `make seed-portfolio` and choose a disposable demo password. This explicitly creates Willow & Loom, three fictional manual leads, an approved policy and the active furniture rubric. Repeating the command leaves an existing account untouched. New registrations remain empty.

For a credential-free, reproducible full simulator demonstration, use a separate disposable database, migrate it, and run:

```bash
cd frontend
PLAYWRIGHT_QUALIFICATION_FIXTURE=1 npm run test:e2e -- e2e/qualification.spec.ts e2e/channels.spec.ts e2e/release.spec.ts
```

The fixture launcher is under backend/tests, never imported by the production app. It replaces qualification generation only. Auth, PostgreSQL, approved-source retrieval, citation checking, score computation, CRM persistence and signed website intake are real. Other AI calls still report missing credentials. For browser QA, use an isolated `_test` database and empty provider keys. The generated screenshots come from the running app; browser traces are available under frontend/test-results after failures.

For a live inference demonstration, configure your own server-side Gemini/NVIDIA key. In Settings refresh models, select/save a supported model and test it explicitly. Listing does not prove inference access, pricing or free entitlement. A failed test should be shown honestly; do not substitute a fixture while calling it live. Provider/model selection remains workspace configuration, never hardcoded in the furnishing workflow.

## Recording script

1. **0:00–0:40 — Business and CRM.** Sign in to the fictional furnishing workspace. Show the business profile, three new leads and independent pipeline stages. Explain that source labels describe provenance, not proof of a connected channel. New workspaces start empty.
2. **0:40–1:25 — Trusted knowledge.** Open Knowledge Base. Review the fictional policy and run the approved-source search for delivery. To demonstrate a PDF, export `docs/demo/FICTIONAL_BUSINESS_POLICY.txt` to a small text PDF locally, upload it, inspect the unapproved extraction, then approve it. The automated browser scenario also imports a generated fictional PDF. A live public website import requires authorization and external network access; do not label a fixture as a fetched website.
3. **1:25–2:20 — Qualification.** In AI Qualification show the furniture rule weights and INR 50,000 minimum. With a working live model, select a fictional lead and send “I need curtains in Bengaluru, budget 80000 INR, next month.” Inspect extracted facts, evidence, immutable rubric version and deterministic points. Ask a delivery question on another new lead to show a cited answer; ask an unsupported warranty question to show human review. Exact live extraction is nondeterministic. In credential-free mode, show the executed generic-B2B simulator browser case and fixture evaluation results; name the fixture explicitly.
4. **2:20–3:15 — Signed intake and Inbox.** Create a website integration and save the secret privately. Use **Queue fictional test**, process one worker tick, then show the real Inbox receipt and CRM lead. Qualification defaults off; enabling it requires active rules and a saved working model. Website intake never sends an external message. For a live WhatsApp demonstration use only an authorized Meta test number and recipient, verify signatures/callback/status and the 24-hour window, then take over before a new message. If credentials are unavailable, show fixture-backed adapter tests and say live receive/send is unverified.
5. **3:15–4:10 — Human control and evidence.** Take over with a reason, show the audit timeline, and verify a later message is saved without another inference/send. Move the lead with the keyboard stage menu. Open Analytics, choose a UTC window, show real source/status/failure totals and definitions. Do not describe stage snapshots as revenue conversion.
6. **4:10–4:45 — Reliability.** Show readiness, shared rate-limit/concurrency tests, fixture evaluation evidence and deployment/backup notes. Explain the Docker runtime permission blocker and live-provider/Meta gates. Finish on the working UI, not a fabricated production-success banner.

## Repeatable checks and evidence

- `make test`: actual PostgreSQL integration/security/scoring/channel tests; use only an explicitly disposable `_test` database.
- `make evaluate`: 11 labeled model-output fixtures with expected fields, scores, grounding and escalation. Passes measure guardrails, not live-model accuracy.
- `backend/.venv/bin/python scripts/benchmark.py`: 30 serial in-process CRUD reads and signed acceptance requests. Report measured scope, never production throughput.
- `npm run test:e2e` in frontend with fixture flag: CRM, settings, simulator, Inbox and review-first PDF/analytics flows. Session 5 screenshots are in docs/evidence.

Do not record signing secrets, tokens, `.env`, real prospect data or private account settings. Crop once-displayed secrets out of any recording. No real outreach is needed for the fixture demo.
