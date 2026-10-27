# EasyCRM deployment and operations

Session 5 supplies a modular-monolith deployment, not a hosted service. Use Python 3.12, PostgreSQL 16, Node 22 and Poppler on Ubuntu for local development; see README. No real application database was used in release tests. The Docker daemon was inaccessible in this session, so image builds and Compose startup remain deployment gates.

## Configure and start

Run from the application root containing `compose.yaml`:

```bash
cp .env.example .env  # only on first setup; preserve an existing .env
```

Choose a unique URL-safe database password, set `CORS_ORIGINS=["https://crm.your-domain.example"]`, and generate a stable `WEBHOOK_MASTER_KEY` with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. Store secrets outside Git with restricted permissions (`chmod 600 .env`). Optional inference and Meta keys stay exclusively on the backend/worker. Preserve this master key with encrypted configuration backups; replacing it revokes website signing secrets. Do not print a resolved Compose configuration into public logs because it includes environment values.

```bash
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml up -d --build
docker compose -f compose.production.yaml ps
curl --fail http://127.0.0.1:8080/api/v1/health/ready
```

Production frontend is a compiled SPA in unprivileged Nginx, listening only on host loopback 8080. Database and API have no published ports. The one-shot migration completes before API and worker start. Backend/worker run non-root with dropped capabilities, read-only filesystems, bounded temporary storage, 512 MiB memory and PID limits. The API refuses production startup without secure cookies, HTTPS CORS origins, a stable signing master key and current migrations. The worker writes a heartbeat after successful ticks; readiness requires a heartbeat newer than 180 seconds. One worker tick may include a provider timeout; tune/monitor this freshness threshold before scaling.

Put a trusted TLS reverse proxy on the host, forwarding `https://crm.your-domain.example` to `127.0.0.1:8080`. Configure certificate renewal and HSTS at that edge. Do not sign in over loopback HTTP in production: cookies are intentionally Secure. Publish the same HTTPS `/api/v1/webhooks/meta/{integration_id}` callback to Meta. Nginx serves SPA fallback, routes `/api/`, applies a 2 MiB body cap, CSP/frame/referrer controls and edge throttles. External Google font requests may be blocked by CSP; system font fallback remains available. Never expose internal FastAPI directly to the internet.

API-level counters are shared in PostgreSQL. The included API ignores forwarded headers; auth counters therefore see a conservative shared proxy address. Edge limits similarly see your outer TLS proxy unless configured with an explicitly trusted real-IP range. This trades per-client fairness for spoof resistance. Configure that trust at your chosen edge before public multi-user use. Do not blindly trust arbitrary `X-Forwarded-For` headers.

For code updates, back up first, then repeat `up -d --build` (restart alone cannot update code baked into an image). Monitor readiness and worker logs. Roll back application images only after checking compatibility with the additive database revision; do not downgrade a real database casually. The dev and production Compose files use separate project names and named volumes. Moving existing data requires a reviewed dump/restore; switching files does not migrate the development volume automatically.

## Back up and restore

Backups contain personal data. Use encrypted storage with access controls and an explicit expiry policy. Keep signing/provider secrets separately. This example makes a custom-format PostgreSQL dump; it does not copy `.env` into the archive:

```bash
umask 077
mkdir -p backups
docker compose -f compose.production.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/easycrm.dump
```

Only restore into a **new empty database** after reviewing the target. Stop intake/worker and keep the original database/volume intact until verification. On a PostgreSQL host with appropriate operator access:

```bash
createdb easycrm_restore_test
pg_restore --exit-on-error --no-owner --no-privileges --dbname=easycrm_restore_test backups/easycrm.dump
psql easycrm_restore_test -c 'SELECT version_num FROM alembic_version;'
psql easycrm_restore_test -c 'SELECT count(*) FROM leads;'
```

Use a separate restore `DATABASE_URL`, run `alembic check`, verify workspace/lead/source counts, sign in to a fictional test account and confirm tenant boundaries. Document recovery time and backup age from the actual drill. A local disposable-database dump/restore was executed for Session 5; remote encrypted storage, scheduled backups and actual host recovery are not verified. Set `backups/` outside Git (also ignored locally). Never use `docker compose down -v` on valuable data.

## Daily operations and failure inspection

Run `docker compose -f compose.production.yaml exec -T backend python -m app.channel_maintenance` daily through your scheduler. It removes expired sessions/counters, request logs older than 30 days and terminal intake content older than 30 days while retaining replay identifiers. Active CRM/message histories are not automatically expired.

Watch `/api/v1/health/live` and `/api/v1/health/ready`, structured API/worker logs, Analytics failures/unknown sends and Integrations delivery states. Configure alerts for readiness 503, increasing failed/unknown deliveries, stale worker heartbeat and queued backlog; no external alert destination is preconfigured. Logs omit bodies/PII/provider errors and use generated request IDs. Do not enable access logs that record Meta verification query tokens.

Stop/restart a stuck worker before using admin `/integrations/recover`; claims older than ten minutes become failed (inference) or unknown (send). Failed unredacted intake can be explicitly retried; it may spend provider quota. Unknown sends require provider-side reconciliation and are never automatically resent. Automatic backoff is limited to safe transport cases, five attempts. Paid inference has no automatic retry or model fallback. Inbox takeover cancels stale queued AI work; an HTTP send already in progress cannot be recalled.

## Security and release limits

- Website ingestion: public HTTPS only, vetted/pinned DNS, redirect revalidation, no credentials/query strings, no proxy environment/cookies/JS/crawling; 2 MiB and bounded read time. Restrict outbound network access at the host as defense in depth. DNS resolution uses OS resolver timeouts. No live external-page fetch is claimed by fixture tests.
- PDFs: content signature/type/size validation, ten-second Poppler subprocess, 256 MiB child address-space/64 KiB output-file/eight-second CPU limits, disabled core dumps, first 30 pages, text cap, discarded originals and unprivileged/container limits. The helper uses POSIX resource limits (Ubuntu/Linux). No OCR, antivirus, advanced parser sandbox or comprehensive malformed-PDF security proof. Keep Poppler updated and review content before publishing.
- Knowledge/source and customer text remain untrusted model inputs. Only approved workspace excerpts enter inference; citations are checked verbatim. Prompt-injection regexes/evidence checks are conservative, not semantic guarantees. Live quality and multilingual safety require a representative evaluation set.
- Export/delete is admin-only and audited. Pause all integrations, drain intake, delete the scoped lead, then review residual sources/backups. Minimal receipt IDs/hashes remain for replay defense and may be personal identifiers; set a policy before deployment. Restore processes must reapply outstanding erasure requests.
- Membership administration, password reset/email verification, formal accessibility/security review, production load/fairness, dependency/image pinning, license selection, monitoring and live Meta app/account permissions remain release gates. This MVP has no legal/compliance certification or production SLA.
