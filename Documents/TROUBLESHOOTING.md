# Troubleshooting

Common failures and how to fix them. Start with
[First: what does health say?](#first-what-does-health-say) — it narrows most
problems in one request.

---

## First: what does health say?

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "degraded",
  "checks": { "database": false, "redis": true }
}
```

| Result | Go to |
| --- | --- |
| Connection refused | [The app will not start](#the-app-will-not-start) |
| `"database": false` | [Database](#database) |
| `"redis": false` | [Redis](#redis) |
| `status: healthy` but a request fails | Find the request's `X-Request-ID` and grep the logs for it |

Every response carries an `X-Request-ID` header that also appears in that
request's log line — the fastest way to find what actually happened:

```bash
docker compose -f docker-compose.prod.yml logs app | grep "<request-id>"
```

---

## The app will not start

### `ValidationError: Field required`

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
APP_NAME
  Field required
```

**Cause.** A required variable is missing. Settings are loaded at import, so
this happens before the server binds a port.

**Fix.** Confirm `.env` exists and is in the directory you launched from:

```bash
cp .env.example .env
```

Required with no default: `APP_NAME`, `APP_VERSION`, `DATABASE_URL`,
`REDIS_URL`, `JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`.

### `Extra inputs are not permitted`

```
POSTGRES_USER
  Extra inputs are not permitted
```

**Cause.** `.env` contains a key that `Settings` does not declare. Unknown
keys are rejected on purpose — it catches typos like `DATABSE_URL` that would
otherwise silently fall back to a default.

**Fix.** Correct the spelling, or add the field to `app/core/settings.py` if
the variable is genuinely new.

### `DEBUG must be False when ENVIRONMENT=production`

```
Value error, DEBUG must be False when ENVIRONMENT=production.
JWT_SECRET_KEY must be at least 32 characters when ENVIRONMENT=production.
```

**Cause.** Deliberate. The app refuses to boot with an insecure production
configuration rather than starting and quietly being unsafe. All problems are
reported at once, so you can fix them in one pass.

**Fix.** Set `DEBUG=false`, generate a real secret, and remove `*` from
`CORS_ALLOWED_ORIGINS`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### `JWT_SECRET_KEY is still the public sample value from .env.example`

**Cause.** `.env.example` ships working development secrets so a fresh
checkout runs immediately. They are committed to source control, so anyone
could forge tokens or decrypt stored Instagram tokens on an instance still
using them. Production refuses to start rather than let that happen.

**Fix.** Generate real values:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `Fernet key must be 32 url-safe base64-encoded bytes`

**Cause.** `TOKEN_ENCRYPTION_KEY` is not a valid Fernet key — often a
hand-typed value or one generated with `token_hex`.

**Fix.**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> Changing this key makes every stored Instagram token undecryptable.
> Affected users must reconnect.

### `Address already in use`

```bash
uvicorn app.main:app --reload --port 8001
```

Or find and stop the process holding port 8000:

```bash
netstat -ano | findstr :8000
```

```bash
lsof -i :8000
```

---

## Database

### `connection to server at "localhost", port 5432 failed: Connection refused`

**Cause.** Postgres is not running, or not reachable at the configured host.

**Fix.** Start it and confirm:

```bash
docker compose up -d postgres
```

```bash
docker compose ps
```

```bash
docker compose logs postgres
```

If Postgres runs on the host rather than in Docker, check the service is up
and that `DATABASE_URL` matches its port.

### `could not translate host name "postgres"`

**Cause.** `DATABASE_URL` uses the Docker service name `postgres`, but you
are running the app **outside** Docker, where that name does not resolve.

**Fix.** Use `localhost` in `.env` for host runs:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/instagram_ai
```

`docker-compose.prod.yml` overrides this to `postgres` inside the network, so
one `.env` serves both.

### `password authentication failed for user "postgres"`

**Cause.** `DATABASE_URL` credentials do not match the running server. A
common trap: `POSTGRES_PASSWORD` only takes effect when the data volume is
**first created**, so changing it later does not change the actual password.

**Fix.** Either use the original password, or reset the volume — which
**deletes all local data**:

```bash
docker compose down -v && docker compose up -d
```

### `database "instagram_ai" does not exist`

```bash
docker compose exec postgres createdb -U postgres instagram_ai
```

### `relation "users" does not exist`

**Cause.** Migrations have not run.

```bash
alembic upgrade head
```

### `Can't locate revision identified by '...'`

