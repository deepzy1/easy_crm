# Session 4 handoff — channels and unified inbox

Implemented on 27 October 2026 in the existing FastAPI/PostgreSQL/React application. New Alembic revision: `01e3724d4b96`, following `57002a21df59`. No dependency changes. No real tokens, provider calls, prospect messages, commits or pushes were used for verification.

## Delivered behavior

- Admin-only Integrations page creates signed website integrations, displays a newly generated secret once, rotates/revokes keys, enables qualification explicitly, tests a fictional event or a real account lookup, and shows minimized delivery/error logs.
- Raw-body HMAC, a five-minute timestamp window, 64 KiB request limit, bounded per-process rate limits, receipt uniqueness and conflict checking protect website intake. Workspace authority comes from the integration, never the event body.
- Meta challenge/signature verification and official WhatsApp text/status parsing. Only the configured phone-number ID is accepted. Media/echo/unmapped events are acknowledged as ignored, with no invented transcript.
- PostgreSQL durable receipts, contact identities, per-integration threads, inbox messages and transactional outbound queue. The API commits accepted events before acknowledgment; inference and Graph calls happen in a separate worker.
- Inbox lists messages and delivery states, qualification score/context and CRM links. Mode changes require a reason. Manual replies take over, record the actor, use stable request IDs and cancel queued AI replies.
- Facebook leadgen notifications fetch authorized lead details using `GET /{leadgen_id}`. Instagram Login professional-account inbound text is receive-only. Both have fixture contract tests and no live verification.

## Start and configuration

From the application root (the directory containing `compose.yaml`):

```bash
# Add the settings below to the existing .env; do not overwrite your existing file.
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# Store output as WEBHOOK_MASTER_KEY; retain it in deployment secret storage.
make migrate
make backend
# Separate terminals:
make frontend
make channel-worker
```

Docker users rebuild code-baked images and run migrations/worker with:

```bash
docker compose up -d --build
```

Compose now includes `channel-worker`, using the same backend image, database and `.env`. A container restart alone does not rebuild changed source. This session did not rebuild or migrate the user's running application database.

New environment settings:

- `WEBHOOK_MASTER_KEY`: at least 32 random characters. Signing keys are HMAC-derived from the integration ID and monotonically increasing key version. Database rows contain no plaintext signing secret. All API instances need the same master key. Rotation increments the version, immediately revoking the old key. Replacing the master key revokes every website key; retain it with backups.
- `META_GRAPH_VERSION`: explicit Graph version supported by your app; example/default `v25.0`. Check your Meta dashboard before enabling live use; this is not a claim that the example is the latest version.
- `META_CONNECTIONS`: backend-only JSON mapping. Each alias is bound to a workspace UUID, channel kind and external account ID. This server-authored binding prevents another workspace admin claiming your account. Example with placeholders:

```dotenv
META_CONNECTIONS={"whatsapp-test":{"workspace_id":"WORKSPACE_UUID","kind":"whatsapp","external_account_id":"PHONE_NUMBER_ID","app_secret":"APP_SECRET","verify_token":"RANDOM_VERIFY_TOKEN","access_token":"ACCESS_TOKEN"}}
```

Use `meta_leads` with a Facebook Page ID, or `instagram` with an Instagram professional-account ID. Aliases appear only to their authorized workspace admin; secrets never appear in settings, logs or frontend bundles. Change Meta tokens in server secret storage and restart both API and worker. There is no OAuth onboarding or encrypted token editor in this session.

## Website schema, mapping and integration sample

Create a Website integration in the UI. Optional field mapping is canonical field → key in the top-level `lead`/`form` object, e.g. `{"name":"full_name","phone":"mobile","message":"enquiry"}`. Supported fields: `name`, `email`, `phone`, `company`, `message`, `external_contact_id`, `consent_to_contact`. Email is normalized; phone requires international `+` country code. At least email, phone or external contact ID is required. `occurred_at` must include a timezone if supplied. Text is limited to 4,000 characters. Unmapped arbitrary fields are discarded; they do not enter inference or storage.

```json
{"event":"lead.created","occurred_at":"2026-10-27T08:00:00Z","lead":{"name":"Fictional prospect","email":"prospect@example.com","phone":"+919876543210","message":"I would like product information","consent_to_contact":false}}
```

Save that fictional JSON as `/tmp/easycrm-event.json`. The trusted website backend can use the executable sample:

