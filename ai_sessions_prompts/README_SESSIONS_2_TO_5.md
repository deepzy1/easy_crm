# EasyCRM — Codex Sessions 2–5

These four prompts continue **after Session 1**. They are sequential and should be passed into Codex **one at a time**, with access to the current repo and original EasyCRM documentation.

| Session | File | Major outcome |
|---|---|---|
| 2 | `SESSION_2_BUSINESS_KNOWLEDGE_RAG.md` | Company knowledge + grounded RAG |
| 3 | `SESSION_3_AI_LEAD_QUALIFICATION.md` | Structured AI qualification + deterministic scoring |
| 4 | `SESSION_4_CHANNEL_INTEGRATIONS.md` | Website webhooks + WhatsApp; Meta/Instagram where permitted |
| 5 | `SESSION_5_PRODUCTION_PORTFOLIO.md` | Reliability, analytics, deployment, portfolio demonstration |

## Recommended workflow
1. Finish and test Session 1 before starting Session 2.
2. Attach the relevant `SESSION_N_*.md` in Codex; tell Codex to inspect the repo and complete that session's acceptance gates.
3. Before moving forward, review its `docs/SESSION_N_HANDOFF.md`, migration and test results. Fix blockers.
4. Commit each successful session to Git with a descriptive message.

**Project identity:** EasyCRM. **Visual reference:** Attio-inspired, clean white background and blue accent. **Technical focus:** FastAPI, PostgreSQL, React, Gemini/NVIDIA model selection in UI, RAG, explainable lead qualification, secure webhooks and WhatsApp CRM integration.

No real API keys belong in Git. Configure server-side environment variables and never expose them in frontend bundles. Live third-party integrations depend on provider credentials, permissions, account/app configuration and compliance requirements.