**Cause.** `alembic_version` names a revision that is not in
`alembic/versions/` — usually after switching branches.

**Fix.** Check both sides:

```bash
alembic history
```

```bash
docker compose exec postgres psql -U postgres -d instagram_ai -c "SELECT * FROM alembic_version;"
```

Then either check out the branch containing that revision, or, on a
disposable local database, reset:

```bash
docker compose down -v && docker compose up -d && alembic upgrade head
```

### `Target database is not up to date`

Autogenerate refuses to run when pending migrations exist.

```bash
alembic upgrade head
```

### A migration fails partway

**Cause.** Usually adding a `NOT NULL` column to a table with existing rows.

**Fix.** Postgres runs DDL transactionally, so the failed migration rolled
back. Either clear the table (development), or split the change into three
steps: add the column nullable → backfill → set `NOT NULL`.

Always preview first:

```bash
alembic upgrade head --sql
```

---

## Redis

### `Error 10061 connecting to localhost:6379`

**Cause.** Redis is not running.

```bash
docker compose up -d redis
```

```bash
docker compose exec redis redis-cli ping
```

Expect `PONG`.

### The app works but responses are slow

**Symptom.** Requests to `/insights` or `/reports/*` take several seconds
longer than expected, and the logs show:

```json
{"level": "WARNING", "logger": "app.cache", "message": "cache read failed, generating fresh"}
```

**Cause.** Redis is unreachable. This is *designed* behavior — the cache
fails open, so the request regenerates instead of failing. The cost is
latency and an extra Gemini API call.

**Fix.** Restore Redis. Nothing is broken in the meantime.

### Background jobs never finish

`GET /jobs/{job_id}` stays `queued` forever.

**Cause.** No worker is consuming the queue.

```bash
python -m app.worker
```

Or in Docker:

```bash
docker compose -f docker-compose.prod.yml up -d worker
```

```bash
docker compose -f docker-compose.prod.yml logs -f worker
```

---

## Authentication

### `401` on every request right after deploying

**Cause.** Expected once. Access tokens now carry a `type` claim that older
tokens lack, so tokens issued before that change are rejected.

