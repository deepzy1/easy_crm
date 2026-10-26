# Session 1 — AI model management upgrade

Scope: model discovery, safe diagnostics, Settings, and the existing text Playground. Authentication, CRM, PostgreSQL ownership, and white/blue UI are preserved. No Session 2 RAG or lead qualification features were implemented. No dependencies or database schema changes are required.

## Original Gemini failure

On 26 October 2026, an explicit minimal generation request with the configured server key and the existing `gemini-2.5-flash` REST payload returned HTTP **404 `NOT_FOUND`**, classified as model unavailable for the key/API version. It was not a 401/403 authentication failure, a 429 quota response, or an explicit billing error. The original adapter mapped every other HTTP failure to “Provider rejected this request”, concealing the category. The request format matched Google’s documented `generateContent` contract.

Discovery with the same key succeeded and returned **34 text-compatible models**, including all eight requested IDs: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3-flash-preview`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`. This explicitly demonstrates that a listed model can still reject generation. The narrower account-side reason for the 404 is not exposed by our retained sanitized evidence; we do not claim that the model is universally retired or that billing caused it.

A separate explicit Test Model request for discovered `gemini-3.8-flash` through the new adapter returned HTTP **503**, categorized as provider temporarily unavailable. No automatic retries or fallback requests followed. Successful live generation remains unverified. NVIDIA has no configured key in this environment; its inference contract is verified with mocks only.

