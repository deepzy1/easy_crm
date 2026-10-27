# EasyCRM — API & Technical Specification

**Version:** 0.1 · **Draft contract:** Names and sample payloads are proposed; implement with OpenAPI-generated schemas and tests.

**Session 5 actual additions:** Generated `/openapi.json` remains authoritative; the older inventory below is a draft. Every workspace route below checks membership, with admin-only writes/import/export/delete. Timestamps are aware UTC; date intervals are `[since, until)`.

- `GET /api/v1/health/live` process liveness; `GET /api/v1/health/ready` schema/database and optional worker freshness (503 when unavailable). Existing `/api/v1/health` retains its database check.
- `GET /workspaces/{ws}/knowledge/sources` → `{items, can_manage}` over the existing reviewed-text store.
- `POST /workspaces/{ws}/knowledge/sources` → 201 source, body `{title, url, authorized:true}`. Public HTTPS, no credentials/query strings, bounded redirects/size/time; source is unapproved. Extraction failures return a persisted `state:"failed"` and authored `error`, never a success label.
- `POST /workspaces/{ws}/knowledge/uploads?title=...` → 201 source, **raw PDF bytes**, `Content-Type: application/pdf` (not the draft multipart contract). Limit 2 MiB, first 30 pages and 12,000 extracted characters; wrong MIME is 415, oversize is 413. Originals are discarded.
- `PATCH /workspaces/{ws}/knowledge/sources/{id}` with `{title,text,approved}` reviews/approves ready sources. `DELETE` removes a source from future retrieval. Historical audit citations remain.
- `GET /workspaces/{ws}/knowledge/search?q=...` returns up to three approved tenant-scoped verbatim excerpts, no provider call. The existing `/qualification/knowledge` manual text API is preserved.
- `GET /workspaces/{ws}/analytics/operations?since=...&until=...` returns lead/source/current-status/stage cohort counts, qualification rate, handoff conversations, receipt/message states, failures/unknown sends, measured timing samples/means and definitions. Admins also see the deployment worker heartbeat. Existing `/analytics/overview` retains all-time dashboard compatibility.
- `GET /workspaces/{ws}/leads/{id}/export` → audited admin JSON bundle of lead, notes, contact identities, channel threads/messages and qualification history. No integration/provider secrets. Not a complete legal subject report.
- Existing `DELETE /workspaces/{ws}/leads/{id}` is now admin-only. Pause all workspace integrations and drain pending/qualify/processing intake first (otherwise 409); deletion cascades subject history and redacts matching receipts. Minimal replay IDs/hashes remain. `GET /workspaces/{ws}/privacy/audit` returns the newest 50 minimal export/erase audits (admin; `limit` 1–100).

All error responses, including origin/oversize rejections, carry a server-generated `X-Request-ID` and safe JSON error. Fixed-window limits are shared across API/worker processes using atomic PostgreSQL counters; maintenance prunes expired counters and sessions. See [DEPLOYMENT.md](DEPLOYMENT.md) for proxy trust, operational controls and retention limits.

**Implementation update (27 October 2026):** Session 3's actual incremental API and payloads are documented in [SESSION_3_HANDOFF.md](SESSION_3_HANDOFF.md). In particular, `/qualification/simulate` accepts one persisted lead/message with an external receipt ID and aware timestamp, rather than the stateless conversation-array proposal below. Rules are immutable versions created by POST; activation is a separate POST. Reviewed business text uses `/qualification/knowledge`; website/PDF ingestion is not implemented. `/leads/{id}/qualification/control` provides auditable takeover/resume/close/override. Existing CRM status spells `needs-human`; the qualification state machine uses `needs_human` and maps it at the boundary. Generated OpenAPI is authoritative.

