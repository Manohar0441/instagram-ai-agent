# Deployment Guide

Production deployment for the AI Instagram Analytics Platform: a FastAPI app,
an RQ background worker, PostgreSQL, and Redis.

## Stack

| Service    | Purpose                                                              |
| ---------- | --------------------------------------------------------------------- |
| `app`      | The FastAPI API, served by Uvicorn (4 workers by default)             |
| `worker`   | RQ background worker - processes queued jobs (e.g. report generation) |
| `postgres` | Primary datastore                                                     |
| `redis`    | Backs the background job queue and the AI-response cache              |

`app` and `worker` are built from the same [Dockerfile](Dockerfile) and run
the same image with a different command - `worker` overrides the default
`CMD` to run `python -m app.worker` instead of Uvicorn.

## 1. Required environment variables

Copy your local `.env` (never commit it) and ensure at minimum:

| Variable                   | Notes                                                                 |
| --------------------------- | ---------------------------------------------------------------------- |
| `ENVIRONMENT`                | Set to `production`. Triggers stricter startup validation (see below). |
| `DEBUG`                      | Must be `false` in production - startup fails otherwise.               |
| `JWT_SECRET_KEY`             | Must be ≥32 random characters in production - startup fails otherwise. |
| `TOKEN_ENCRYPTION_KEY`       | A Fernet key (see "Rotating secrets" below).                           |
| `DATABASE_URL`               | Used for local/non-Docker runs; the Compose file overrides this for `app`/`worker` to point at the `postgres` container. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Must match the credentials embedded in `DATABASE_URL`. Used by `docker-compose.prod.yml` to initialize Postgres and build the in-network `DATABASE_URL`. |
| `REDIS_URL`                  | Same override behavior as `DATABASE_URL`.                              |
| `CORS_ALLOWED_ORIGINS`       | Comma-separated real frontend origin(s). Must not be `*` in production. |
| `GOOGLE_API_KEY`             | Required for `/ai/*`, `/insights`, `/recommendations`, `/reports/*` to function - those endpoints return 503 without it, everything else works fine. |
| `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` / `INSTAGRAM_REDIRECT_URI` | Required for `/instagram/connect` - returns 503 without them. |

Startup will refuse to boot with a clear error if `ENVIRONMENT=production`
and `DEBUG=true`, `JWT_SECRET_KEY` is too short, or `CORS_ALLOWED_ORIGINS`
contains `*` - this is deliberate (see `app/core/settings.py`).

Everything else in `.env` has a documented default in
[`app/core/settings.py`](app/core/settings.py).

## 2. Build and run

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This starts Postgres and Redis, waits for both to report healthy, then
starts `app` and `worker`. The app container's entrypoint
([`docker/entrypoint.sh`](docker/entrypoint.sh)) runs `alembic upgrade head`
before starting the server - migrations are automatic, not a manual step.

Check everything is up:

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

## 3. Health checks

Three endpoints, unauthenticated and unversioned (not under `/api/v1`), for
infrastructure to probe:

- **`GET /health/live`** - is the process alive? No dependency checks.
  Failing this means restart the container.
- **`GET /health/ready`** - can this instance serve traffic? Checks
  Postgres and Redis connectivity, returns 503 if either is unreachable.
  Failing this means stop routing traffic here, but don't necessarily
  restart.
- **`GET /health`** - general summary (app name/version/environment/uptime
  plus the same dependency checks) for humans and dashboards.

The Docker image's own `HEALTHCHECK` uses `/health/live`.

## 4. Background jobs

Report generation can run synchronously (`GET /reports/weekly`,
`GET /reports/monthly`) or as a background job:

```
POST /api/v1/jobs/reports/{weekly|monthly}  -> 202 {"job_id": "..."}
GET  /api/v1/jobs/{job_id}                  -> {"status": "queued|started|finished|failed", "result": {...}}
```

Jobs are tagged with the requesting user's ID; `GET /jobs/{job_id}` 404s if
the job doesn't belong to the caller. Scale worker throughput by running
more `worker` replicas:

```bash
docker compose -f docker-compose.prod.yml up -d --scale worker=3
```

## 5. Caching

`/insights`, `/recommendations`, `/reports/weekly`, and `/reports/monthly`
cache their (LLM-generated) response in Redis for `CACHE_TTL_SECONDS`
(default 900s / 15 minutes), keyed per user. If Redis is unreachable,
caching fails open - the endpoint just generates fresh every time rather
than erroring. Lower `CACHE_TTL_SECONDS` for fresher data at the cost of
more Gemini API calls, or raise it to cut cost/latency further.

## 6. Rate limiting