Google’s [model catalogue](https://ai.google.dev/gemini-api/docs/models) documents the current IDs. Its [deprecation guidance](https://ai.google.dev/gemini-api/docs/deprecations) describes restricted legacy 2.5 access. The application does not embed these example IDs or silently choose a default; the user selects from actual discovery results.

## Backend behavior

- Provider adapters: shared safe transport/error classification in `app/ai/providers.py`, Gemini REST in `app/ai/gemini.py`, NVIDIA OpenAI-compatible requests in `app/ai/nvidia.py`.
- `GET /api/v1/workspaces/{ws}/ai/models?provider=gemini|nvidia` requires membership. `refresh=true` requires admin and bypasses the cache. Metadata retrieval never triggers a generation test. Discovery has a separate workspace request throttle.
- Gemini follows `nextPageToken`, preserves the exact returned resource name and model suffix, deduplicates repeated IDs, and rejects looping/incomplete pagination. Only `generateContent` models suitable for text are offered; known audio/image-only variants are excluded. Future undocumented modality metadata may require adapter updates; use Test Model to verify compatibility.
- NVIDIA refreshes `/v1/models` presence for the exact IDs in `NVIDIA_MODELS`. Its generic list alone is insufficient to identify chat support or account inference access. The existing `nvidia/nemotron-3-ultra-550b-a55b` identifier remains supported and matches [NVIDIA’s reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b-infer). Other chat IDs can be configured after checking NVIDIA’s model reference. Unknown generic catalogue entries are not silently treated as chat models.
- Discovery cache: configurable 300-second TTL, maximum 16 credential/configuration combinations, no secrets stored (credential fingerprint only). Failed refresh exposes a sanitized error and marks any previous catalogue stale. No partial Gemini page set is cached.
- Generation observations: workspace/provider/model/credential scoped, 15-minute expiry, maximum 2,048 observations. “Verified working” records successful generation; “Available” only records provider listing. Status/observation caches are per-process and reset on restart; they are not durable account entitlements.
- Save uses the existing PostgreSQL `ModelPreference` row. Gemini must appear in discovery; NVIDIA must belong to its configured chat allowlist. Each Playground request reads the saved row immediately, with no backend restart. Saved generation is not blocked by catalogue refresh failures; upstream generation remains authoritative.
- Tests use a short fixed prompt and a 256-token output cap; Playground retains the 2,048-token cap. Thinking models can spend the cap on reasoning and return no usable text. That produces an explicit error without silently increasing the budget, retrying, or charging another model.

## Diagnostics and credential boundaries

The UI reports distinct categories: `missing_credentials`, `provider_auth`, `provider_access`, `provider_billing`, `provider_model_unavailable`, `provider_rate_limit`, `provider_request`, `provider_timeout`, `provider_network`, `provider_unavailable`, and `provider_response`.

Google can return invalid-key errors as HTTP 400; these are classified by known structured reasons/message signals. HTTP 403 without an invalid-key signal is described as restricted access rather than proof of an invalid key. Billing classifications require HTTP 402 or explicit billing/tier signals. Ambiguous 400 responses remain request errors. See [Google’s API errors](https://ai.google.dev/gemini-api/docs/api-errors).

Only authored messages, stable error categories, and numeric upstream statuses leave the adapter. Safe log records contain provider, status, and category, without upstream text, credentials, URLs, prompts, or response payloads. `GEMINI_API_KEY` and `NVIDIA_API_KEY` remain backend environment secrets. No key-entry UI, local storage, paid fallback, or automatic model testing is added.

Free-tier eligibility is always **unverified**, including after a successful test. Neither catalogue listing nor a successful request establishes that the request was free. Billing, pricing, account eligibility, quotas, and region remain controlled by providers.

## Verification

Automated tests mock all upstream provider responses. PostgreSQL integration and Playwright checks run against an isolated temporary database, with empty provider keys for the actual browser backend. The UI model workflows additionally use mocked HTTP endpoints. Final results on 26 October 2026:

- **Passed:** 66 pytest cases against real isolated PostgreSQL 16, with Alembic migrations and mocked upstream providers. Includes discovery/pagination, cache refresh/expiry/key rotation, malformed metadata, invalid keys, access/billing/quota distinctions, safe diagnostics, unsupported IDs, provider switching, saved preferences, Playground usage, workspace isolation, admin permissions, authentication, and CRM regressions. One existing Starlette/httpx deprecation warning remains.
- **Passed:** 7 Playwright scenarios in installed Chrome: 4 original foundation scenarios and 3 new model-management workflows. The 3 model scenarios were rerun successfully to capture final screenshots. Tests used dedicated ports 5174/8001 to avoid an older existing development server.
- **Passed:** TypeScript and Vite production build, Ruff lint/format, Prettier check, and `alembic check` (no schema drift).
- **Passed:** visual review of [desktop](evidence/ai-models-upgrade-desktop.png) and [390px mobile](evidence/ai-models-upgrade-mobile.png) captures. Both screenshots use fictional workspace data and **mocked** provider success/catalogues, not evidence of live inference.
- **Passed:** explicit live Gemini model discovery (34 text models).
- **Provider failures confirmed:** explicit original-model generation returned 404; the explicit current-model test returned 503. Neither is reported as successful inference. No retry or fallback was attempted.
- **Not executed:** live NVIDIA discovery/generation (no configured key), successful live Gemini generation, or remote CI/production deployment.

The temporary test services were stopped after verification. Existing development services, application data, and server credentials were not changed. No commits or pushes were made.

## Files changed

Paths are relative to the application root:

- Backend: `backend/app/ai/providers.py`, new `backend/app/ai/gemini.py`, new `backend/app/ai/nvidia.py`, new `backend/app/ai/catalogue.py`, `backend/app/api/ai.py`, `backend/app/core/config.py`, `backend/app/main.py`.
- Backend tests: `backend/tests/test_ai.py`, `backend/tests/conftest.py`, `backend/tests/test_crm.py`.
- Frontend: `frontend/src/AI.tsx`, `frontend/src/api.ts`, `frontend/src/styles.css`.
- Browser tests/configuration: new `frontend/e2e/ai-models.spec.ts`, `frontend/e2e/foundation.spec.ts`, `frontend/playwright.config.ts`.
- Configuration/documentation: `.env.example`, `README.md`, `docs/SESSION_1.md`, new `docs/AI_MODELS.md`.
- Visual evidence: new `docs/evidence/ai-models-upgrade-desktop.png`, new `docs/evidence/ai-models-upgrade-mobile.png`.