```bash
read -rs -p 'Website signing secret: ' EASYCRM_WEBHOOK_SECRET; echo
export EASYCRM_WEBHOOK_SECRET
python3 scripts/send_website_event.py \
  --url 'http://localhost:8000/api/v1/webhooks/forms/INTEGRATION_UUID' \
  --event-id 'website-submission-1024' --body-file /tmp/easycrm-event.json
unset EASYCRM_WEBHOOK_SECRET
```

Equivalent cURL, with signing performed only on a trusted server:

```bash
export EASYCRM_EVENT_ID=website-submission-1024
export EASYCRM_TIMESTAMP="$(date +%s)"
export EASYCRM_BODY_FILE=/tmp/easycrm-event.json
# EASYCRM_WEBHOOK_SECRET must already be set server-side, as above.
EASYCRM_SIGNATURE="$(python3 - <<'PY'
import hashlib, hmac, os
from pathlib import Path
raw = Path(os.environ['EASYCRM_BODY_FILE']).read_bytes()
value = os.environ['EASYCRM_TIMESTAMP'].encode()+b'.'+os.environ['EASYCRM_EVENT_ID'].encode()+b'.'+raw
print('sha256='+hmac.new(os.environ['EASYCRM_WEBHOOK_SECRET'].encode(), value, hashlib.sha256).hexdigest())
PY
)"
curl --fail-with-body 'http://localhost:8000/api/v1/webhooks/forms/INTEGRATION_UUID' \
  -H 'Content-Type: application/json' \
  -H "X-EasyCRM-Event-ID: $EASYCRM_EVENT_ID" \
  -H "X-EasyCRM-Timestamp: $EASYCRM_TIMESTAMP" \
  -H "X-EasyCRM-Signature: $EASYCRM_SIGNATURE" \
  --data-binary @/tmp/easycrm-event.json
unset EASYCRM_SIGNATURE EASYCRM_WEBHOOK_SECRET
```

Reuse the event ID and exact body for redelivery; generate a fresh timestamp/signature within five minutes. Same ID/body is a duplicate, changed body is HTTP 409, invalid/stale signatures are 401. Successful intake returns HTTP 202 with a durable `delivery_id`; processing completion is separate.

A public HTML form sends only to **your trusted website backend**, never directly to the signed EasyCRM endpoint:

```html
<form action="/enquiries" method="post">
  <label>Name <input name="full_name" maxlength="100" required></label>
  <label>Email <input name="email" type="email" required></label>
  <label>Enquiry <textarea name="enquiry" maxlength="4000" required></textarea></label>
  <label><input type="checkbox" name="consent_to_contact" value="true"> I agree to requested follow-up.</label>
  <button type="submit">Send enquiry</button>
</form>
```

Your site's `/enquiries` handler applies its normal CSRF/abuse controls, assigns a persistent submission ID, converts form values to the JSON envelope, and forwards exact bytes using `signed_headers` from the sample Python client. Store the signing secret exclusively in that server's environment. This is a backend integration example, not an unsecured public relay included in EasyCRM. Website ingestion never sends an external message, even with qualification enabled or consent recorded.

## Meta app setup and callback steps

1. Create/configure a Meta business app and WhatsApp product. Use your WhatsApp Business Account's test phone-number ID and explicitly approved recipient test number from **WhatsApp → API Setup**. This repository has no real test phone numbers configured.
2. Obtain an authorized token with `whatsapp_business_messaging`; business/phone administration uses `whatsapp_business_management`. Add business management permissions only when your actual asset queries require them. Temporary dashboard tokens expire; choose and rotate an appropriate system-user token for longer tests. The UI's account lookup tests only visibility, not messaging entitlement.
3. Put the phone-number ID, app secret, random verify token, token and actual EasyCRM workspace UUID into `META_CONNECTIONS`. Restart API and worker; create the matching WhatsApp integration in the admin UI.
4. Expose the API through a public HTTPS callback. Copy `/api/v1/webhooks/meta/{integration_id}` from the UI into Meta's webhook setup and supply the exact backend verify token. Meta sends `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`; successful verification returns the challenge as plaintext.
5. Subscribe to `messages` on the intended WABA/phone asset. POST signatures are HMAC-SHA256 over the exact raw body using the app secret, in `X-Hub-Signature-256`. Events for a different phone-number ID are ignored even when signed by the same app.
6. Activate qualification rules and save the workspace's Gemini/NVIDIA model. Enable the integration's AI policy explicitly; it defaults off. Send a text **from the approved test recipient** to the test business number. Verify receipt → Inbox → assessment → outbound status → Meta delivery receipt. Use Inbox takeover, then send again; there must be no AI send. Perform this live check before enabling customers.
7. Facebook Lead Ads: separately bind a `meta_leads` alias to the authorized Page. Subscribe the Page's `leadgen` field and configure leads access for the token holder. `leads_retrieval` is required for reading submissions; Page subscription/asset discovery commonly require `pages_manage_metadata`, `pages_show_list`, `pages_read_engagement`, with additional ad permissions depending on the app's actual operations. Check the current app review and asset-task requirements in Meta's dashboard; a Page ID alone gives no access. Use Meta's lead testing tool before any production approval claim.
8. Instagram: use **Instagram API with Instagram Login** with a professional account, authorized app/test roles, `instagram_business_basic` and `instagram_business_manage_messages`, and the account's `messages` webhook subscription. Bind the IG account ID to an `instagram` alias. The implemented adapter validates inbound text and ignores echoes. No Instagram outbound composer, private-message scraping or Facebook-Login fallback is provided.