**Session 4 implementation:** Signed intake, durable worker/outbox, integrations and Inbox now exist. The exact implemented paths (including `/integrations` and per-integration `/webhooks/meta/{id}` callbacks) are listed in [SESSION_4_HANDOFF.md](SESSION_4_HANDOFF.md#actual-http-api); the older inventory below remains the broader draft. No template outreach or live Meta verification is claimed.

## 1. Conventions

- Base URL: `/api/v1`; JSON over HTTPS except binary document upload.
- REST user endpoints use `Authorization: Bearer <access_token>`; workspace scope from `/workspaces/{workspace_id}/...` route **plus verified membership**, never client-supplied body workspace ID.
- IDs: UUID strings; timestamps: UTC ISO 8601; paginated lists: `{items, next_cursor}`.
- Errors use consistent body: `{"error":{"code":"...","message":"...","request_id":"...","details":{}}}`. Never expose internal stacks.
- Mutations needing replay safety may accept `Idempotency-Key` header; enforce per workspace/route.
- Use 200/201 for sync success, 202 for async accepted, 400 invalid shape, 401 unauthenticated, 403 forbidden, 404 unavailable, 409 duplicate/conflict, 422 invalid fields, 429 rate limit.

## 2. Endpoint inventory

### Authentication and workspace (M1)

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | Public | Create user |
| POST | `/auth/login` | Public | Obtain token/session |
| GET | `/auth/me` | Signed-in | Current user and memberships |
| POST | `/workspaces` | Signed-in | Create workspace and admin membership |
| GET | `/workspaces` | Signed-in | List member workspaces |
| GET/PATCH | `/workspaces/{ws}/business-profile` | Member/Admin edit | Read/update company facts |
| GET | `/workspaces/{ws}/members` | Admin | List members |

### CRM (M1)

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/workspaces/{ws}/contacts` | Search/add contacts |
| GET/PATCH | `/workspaces/{ws}/contacts/{id}` | Contact details/update |
| GET/POST | `/workspaces/{ws}/leads` | Search/create leads, filter stage/status/source/owner |
| GET/PATCH | `/workspaces/{ws}/leads/{id}` | Lead details/update |
| POST | `/workspaces/{ws}/leads/{id}/stage` | Change pipeline stage |
| POST | `/workspaces/{ws}/leads/{id}/assign` | Assign salesperson |
| GET/POST | `/workspaces/{ws}/leads/{id}/notes` | Notes |
| GET | `/workspaces/{ws}/leads/{id}/timeline` | Activity + source history |
| GET | `/workspaces/{ws}/pipeline` | Kanban grouped leads |

### Generic webhook sources (M1)

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/workspaces/{ws}/integration-sources` | List/create source (admin) |
| POST | `/workspaces/{ws}/integration-sources/{id}/rotate-secret` | Rotate signing secret (admin) |
| PATCH | `/workspaces/{ws}/integration-sources/{id}` | Disable/enable (admin) |
| POST | `/webhooks/forms/{source_id}` | Public transport; HMAC-authenticated payload |

### Knowledge + AI (M2)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/workspaces/{ws}/knowledge/sources` | Add allowed website source |
| POST | `/workspaces/{ws}/knowledge/uploads` | Upload PDF (multipart) |
| GET | `/workspaces/{ws}/knowledge/sources` | Status, URL/name, version |
| POST | `/workspaces/{ws}/knowledge/sources/{id}/publish` | Approve ingestion for retrieval |
| GET/POST | `/workspaces/{ws}/qualification/templates` | List/create rubric templates |
| PUT | `/workspaces/{ws}/qualification/templates/{id}` | Update draft rubric |
| POST | `/workspaces/{ws}/qualification/templates/{id}/publish` | Publish version |
| POST | `/workspaces/{ws}/qualification/simulate` | Synthetic test run; no external sends |
| GET | `/workspaces/{ws}/leads/{id}/qualification` | Score, evidence, missing fields |

### Conversations and WhatsApp (M3)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/workspaces/{ws}/conversations` | Workspace inbox |
| GET | `/workspaces/{ws}/conversations/{id}/messages` | Message timeline |
| POST | `/workspaces/{ws}/conversations/{id}/takeover` | Switch to human mode |
| POST | `/workspaces/{ws}/conversations/{id}/resume-ai` | Explicitly resume AI with checks |
| POST | `/workspaces/{ws}/conversations/{id}/messages` | Staff-authored message; delivery rules apply |
| GET | `/webhooks/meta/whatsapp` | Meta challenge verification |
| POST | `/webhooks/meta/whatsapp` | Meta signed event ingestion |

### Metrics (M4)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/workspaces/{ws}/analytics/overview?from=...&to=...` | Leads by source and status, handoffs, response metrics |

## 3. Sample: create form integration source

`POST /api/v1/workspaces/{ws}/integration-sources`

```json
{
  "name": "Website contact form",
  "kind": "custom_form"
}
```

**201 sample:** secret returned **once**; hash/secret ref stored securely, never shown again.

```json
{
  "id": "5cfcc571-7b55-44d5-9179-397d7bb989c6",
  "name": "Website contact form",
  "kind": "custom_form",
  "webhook_url": "/api/v1/webhooks/forms/5cfcc571-7b55-44d5-9179-397d7bb989c6",
  "signing_secret": "example-show-once-secret"
}
```

## 4. Generic webhook signing contract

Source must sign the **raw request bytes** with HMAC-SHA256 using the source secret, encoding digest in hex:

- `X-EasyCRM-Event-ID: <unique-event-id>`
- `X-EasyCRM-Timestamp: <unix-seconds>`
- `X-EasyCRM-Signature: sha256=<hex-hmac>`
- Signed message bytes: `timestamp + "." + event_id + "." + raw_request_body` (UTF-8 for timestamp and ID; exact raw bytes for body).
- Reject stale timestamps (example ±5 minutes), invalid signatures, excessive body size and disabled source. Verify with constant-time comparison; protect secrets.
- Identical delivery/event ID and payload -> return accepted/already processed without duplicate mutation; same ID and differing payload -> 409 conflict.
- Browser-hosted forms **must not contain the signing secret**: post to the business's trusted backend/serverless endpoint which then signs and forwards to EasyCRM, or use a separately designed abuse-protected public form endpoint in a future milestone.

Example event body (sample customer information is fictional):

```json
{
  "event": "lead.created",
  "external_id": "WEB-1024",
  "occurred_at": "2026-10-26T10:00:00Z",
  "lead": {
    "name": "Rahul Example",
    "phone": "+919876543210",
    "email": "rahul@example.com",
    "interest": "Motorized curtains",
    "message": "Need curtains for five windows",
    "location": "Whitefield, Bengaluru",
    "consent_to_contact": false
  },
  "metadata": {"page": "/contact", "campaign": "organic"}
}
```

**202:** `{"delivery_id":"8bba8a36-2d6f-47e9-b7a5-169d6f125108","status":"accepted"}`.

## 5. CRM examples

`POST /api/v1/workspaces/{ws}/leads`

```json
{
  "contact_id": "3f7f1ab4-b817-4520-aa1a-4fd9de84d580",
  "title": "Curtains for 3BHK",
  "source_type": "manual",
  "pipeline_stage": "new"
}
```

`GET /api/v1/workspaces/{ws}/leads/{id}` (abbreviated)

```json
{
  "id": "ecb9c360-3d8e-427b-9bf0-2a0508f15401",
  "contact_id": "3f7f1ab4-b817-4520-aa1a-4fd9de84d580",
  "title": "Curtains for 3BHK",
  "pipeline_stage": "qualifying",
  "qualification_status": "collecting",
  "qualification_score": 45,
  "owner_user_id": null,
  "source_type": "website",
  "missing_fields": ["budget", "timeline"],
  "next_action": "Ask for budget"
}
```

## 6. AI simulation contract (M2)

`POST /api/v1/workspaces/{ws}/qualification/simulate`

```json
{
  "template_id": "8d8a765c-2e3e-4f79-9ad4-df6004a90356",
  "conversation": [
    {"role": "customer", "text": "Need blinds in Bengaluru next month, budget 80000 INR"}
  ]
}
```

**200 sample** (not a model guarantee):

```json
{
  "extracted": {
    "product_interest": {"value": "blinds", "evidence_message_index": 0},
    "location": {"value": "Bengaluru", "evidence_message_index": 0},
    "budget_inr": {"value": 80000, "evidence_message_index": 0},
    "timeline": {"value": "next month", "evidence_message_index": 0}
  },
  "score": 85,
  "score_type": "rubric_points",
  "qualification_status": "qualified",
  "missing_fields": ["measurement_count"],
  "reasons": ["Service area matched", "Budget provided", "Timeline provided"],
  "suggested_question": "How many windows need blinds?",
  "template_version": 1,
  "grounding_sources": []
}
```

## 7. WhatsApp API boundaries (M3)

Meta provider schemas, versions and policies evolve; use the **official current Meta documentation** when implementing. Preserve provider `message_id`, `phone_number_id`, conversation IDs, timestamps and delivery status. Validate Meta signature on raw body, ensure workspace integration mapping, idempotently persist, and check opt-out + service window/template authorization before sending. Never accept a browser request purporting to be Meta without cryptographic verification.

AI draft -> validated action -> outbound policy check -> provider send -> persist provider status. Recheck human mode at send time.

## 8. Security and acceptance checklist

- [ ] All workspace endpoints enforce membership and object ownership.
- [ ] Webhook signature/replay/size/rate-limit tests pass.
- [ ] Raw webhook body signature canonicalization exactly matches documented contract.
- [ ] PII omitted from application logs and secrets never returned after initial creation.
- [ ] Knowledge query hard-filters workspace and approved source version.
- [ ] API docs generated from implemented schemas (do not ship drifted examples).
- [ ] For every async operation expose useful status/failure and support safe retry.
- [ ] Integration test demonstrates signed webhook -> CRM lead -> AI test qualification -> salesperson review.