**Fix.** Log in again. See
[DEPLOYMENT.md § Upgrading](DEPLOYMENT.md#14-upgrading-an-existing-deployment).

### `401 Could not validate credentials` with a fresh token

Work through these in order:

1. **Header format** — must be `Authorization: Bearer <token>`, with the
   space and no quotes.
2. **Expiry** — tokens last `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 30).
   Log in again.
3. **Wrong token type** — an Instagram OAuth `state` token is not an access
   token; this is rejected deliberately.
4. **`JWT_SECRET_KEY` changed** — rotating it invalidates every issued token.
5. **The user was deleted** — the token is valid but resolves to nobody.

### `401` on login with the right password

**Cause.** The login form field is named `username` (an OAuth2 convention),
but this API authenticates by **email**. Sending an actual username fails.

**Fix.** Put the email address in the `username` field.

### `429 Rate limit exceeded` while testing

**Cause.** Login and register allow 5 requests/minute per IP; AI endpoints
allow 10/minute.

**Fix.** Wait a minute, or raise the limit locally in `.env`:

```
RATE_LIMIT_AUTH=100/minute
```

Do not raise these in production — they are brute-force protection.

---

## Instagram OAuth

This app uses **Instagram API with Instagram Login** — see
[ARCHITECTURE.md § 5](ARCHITECTURE.md#5-instagram-oauth-and-graph-api-integration)
for why, and [SETUP.md](SETUP.md#3-configure-environment-variables) for how
to configure a Meta app for it correctly the first time. The entries below
are for diagnosing it after the fact.

### `503 Instagram integration is not configured`

Set all three:

```
INSTAGRAM_APP_ID=...
INSTAGRAM_APP_SECRET=...
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/v1/instagram/callback
```

Then restart the app — settings load at startup.

### `Feature unavailable: Facebook Login is currently unavailable for this app`

**Cause.** This means the app has no product configured that can serve a
login dialog at all — usually because setup started under **Facebook
Login → Settings** or the generic **Use cases** picker instead of the
Instagram-specific product page.

**Fix.** Don't configure Facebook Login. Go to **Instagram → API setup with
Instagram login** in the left sidebar instead — that page is self-contained
and doesn't require adding a separate Facebook Login use case. Also confirm
**Settings → Basic** has both **Category** and **Privacy Policy URL** set;
Instagram Login won't serve at all without them.

### `Invalid Scopes: instagram_basic, instagram_manage_insights, pages_show_list, pages_read_engagement`

**Cause.** The app is requesting permissions from Meta's older,
Facebook-Login-based Instagram Graph API. Meta stopped issuing that
product's scopes to new apps after introducing Instagram API with Instagram
Login in 2024 — no dashboard configuration makes those specific scope names
valid again.

**Fix.** If you see this, `app/integrations/instagram_client.py` has
reverted to the old scopes (`instagram_basic` / `instagram_manage_insights`
/ `pages_show_list` / `pages_read_engagement`) somehow — the current code
requests `instagram_business_basic,instagram_business_manage_insights`
instead. Check `git diff` on that file, and confirm `INSTAGRAM_APP_ID`/
`INSTAGRAM_APP_SECRET` in `.env` are the **Instagram** App ID/Secret from
*Instagram → API setup with Instagram login*, not the app's main Facebook
App ID/Secret from *Settings → Basic* — the two are easy to mix up and
Meta doesn't reject the wrong one until the OAuth dialog itself.

### `Error validating verification code` / redirect URI mismatch

**Cause.** `INSTAGRAM_REDIRECT_URI` must match a URI registered in the Meta
app **exactly** — scheme, host, port, path, and trailing slash all count.

**Fix.** Compare `.env` against the redirect URI field on *Instagram → API
setup with Instagram login*. In production it must be `https://`.

### The OAuth dialog loads but nothing happens after approving

**Cause.** In Development mode, only the app's admins/developers/testers can
complete login — and Instagram specifically requires the connecting account
to accept a **tester invite**, separately from being an app admin.

**Fix.** *App roles → Instagram testers* → add the account, then on the
phone: Instagram app → **Settings → Apps and Websites → Tester Invites** →
accept. Skipping this step is the most common reason login silently fails
for the app's own developer.

### `401 The Instagram access token has expired`

**Cause.** Long-lived tokens last about 60 days, or the user revoked access.

**Fix.** Reconnect:

```
DELETE /api/v1/instagram/disconnect
GET    /api/v1/instagram/connect
```

There is no automatic refresh yet — it is on the
[roadmap](README.md#roadmap).

### Insight metrics come back `null`

**Cause.** Most likely a metric name this app requests no longer exists in
the pinned Graph API version. Meta renames and retires metrics between
versions, and these names have **not** been verified against a live Meta app.

**Fix.** Check `app/integrations/instagram_client.py`
(`ACCOUNT_INSIGHT_METRICS`, `IMAGE_INSIGHT_METRICS`,
`VIDEO_INSIGHT_METRICS`) against Meta's documentation for your
`INSTAGRAM_GRAPH_API_VERSION`, and adjust.

Other legitimate causes: brand-new posts have no insights yet, and accounts
below Meta's minimum follower threshold get no demographic-adjacent metrics.

### `completion_rate` is always null

Not a bug. It needs video duration, which the Graph API field set this app
requests does not reliably return, so it is reported as unavailable rather
than estimated.

---

## Gemini / AI endpoints

### `503 AI features are not configured`

```
GOOGLE_API_KEY=...
```

Restart afterwards. Confirm with:

```bash
curl http://localhost:8000/api/v1/ai/health -H "Authorization: Bearer <token>"
```

### `502 The AI provider request failed`

The message includes Gemini's own error. Common causes:

| Message contains | Meaning | Fix |
| --- | --- | --- |
| `API_KEY_INVALID` / `UNAUTHENTICATED` | Bad or revoked key | Reissue at aistudio.google.com/apikey and re-enter it in Settings |
| `RESOURCE_EXHAUSTED`, `limit: 0` | This key has **no** free-tier quota for that model | Switch `GEMINI_MODEL` — quota is granted per model |
| `RESOURCE_EXHAUSTED`, non-zero limit | Rate limit hit | Back off; consider raising `CACHE_TTL_SECONDS` |
| `model not found` | `GEMINI_MODEL` is wrong or unavailable to your account | Use `gemini-2.5-flash` |
| timeout | Slow upstream | Retry; raise proxy `proxy_read_timeout` |

Note that `limit: 0` is different from ordinary rate limiting: it means the
model is not available on your key's tier at all, and waiting will not help.
`gemini-2.0-flash` commonly returns this on newer keys while
`gemini-2.5-flash` works.

### AI answers seem stale

**Cause.** Responses are cached per user for `CACHE_TTL_SECONDS` (default
900). Fetching new media does **not** invalidate that cache.

**Fix.** Wait out the TTL, lower it, or clear the key:

```bash
docker compose exec redis redis-cli --scan --pattern 'insights:*' | xargs -r docker compose exec -T redis redis-cli del
```

### The agent says no account is connected, but one is

**Cause.** The tools query by the *authenticated* user's ID, bound by
closure. If the token belongs to a different user than you expect, the agent
correctly reports nothing.

**Fix.** Confirm identity, then confirm the connection:

```bash
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <token>"
```

```bash
curl http://localhost:8000/api/v1/instagram/profile -H "Authorization: Bearer <token>"
```

---

## Docker

### `failed to connect to the docker API` / `daemon is not running`

Start Docker Desktop and wait for it to report *Engine running*.

```bash
docker info
```

### `port is already allocated`

Another container or a host service holds 5432 or 6379.

```bash
docker ps -a
```

Stop the conflicting container, or remap the port in `docker-compose.yml`
(e.g. `"5433:5432"`) and update `DATABASE_URL` to match.

### Changes to the code are not picked up

**Cause.** The image bakes the source in at build time; it does not
hot-reload.

```bash
docker compose -f docker-compose.prod.yml up -d --build app
```

### `exec /entrypoint.sh: no such file or directory`

**Cause.** `docker/entrypoint.sh` has CRLF line endings — the Linux kernel
then looks for an interpreter named `sh\r`.

**Fix.** Convert to LF and rebuild:

```bash
dos2unix docker/entrypoint.sh
```

Add a `.gitattributes` entry to stop it recurring:

```
*.sh text eol=lf
```

### The app container restarts in a loop

```bash
docker compose -f docker-compose.prod.yml logs app
```

Usually a settings validation error or an unreachable database. The
entrypoint runs migrations first, so a database that is not ready yet fails
the container — the Compose file gates startup on Postgres's healthcheck,
which is why `depends_on: condition: service_healthy` is there.

### `POSTGRES_PASSWORD must be set`

`docker-compose.prod.yml` requires it explicitly rather than defaulting to
something insecure. Set it in `.env`.

---

## Tests

### `ModuleNotFoundError: No module named 'app'`

Run pytest from the repository root, where `pytest.ini` lives:

```bash
cd /path/to/AI-Instalysis && pytest
```

### `ModuleNotFoundError: No module named 'fakeredis'`

```bash
pip install -r requirements-dev.txt
```

### Tests fail with `429`

**Cause.** The rate limiter is process-wide. An autouse fixture resets it
between tests, so this usually means a new test class bypassed the standard
fixtures.

**Fix.** Make sure the test uses the `client` fixture rather than
constructing its own `TestClient`.

### A test hangs for several seconds

**Cause.** Something is reaching a real service — usually a test that
constructs its own Redis client instead of using the `fake_redis` autouse
fixture.

```bash
pytest --durations=10
```

### Tests pass individually but fail together

**Cause.** Leaked state. Tables, the rate limiter, and Redis are all reset by
autouse fixtures; a test that writes to module-level globals without
`monkeypatch` can still leak.

**Fix.** Use `monkeypatch`, which reverts automatically.

---

## Still stuck?

1. Read the logs with the failing request's `X-Request-ID`.
2. Set `LOG_LEVEL=DEBUG` and `LOG_FORMAT=text` for readable local output.
3. Confirm configuration is what you think:
   ```bash
   python -c "from app.core.settings import settings; print(settings.model_dump(exclude={'JWT_SECRET_KEY','TOKEN_ENCRYPTION_KEY','GOOGLE_API_KEY','INSTAGRAM_APP_SECRET','POSTGRES_PASSWORD'}))"
   ```
4. Run `pytest` — if the suite passes, the problem is environmental rather
   than in the code.