Official references checked on 27 October 2026:

- [Current WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/) — opt-out, 24-hour window and approved templates, updated 23 September 2026.
- [Meta's official WhatsApp Cloud API Postman collection](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api) — assets, tokens and WhatsApp permissions.
- [Meta's webhook SDK reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/) — raw-body signature and challenge contract. This SDK is archived; it is not a runtime dependency.
- [Facebook lead retrieval setup](https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving/) and [Instagram Login messaging](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/messaging-api) — live account setup references. Direct access to these pages was blocked/rate-limited in this environment; P1 permissions and live contracts require dashboard confirmation. No app review approval is claimed.

Free-form WhatsApp text is allowed only before **last customer event timestamp + 24 hours**. Receipt time/status events cannot extend the window; old/future customer timestamps cannot open a new current window. Outside it, the worker blocks sends with `service_window_closed_approved_template_required`. Template management/outreach is deliberately unavailable; no unapproved or unsolicited template can be queued. Inbound service replies do not grant marketing consent. An opt-out is sticky across all known identities for that lead and blocks both manual/AI sends. AI messages identify themselves as an automated assistant; human escalation is available in Inbox.

## State, retries, concurrency and retention

- Event states: `pending` → `qualify` → durable `processing` claim → `done`/`failed`; disabled integrations become `cancelled`. Leadgen GET failures with known transient causes retry up to five attempts, with exponential delays. No raw third-party error is retained.
- Contact resolution is serialized per workspace. Known normalized email/phone/external identities attach to one lead; conflicting identities are sent to visible failure for manual review, rather than silently merging people. Existing CRM leads can be matched by exact stored email/phone; new events enrich missing contact fields without overwriting human edits. Historical channel source stays on the integration/thread; the original lead source remains its first attribution. Contacts are internal identity records, not a general contact-management UI.
- A lead retains one canonical Session 3 qualification thread. Verified channel workers opt into sharing it; incoming event channel and receipt ID remain distinct. Simulator semantics are preserved. Real channel receipts use the durable inbound UUID when entering the core, avoiding cross-integration receipt collisions.
- Every message persists before inference. Paused messages remain in Inbox without inference. Provider/configuration failures preserve inbound data and become `failed`; **paid inference never retries automatically**. Admin Retry is explicit and may use quota. A durable `processing` marker survives an inference crash, preventing silent repeated paid calls.
- Outbox states: `queued` → `sending` → `sent`/`delivered`/`read`, or `failed`/`unknown`/`cancelled`. Each logical AI/manual message has a unique database dedupe key. Multiple workers cannot claim one queued send twice. Final dispatch checks active integration, latest mode/control version, canonical qualification state, opt-out, supported channel and service window. The integration policy lock uses PostgreSQL NO KEY UPDATE so inbound receipt foreign-key checks can proceed during Graph I/O.
- Confirmed connection failures/HTTP 429 retry up to five attempts with exponential backoff. HTTP 5xx after POST, response-read timeout or malformed success is **unknown**, because Meta may have accepted the message. They are not resent automatically. Signed status receipts correlate using external ID or `biz_opaque_callback_data` and monotonically advance delivery state. Permanent API rejections become failed.
- Human control cancels queued AI messages and increments a version, so takeover followed by resume cannot revive stale replies. During inference the channel mode can change without waiting on the core's lead lock; the core is synchronized when available and after inference. Thread/integration/contact/lead locks serialize the final HTTP attempt against control changes. An HTTP send already in progress cannot be recalled; no exactly-once external delivery claim is made.
- After stopping/restarting a stuck worker, admin `POST /integrations/recover` marks claims older than ten minutes as failed (inference) or unknown (send). It does not resend. Inspect Meta before any manual follow-up. The API has no unsafe Retry button for unknown outbound messages.
- Raw requests are never stored. Normalized envelopes contain only supported contact fields, text, timestamps and bounded attribution; delivery logs omit PII and secrets. Run `make channel-maintenance` daily: remove request logs older than 30 days and redact completed/failed/cancelled event envelopes while retaining hashes for replay defense. Redacted events cannot be retried. Inbox, CRM/contact and historical qualification data persist until the existing scoped lead deletion; automated subject retention/export remains Session 5 work.
- Rate limits are bounded **per process**, not globally shared. PostgreSQL queue processing is intentionally simple: one intake, one qualification and one outgoing message per worker tick, with row locks and durable claims. Shared gateway throttling, fair scheduling, throughput/load limits, provider Retry-After interpretation, and production monitoring are follow-ups.

## Actual HTTP API

All paths start `/api/v1`. Admin is required for `/workspaces/{ws}/integrations...`; members can use Inbox. No public caller selects a workspace.

- `GET/POST /workspaces/{ws}/integrations`; create `{name, kind, credential_alias?, ai_enabled:false, field_map:{}}`.
- `PATCH /workspaces/{ws}/integrations/{id}` with `{active, ai_enabled}`.
- `POST /workspaces/{ws}/integrations/{id}/rotate` returns a new website secret once.
- `POST /workspaces/{ws}/integrations/{id}/test` queues an explicit fictional website event or performs a real Meta account lookup.
- `GET /workspaces/{ws}/integrations/deliveries` returns latest 100 receipts and 100 request outcomes.
- `POST /workspaces/{ws}/integrations/deliveries/{id}/retry`; failed, unredacted events only.
- `POST /workspaces/{ws}/integrations/recover`; stopped-worker claim recovery described above.
- `POST /webhooks/forms/{id}` → 202 accepted/duplicate; documented HMAC headers.
- `GET/POST /webhooks/meta/{id}` → challenge or immediate durable acceptance; stable integration-specific callback, not the draft shared `/meta/whatsapp` path.
- `GET /workspaces/{ws}/inbox` returns latest 100 threads; `GET /inbox/{id}/messages` returns latest 200 messages in time order.
- `POST /workspaces/{ws}/inbox/{id}/control` with `{mode:"human"|"ai", reason}`.
- `POST /workspaces/{ws}/inbox/{id}/messages` with `{request_id, text}` → 202 queued. Same ID/text replays; changed text conflicts. Only permitted in-window WhatsApp messages can be queued.

## Verification and Session 5 gaps

Executed checks: **132 backend tests passed**, **10 browser scenarios passed** (37.7 seconds), and the final channel browser case passed again after mobile timing fixes (11.6 seconds). Ruff, formatting, TypeScript/Vite build, Alembic drift check, Compose config and whitespace checks passed. The existing Starlette/httpx TestClient deprecation warning remains. See [verification evidence](evidence/session-4-verification.json) and [desktop](evidence/session-4-desktop.png)/[mobile](evidence/session-4-mobile.png) screenshots. PostgreSQL tests use explicitly disposable databases ending `_test`; browser scenarios create fictional accounts and exercise real API/SQL/worker code. External inference/Meta success is fixture-based in backend tests. Browser channel success uses signed fictional website intake with AI disabled; no external channel/provider sends occur.

Repeat from the application root:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/easycrm_test'
make test
cd backend
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic check
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
cd ../frontend
npm run build
npm run format:check
# Set DATABASE_URL to a separate, migrated disposable browser database.
PLAYWRIGHT_QUALIFICATION_FIXTURE=1 npm run test:e2e
```

Do not enable customers until live WhatsApp receive/send/status/takeover is proven with authorized test assets, including public HTTPS webhook delivery. Facebook/Instagram app review/access remain external gates. Session 2 website/PDF ingestion remains absent. Session 5 still needs production hosting/TLS, globally shared throttling, alerting, backup/restore exercises, formal retention/erasure policy, load/fairness checks, live-provider quality evaluation, broader multilingual opt-out handling, and review of account-specific Meta permissions. Existing automated tests are not evidence for those external gates.

Changed areas: `models/entities.py`, additive migration, `schemas/channels.py`, `services/{channels,webhooks,qualification}.py`, `integrations/meta.py`, `api/channels.py`, `core/config.py`, `main.py`, `channel_worker.py`, `channel_maintenance.py`, `frontend/src/Channels.tsx`, App/styles, tests, Compose/Make/environment sample, trusted-server signing client and implementation docs.