Every endpoint has a default limit (`RATE_LIMIT_DEFAULT`, 100/minute per IP
by default); auth endpoints (`RATE_LIMIT_AUTH`) and AI-backed endpoints
(`RATE_LIMIT_STRICT`) have their own stricter limits. Limiting is
**in-memory per process**, not Redis-backed - this is deliberate (see the
comment in `app/core/rate_limit.py`): the rate-limiting library used here
does not fail open when its storage backend is unreachable, so a
Redis-backed limiter would turn a Redis blip into a total outage. The
trade-off is that limits aren't shared across multiple `app` replicas -
each replica enforces its own bucket. Acceptable for abuse protection at
moderate scale; revisit if you need cross-replica consistency.

## 7. Logging and monitoring

- **Logs**: structured JSON on stdout (one object per line - timestamp,
  level, logger, message, plus any extra fields like `request_id` or
  `duration_ms`). Set `LOG_FORMAT=text` for human-readable output locally.
  `LOG_LEVEL` controls verbosity (default `INFO`).
- **Metrics**: Prometheus-format metrics at `GET /metrics` (request counts,
  latency histograms, status codes), powered by
  `prometheus-fastapi-instrumentator`. Point a Prometheus scrape config at
  `app:8000/metrics`.
- **Request tracing**: every response carries an `X-Request-ID` header,
  also present in that request's log line, for correlating a client-side
  error report with server logs.
- **Errors**: any unhandled exception is logged server-side with a full
  stack trace and returns a generic `{"detail": "..."}` to the client - no
  internal details ever leak in the response body.

## 8. Scaling the app

Uvicorn runs with 4 workers by default (`Dockerfile` `CMD`). For more
throughput than one container can provide, run multiple `app` replicas
behind a load balancer:

```bash
docker compose -f docker-compose.prod.yml up -d --scale app=3
```

(Drop the fixed `ports:` mapping and put a reverse proxy/load balancer in
front if you do this, since multiple containers can't all bind host port
8000.)

## 9. Rotating secrets

- **`JWT_SECRET_KEY`**: rotating invalidates every existing access token -
  all users get logged out. Not disruptive to schedule during a maintenance
  window.
- **`TOKEN_ENCRYPTION_KEY`**: encrypts stored Instagram access tokens.
  Rotating it makes existing stored tokens undecryptable - affected users
  will need to reconnect their Instagram account via `/instagram/connect`.
  Generate a new one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

## 10. Reverse proxy and TLS

The app speaks plain HTTP on port 8000 and does **not** terminate TLS. Put a
reverse proxy in front of it in production. Two things it must do:

1. **Terminate TLS**, so traffic between client and proxy is encrypted.
2. **Forward the real client IP**, otherwise rate limiting sees every request
   as coming from the proxy and buckets all users together.

### Nginx

```nginx
upstream instagram_ai {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.example.com;
    # Everything except the ACME challenge goes to HTTPS.
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # The app sets its own security headers; HSTS is repeated here so it is
    # present even on responses the proxy generates itself (e.g. 502s).
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    client_max_body_size 1m;

    location / {
        proxy_pass http://instagram_ai;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # AI endpoints wait on a Gemini round trip; the default 60s is tight.
        proxy_read_timeout 120s;
    }

    # Do not expose metrics publicly - scrape them from inside the network.
    location /metrics { deny all; }
}
```

### Caddy

Caddy obtains and renews certificates automatically:

```caddy
api.example.com {
    reverse_proxy 127.0.0.1:8000
    @metrics path /metrics
    respond @metrics 403
}
```

### Making the app trust the proxy

Uvicorn ignores `X-Forwarded-*` headers unless told which proxies to trust.
Without this, `request.client.host` is the proxy's address and per-IP rate
limiting is effectively global.

Update the `CMD` in the [Dockerfile](Dockerfile) (or the compose `command:`):

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 \
        --proxy-headers --forwarded-allow-ips="*"
```

Use `--forwarded-allow-ips="*"` **only** when the app is unreachable except
through your proxy — otherwise a client can spoof its own IP. If the app port
is exposed, list the proxy's address explicitly instead.

Also set `CORS_ALLOWED_ORIGINS` to your real frontend origin(s), and remove
the `ports:` mapping from the `app` service in `docker-compose.prod.yml` so
only the proxy can reach it.

### TLS checklist

- [ ] TLS 1.2+ only
- [ ] Certificate auto-renewal running (certbot timer, or Caddy)
- [ ] HTTP redirects to HTTPS
- [ ] `--proxy-headers` enabled and the trusted-proxy list scoped correctly
- [ ] `/metrics` not publicly reachable
- [ ] `INSTAGRAM_REDIRECT_URI` uses `https://` and matches the Meta app config exactly

---

## 11. Backups

The only stateful component is PostgreSQL. Redis holds cache and queue data,
both of which are safe to lose — the cache regenerates and queued jobs can be
re-submitted.

### Backing up

```bash
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -Fc instagram_ai > backup-$(date +%F).dump
```

