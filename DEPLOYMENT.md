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
| `OPENAI_API_KEY`             | Required for `/ai/*`, `/insights`, `/recommendations`, `/reports/*` to function - those endpoints return 503 without it, everything else works fine. |
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
more OpenAI calls, or raise it to cut cost/latency further.

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

## 10. Pre-launch checklist

- [ ] `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Real `JWT_SECRET_KEY` (≥32 chars, generated fresh, not the dev value)
- [ ] Real `TOKEN_ENCRYPTION_KEY` (generated fresh, not the dev value)
- [ ] `CORS_ALLOWED_ORIGINS` set to your actual frontend origin(s), not `*`
- [ ] `OPENAI_API_KEY` and Instagram app credentials set, if those features are needed
- [ ] `POSTGRES_PASSWORD` changed from any default
- [ ] `.env` is not committed and is only readable by the deploying process
- [ ] `docker compose -f docker-compose.prod.yml up -d --build` completes and `GET /health` returns 200
- [ ] `/docs` and `/redoc` are disabled (automatic when `ENVIRONMENT=production`)