`-Fc` produces a compressed custom-format dump, which restores faster and
allows selective restore.

A minimal nightly cron entry with 14-day retention:

```bash
0 3 * * * cd /srv/AI-Instalysis && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -Fc instagram_ai > /backups/instagram_ai-$(date +\%F).dump && find /backups -name 'instagram_ai-*.dump' -mtime +14 -delete
```

### Restoring

```bash
docker compose -f docker-compose.prod.yml stop app worker
```

```bash
docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U postgres -d instagram_ai --clean --if-exists < backup-2026-07-31.dump
```

```bash
docker compose -f docker-compose.prod.yml start app worker
```

### What to know before you rely on this

- **Test the restore.** An untested backup is a hypothesis. Restore into a
  scratch database periodically and confirm the row counts.
- **`TOKEN_ENCRYPTION_KEY` is part of your backup.** Stored Instagram tokens
  are encrypted with it; restoring a dump without the matching key leaves
  every connected account undecryptable and every user needing to reconnect.
  Back the key up separately, in a secrets manager — never alongside the dump.
- **Back up `.env` too**, to the same secrets manager.

---

## 12. Updating and rolling back

### Update

```bash
git pull
```

```bash
docker compose -f docker-compose.prod.yml build
```

```bash
docker compose -f docker-compose.prod.yml up -d
```

Migrations run automatically on app startup. Confirm afterwards:

```bash
curl -fsS https://api.example.com/health
```

For a zero-downtime update you need two app replicas behind the proxy,
restarted one at a time — Compose alone cannot do this; use `docker service
update` (Swarm) or a Kubernetes rolling update.

### Rolling back

Roll back **code** by checking out the previous tag and rebuilding:

```bash
git checkout <previous-tag> && docker compose -f docker-compose.prod.yml up -d --build
```

If the release included a migration, roll the **schema** back first — the old
code will not understand the new schema:

```bash
docker compose -f docker-compose.prod.yml exec app alembic downgrade -1
```

Check what you are about to undo:

```bash
docker compose -f docker-compose.prod.yml exec app alembic current
```

> **A downgrade that drops a column destroys its data.** If the migration you
> are reversing added and populated a column, take a backup first. Prefer
> forward-fixing (a new migration that corrects the problem) over downgrading
> in production wherever possible.

### Release checklist

- [ ] Backup taken and its restore verified recently
- [ ] Reviewed the migration SQL: `alembic upgrade head --sql`
- [ ] `pytest` green on the release commit
- [ ] Tagged, so rollback has a target
- [ ] `/health` returns 200 after deploy
- [ ] Logs checked for errors in the first few minutes

---

## 13. Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

339 tests covering unit logic, services against a real database, and every
endpoint over HTTP. Nothing external is contacted — no database server, no
Redis, no Meta, no Gemini — so the suite is safe to run anywhere and costs
nothing. Run a single layer with `pytest -m unit`, `-m integration`, or
`-m api`. See [CODE_REVIEW.md](CODE_REVIEW.md) for what is and isn't covered.

## 14. Upgrading an existing deployment

Two behavior changes affect a running deployment:

- **All existing access tokens are rejected once**, because access tokens now
  carry a `type` claim that older tokens lack. Signed-in users are logged out
  and simply sign in again; tokens are 30-minute-lived, so nothing else is
  needed. This closes a flaw where an Instagram OAuth *state* token — which
  travels in a URL and so reaches browser history and `facebook.com` via the
  `Referer` header — was accepted as an API credential.
- **`GET /api/v1/users` and `POST /api/v1/users` no longer exist**, and
  `GET /api/v1/users/{id}` now requires authentication and returns only the
  caller's own record. The list endpoint exposed every user's email address
  with no authentication at all; the POST duplicated `/auth/register` while
  bypassing its brute-force rate limit. Any client calling those endpoints
  must move to `/auth/register` and `/auth/me`.

## 15. Pre-launch checklist

- [ ] `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Real `JWT_SECRET_KEY` (≥32 chars, generated fresh — **not** the sample value from `.env.example`, which is public)
- [ ] Real `TOKEN_ENCRYPTION_KEY` (generated fresh — **not** the public sample value)
- [ ] `TOKEN_ENCRYPTION_KEY` stored in a secrets manager, separately from database backups
- [ ] `CORS_ALLOWED_ORIGINS` set to your actual frontend origin(s), not `*`
- [ ] `GOOGLE_API_KEY` and Instagram app credentials set, if those features are needed
- [ ] `POSTGRES_PASSWORD` changed from any default
- [ ] `.env` is not committed and is only readable by the deploying process
- [ ] `docker compose -f docker-compose.prod.yml up -d --build` completes and `GET /health` returns 200
- [ ] `/docs` and `/redoc` are disabled (automatic when `ENVIRONMENT=production`)
