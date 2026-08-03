# Deployment Guide

Production deployment for the AI Instagram Analytics Platform: a serverless
stack built for a single-user, low-traffic app — AWS Lambda (FastAPI via
Mangum) behind an API Gateway HTTP API, Neon (serverless Postgres), DynamoDB
(AI response cache), and CloudFront + S3 for the frontend. No always-on
server, no VPC, no NAT Gateway.

## Stack

| Component     | Role                                                                 |
| -------------- | --------------------------------------------------------------------- |
| Lambda         | The FastAPI API                                                      |
| API Gateway (HTTP API) | Invokes Lambda; see "Why API Gateway, not a Lambda Function URL" below |
| Neon           | PostgreSQL, reachable over the public internet (TLS) — no VPC needed |
| DynamoDB       | AI response cache (`get_or_generate`, 900s TTL by default)           |
| S3 + CloudFront| Static frontend build, served over HTTPS with no owned domain needed |
| CloudFront (2nd origin) | Fronts the API Gateway origin at `/api/*` and `/health*`, same distribution as the frontend |

There is deliberately no background-job worker and no Redis/ElastiCache —
report regeneration is synchronous (same pattern as the full-report export),
and the cache is DynamoDB rather than Redis, both specifically so nothing in
the stack needs a VPC. Giving Lambda VPC access to reach a database would
also require a NAT Gateway for it to still reach the internet (Gemini,
Instagram) — that alone costs more than everything else in this stack
combined, which is why Neon (public-internet Postgres) and DynamoDB (a public
AWS service) were chosen over RDS/ElastiCache.

### Why API Gateway, not a Lambda Function URL

The original design here was CloudFront → Origin Access Control (OAC) →
Lambda Function URL directly, with no API Gateway at all. Two real,
non-obvious blockers ruled it out:

1. **This AWS account has Lambda's "block public access for Function URLs"
   enabled** (the default on accounts created after ~2024). A Function URL
   with `AuthType=NONE` and a resource policy explicitly granting
   `Principal: "*"` still returned `403 AccessDeniedException` for every
   request, direct or through CloudFront — the block overrides the resource
   policy regardless of what it says.
2. **OAC (`AuthType=AWS_IAM`) doesn't work for POST/PUT bodies from ordinary
   browser clients.** Lambda Function URLs reject unsigned payloads; per
   [AWS's own docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html),
   the *viewer* (not CloudFront) must precompute the request body's SHA256
   and send it as `x-amz-content-sha256` for the signature to validate. No
   ordinary web app can reasonably do that from a browser `fetch()` call.
   GET requests worked fine through OAC; every POST (starting with login)
   came back as a CloudFront-masked 403 that silently rendered the SPA's
   `index.html` instead of a real error, via the custom-error-response
   fallback below.

An API Gateway HTTP API in front of Lambda sidesteps both: API Gateway
invokes Lambda via the internal Lambda Invoke API (its own execution
permissions, not a signed HTTPS call), so there's no payload-hash
requirement and no Function-URL-specific public-access block to fight.
CloudFront talks to API Gateway as a normal custom origin, authenticated by
a shared-secret header (see below) rather than OAC.

**The trade-off**: HTTP API Gateway has a hard 30-second integration
timeout that cannot be raised (unlike a Function URL, which supports up to
15 minutes). `GEMINI_TIMEOUT_SECONDS` is set to `20` in this deployment
(rather than the code's local-dev default of `45`).

That value replaced an initial `8`, which turned out to be broken rather
than just tight: `langchain_google_genai`'s client hard-rejects any deadline
under 10 seconds with an immediate 400 `INVALID_ARGUMENT` ("Manually set
deadline 8s is too short. Minimum allowed deadline is 10s") — so at `8`,
every single AI call failed instantly regardless of Gemini's actual
latency, not just the occasional slow one. `app/services/ai_generation.py`
now clamps `timeout=max(GEMINI_TIMEOUT_SECONDS, 10)` in `build_llm` as a
fail-safe against this exact misconfiguration recurring, but the deployed
env var should still be a sane value on its own, hence `20`.

**Known follow-up risk**: `20` gives chat/insights/recommendations (each a
single Gemini call) comfortable headroom, but the full-report export runs
3 *sequential* Gemini calls (`app/services/export_service.py`, one each for
insights/recommendations/report) with no per-call override — worst case
`3 × 20s = 60s`, well past API Gateway's 30s cap. The 3 calls have no data
dependency on each other (each builds its own context straight from
analytics), so the structurally sound fix is running them concurrently
(e.g. a thread pool, since they're blocking calls) so wall time is bounded
by the slowest single call instead of their sum — not done here, flagged
for whoever picks up the export endpoint next. Until then, if export
timeouts start showing up in practice, the fallback is the same one noted
below: front Lambda with an Application Load Balancer instead (no timeout
ceiling this low, no payload-hash requirement either) — priced with an
hourly base charge, unlike API Gateway's pay-per-request model, so it's a
deliberate cost/latency trade-off, not a drop-in swap.

## 1. Required environment variables

Set these as Lambda environment variables (encrypted at rest with the
default AWS-managed KMS key — no cost, no extra setup):

| Variable                   | Notes                                                                 |
| --------------------------- | ---------------------------------------------------------------------- |
| `ENVIRONMENT`                | Set to `production`. Triggers stricter startup validation (see below). |
| `DEBUG`                      | Must be `false` in production - startup fails otherwise.               |
| `JWT_SECRET_KEY`             | Must be ≥32 random characters in production - startup fails otherwise. |
| `TOKEN_ENCRYPTION_KEY`       | A Fernet key (see "Rotating secrets" below).                           |
| `DATABASE_URL`               | Neon's pooled connection string, `sslmode=require`.                    |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | Set small (e.g. `1` / `0`) - each Lambda invocation only ever needs one connection; Neon's own pooler absorbs the rest. |
| `DYNAMODB_CACHE_TABLE`       | Defaults to `instalysis-cache`; only set if you named it differently.  |
| `DYNAMODB_ENDPOINT_URL`      | **Leave unset** in production so boto3 talks to the real AWS endpoint. |
| `CORS_ALLOWED_ORIGINS`       | Comma-separated real frontend origin(s) - the CloudFront domain. Must not be `*` in production. |
| `GOOGLE_API_KEY`             | Required for `/ai/*`, `/insights`, `/recommendations`, `/reports/*`, `/export/*` to function - those endpoints return 503 without it, everything else works fine. |
| `GEMINI_TIMEOUT_SECONDS`     | Set to `20` in this deployment (not the code default of `45`) - see "Why API Gateway, not a Lambda Function URL" above for why, including the known export-endpoint risk at this value. Values under 10 are clamped up in code (`app/services/ai_generation.py`) since Gemini's own client rejects a deadline that low outright. |
| `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` / `INSTAGRAM_REDIRECT_URI` | Required for `/instagram/connect` - returns 503 without them. |
| `CLOUDFRONT_ORIGIN_VERIFY_SECRET` | A random secret CloudFront attaches to every request as a custom origin header; `OriginVerifyMiddleware` rejects anything reaching Lambda without it, since the API Gateway origin has no other access restriction. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |

`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` exist as
settings fields purely for local dev against DynamoDB Local (see below) -
leave them unset in the Lambda environment; the function's execution role
supplies real credentials automatically.

Startup will refuse to boot with a clear error if `ENVIRONMENT=production`
and `DEBUG=true`, `JWT_SECRET_KEY` is too short, or `CORS_ALLOWED_ORIGINS`
contains `*` - this is deliberate (see `app/core/settings.py`).

Everything else has a documented default in
[`app/core/settings.py`](app/core/settings.py).

## 2. Database — Neon

1. Create a Neon project and database (free tier: 0.5GB storage,
   autosuspend when idle).
2. Copy its pooled connection string into `DATABASE_URL`.
3. Run migrations from a local machine or a CI step (not from inside
   Lambda):
   ```bash
   DATABASE_URL="<neon connection string>" alembic upgrade head
   ```
4. Watch the 0.5GB free-tier cap as data grows; Neon's paid tier (~$19/month)
   is the upgrade path if it's ever outgrown.
5. Create the one app account - there is no self-service registration
   endpoint (see the comment at the top of
   `app/api/v1/endpoints/auth.py`):
   ```bash
   DATABASE_URL="<neon connection string>" python -m scripts.create_user \
     --username you --full-name "Your Name" --email you@example.com
   ```

## 3. Cache — DynamoDB

Create the table (idempotent, safe to re-run):

```bash
python -m scripts.create_cache_table
```

This creates a table with `cache_key` as its partition key and enables
native TTL on the `expires_at` attribute. DynamoDB's TTL deletion is
best-effort (can lag up to 48h), so the app also checks expiry itself on
every read (`app/utils/cache.py`) - the native TTL is purely a storage-cost
cleanup, not something the app's correctness depends on.

For local development, `docker-compose.yml` runs DynamoDB Local instead:

```bash
docker compose up -d postgres dynamodb-local
DYNAMODB_ENDPOINT_URL=http://localhost:8100 python -m scripts.create_cache_table
```

## 4. Build and deploy the Lambda function

```bash
docker build -f Dockerfile.lambda -t instalysis-api .
```

Push to ECR and create/update the function:

```bash
aws ecr create-repository --repository-name instalysis-api   # first time only
docker tag instalysis-api:latest <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest

aws lambda update-function-code \
  --function-name instalysis-api \
  --image-uri <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest
```

Function configuration:

- **No VPC.** Neon (public internet) and DynamoDB (public AWS service) are
  both reachable without one - attaching a VPC here would require a NAT
  Gateway just for Gemini/Instagram calls to keep working, at a cost that
  dwarfs the rest of this stack.
- **Memory**: start at 1024MB. The langchain/pydantic/sqlalchemy import
  chain is heavy enough that more memory often nets out cost-neutral or
  cheaper via faster execution; tune after real usage.
- **Timeout**: 150s. Generous relative to what actually runs (API Gateway's
  own 30s cap is the real ceiling - see above), but harmless to leave high.
- **No Function URL.** Put an API Gateway HTTP API in front instead (see
  "Why API Gateway, not a Lambda Function URL" above):
  ```bash
  aws apigatewayv2 create-api --name instalysis-api-gw --protocol-type HTTP \
    --target arn:aws:lambda:<region>:<account-id>:function:instalysis-api
  # "quick create" above auto-creates a $default route + AWS_PROXY
  # integration + auto-deployed $default stage, but does NOT grant Lambda
  # invoke permission scoped correctly - add it explicitly:
  aws lambda add-permission --function-name instalysis-api \
    --statement-id AllowAPIGatewayInvoke --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:<region>:<account-id>:<api-id>/*"
  ```
- **IAM role**: basic Lambda execution (CloudWatch Logs) plus
  read/write on the DynamoDB cache table only. Nothing else.

Cold starts (~1-3s) are an accepted trade-off for near-zero idle cost - no
provisioned concurrency, which would cost money for a single low-traffic
user and defeat the reason for choosing serverless.

## 5. Frontend — S3 + CloudFront

1. `npm run build` in `frontend/`, upload `dist/` to a private S3 bucket.
2. CloudFront distribution with **two** origins:
   - Default → the S3 bucket, via Origin Access Control (OAC still works
     fine here - S3 has no payload-hash requirement, this part of the
     original design was always correct).
   - The API Gateway domain (`<api-id>.execute-api.<region>.amazonaws.com`),
     as a plain custom origin - **no OAC**. Authenticate it instead with a
     custom origin header carrying `CLOUDFRONT_ORIGIN_VERIFY_SECRET`
     (`CustomHeaders` on the origin config); `OriginVerifyMiddleware`
     rejects any request that arrives without the matching header, which is
     what stops this origin being reachable by anyone who finds the raw API
     Gateway URL.
   - Two behaviors point at this origin: `/api/*` and `/health*`. **Easy to
     miss on the second**: the app's health endpoints (`/health`,
     `/health/live`, `/health/ready`) live at the root, not under
     `/api/v1` (see `app/main.py`), so they don't match `/api/*`. Without
     this second behavior they silently fall through to the S3 default
     behavior, which - because of the SPA fallback below - returns a 200
     with the frontend's `index.html` instead of a real health check,
     masking actual backend failures rather than surfacing them.
3. Set the API Gateway behaviors' cache policy to **CachingDisabled** (every
   response here is per-user/authenticated, never shareable) and origin
   request policy to **AllViewerExceptHostHeader** (forwards the
   `Authorization` header and everything else the API needs, except `Host`,
   which would otherwise not match what Lambda/API Gateway expect). Origin
   response timeout can stay at CloudFront's default - API Gateway's own 30s
   integration timeout is always the binding constraint underneath it.
   CloudFront layer if this isn't raised. Test the export page's slowest
   path (cold cache, all 3 AI sections generating) against the deployed URL
   before considering a deploy done - request a quota increase to 180s if
   60s isn't enough in practice.
4. Point the frontend's `VITE_API_BASE_URL` at the CloudFront domain **root**
   (e.g. `https://xxxx.cloudfront.net`, no `/api` suffix) - `src/api/client.ts`
   appends `/api/v1` itself. One origin for both frontend and API, no CORS
   complications.
5. No domain required to start - CloudFront's default `*.cloudfront.net`
   domain works immediately with a free, automatically-issued certificate.
   When a custom domain is added later: request an ACM cert in `us-east-1`,
   add the domain as a CloudFront alternate domain name, point DNS at the
   distribution. No backend changes needed either way.

## 6. Health checks

Three endpoints, unauthenticated and unversioned (not under `/api/v1`):

- **`GET /health/live`** - is the process alive? No dependency checks.
- **`GET /health/ready`** - can this instance serve traffic? Checks Neon and
  the DynamoDB cache table, returns 503 if either is unreachable.
- **`GET /health`** - general summary (app name/version/environment/uptime
  plus the same dependency checks) for humans and dashboards.

## 7. Caching

`/insights`, `/recommendations`, `/reports/weekly`, `/reports/monthly`, and
`/export/full-report` cache their (LLM-generated) response in DynamoDB for
`CACHE_TTL_SECONDS` (default 900s / 15 minutes), keyed per user. If DynamoDB
is unreachable, caching fails open - the endpoint just generates fresh every
time rather than erroring. Lower `CACHE_TTL_SECONDS` for fresher data at the
cost of more Gemini API calls, or raise it to cut cost/latency further.

## 8. Rate limiting

Every endpoint has a default limit (`RATE_LIMIT_DEFAULT`, 100/minute per IP
by default); auth, AI-backed, and export endpoints have their own stricter
limits (`RATE_LIMIT_AUTH`, `RATE_LIMIT_STRICT`, `RATE_LIMIT_EXPORT`).
Limiting is **in-memory per process**, not centrally stored - a cold Lambda
instance starts with empty buckets, so limits don't coordinate perfectly
across concurrent invocations. An accepted, low-risk limitation for a single
user; Gemini's own API-side quota is the real backstop against runaway spend.

## 9. Logging and monitoring

- **Logs**: structured JSON on stdout, captured automatically by CloudWatch
  Logs for the Lambda function. Set a log retention policy (14-30 days) on
  the function's log group so logs don't accumulate unbounded cost.
- **Metrics**: Lambda's own CloudWatch metrics (invocations, duration,
  errors, throttles) cover the operational basics without extra setup. The
  app also exposes Prometheus-format metrics at `GET /metrics` if a scraper
  is ever added.
- **Request tracing**: every response carries an `X-Request-ID` header, also
  present in that request's log line.
- **Errors**: any unhandled exception is logged server-side with a full
  stack trace and returns a generic `{"detail": "..."}` to the client - no
  internal details ever leak in the response body.

## 10. Rotating secrets

- **`JWT_SECRET_KEY`**: rotating invalidates every existing access token -
  all users get logged out. Update the Lambda environment variable and
  deploy; not disruptive to schedule during a maintenance window.
- **`TOKEN_ENCRYPTION_KEY`**: encrypts stored Instagram access tokens.
  Rotating it makes existing stored tokens undecryptable - affected users
  will need to reconnect their Instagram account via `/instagram/connect`.
  Generate a new one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

## 11. Backups

The only stateful component is Neon (Postgres). DynamoDB holds only cache
data, which is safe to lose entirely - it just regenerates on the next
request.

Neon takes automatic point-in-time backups on its free tier (retention
varies by plan - check the current terms in the Neon console). For an
additional local copy:

```bash
pg_dump "$DATABASE_URL" -Fc > backup-$(date +%F).dump
```

### What to know before you rely on this

- **Test the restore.** An untested backup is a hypothesis. Restore into a
  scratch database periodically and confirm the row counts.
- **`TOKEN_ENCRYPTION_KEY` is part of your backup.** Stored Instagram tokens
  are encrypted with it; restoring a dump without the matching key leaves
  every connected account undecryptable and every user needing to reconnect.
  Back the key up separately, in a secrets manager - never alongside the dump.

## 12. CI/CD pipeline

`.github/workflows/deploy-backend.yml` and `deploy-frontend.yml` handle
deployment automatically - the manual steps in the next section are the
fallback path (a broken pipeline, a one-off hotfix), not the normal one.

Both workflows follow the same shape:

1. **Every push, on any branch, and every pull request** runs build +
   test: the backend installs `requirements-dev.txt`, runs the full
   `pytest` suite, then builds the Lambda image (`Dockerfile.lambda`) to
   confirm it still builds; the frontend runs `npm run build` (which
   includes `tsc -b`, so a type error fails the run) and `npm run lint`
   (oxlint). Nothing is deployed at this stage - it's purely a gate, so a
   broken feature branch or PR shows red before it can reach master.
2. **Only a direct push to `master`** (this repo's default branch -
   confirm with `git remote show origin` if that's ever unclear)
   additionally deploys: the backend pushes the already-built image to ECR
   and updates the Lambda function; the frontend syncs its build output to
   S3 and invalidates CloudFront. A PR *from* a branch into master, or a
   push to any other branch, never touches AWS - both workflows gate every
   AWS-touching step behind `if: env.IS_DEPLOY == 'true'`, computed from
   `github.ref` and `github.event_name`.

There is currently no frontend test suite (no vitest/jest) - `tsc -b` and
oxlint are what "tested" means for the frontend today; see
`frontend/package.json`'s `lint`/`build` scripts.

Both workflows can also be triggered manually from the Actions tab
(`workflow_dispatch`), which still runs on whatever branch is selected and
still only deploys if that's `master`.

## 13. Updating and rolling back

### Update

Normally this is just `git push` to `master` and the pipeline above
handles the rest. The manual path below is the fallback:

```bash
git pull
docker build -f Dockerfile.lambda -t instalysis-api .
docker tag instalysis-api:latest <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest
aws lambda update-function-code --function-name instalysis-api \
  --image-uri <account-id>.dkr.ecr.<region>.amazonaws.com/instalysis-api:latest
```

If the release includes a migration, run it against Neon **before**
deploying the new image:

```bash
DATABASE_URL="<neon connection string>" alembic upgrade head
```

Confirm afterwards:

```bash
curl -fsS https://<cloudfront-domain>/health
```

### Rolling back

Lambda keeps prior image-backed versions - point the function (or an alias)
back at the previous image URI to roll back code instantly, no rebuild
needed. If the release included a migration, roll the **schema** back first
- the old code will not understand the new schema:

```bash
DATABASE_URL="<neon connection string>" alembic downgrade -1
```

> **A downgrade that drops a column destroys its data.** If the migration you
> are reversing added and populated a column, take a backup first. Prefer
> forward-fixing (a new migration that corrects the problem) over downgrading
> in production wherever possible.

### Release checklist

- [ ] Backup taken and its restore verified recently
- [ ] Reviewed the migration SQL: `alembic upgrade head --sql`
- [ ] `pytest` green on the release commit
- [ ] `/health` returns 200 after deploy
- [ ] CloudWatch Logs checked for errors in the first few minutes

## 14. Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Covers unit logic, services against a real (in-memory SQLite) database, and
every endpoint over HTTP. Nothing external is contacted - no database
server, no AWS, no Meta, no Gemini (a moto-mocked DynamoDB and a fake LLM
stand in) - so the suite is safe to run anywhere and costs nothing. Run a
single layer with `pytest -m unit`, `-m integration`, or `-m api`.

## 15. Pre-launch checklist

- [ ] `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Real `JWT_SECRET_KEY` (≥32 chars, generated fresh — **not** the sample value from `.env.example`, which is public)
- [ ] Real `TOKEN_ENCRYPTION_KEY` (generated fresh — **not** the public sample value)
- [ ] `TOKEN_ENCRYPTION_KEY` stored in a secrets manager, separately from database backups
- [ ] `CORS_ALLOWED_ORIGINS` set to the CloudFront domain, not `*`
- [ ] `GOOGLE_API_KEY` and Instagram app credentials set, if those features are needed
- [ ] Lambda function has no VPC configuration
- [ ] Lambda execution role scoped to CloudWatch Logs + the one DynamoDB table only
- [ ] `CLOUDFRONT_ORIGIN_VERIFY_SECRET` set on Lambda and matches the CloudFront origin's custom header exactly - the API Gateway origin has no other access restriction
- [ ] `GEMINI_TIMEOUT_SECONDS=20` set (not the code default of 45, and not below 10 - Gemini's client rejects a lower deadline outright)
- [ ] `VITE_API_BASE_URL` set to the CloudFront domain **root** (no `/api` suffix) at frontend build time - `frontend/.env.production` holds this; verify it's picked up (`grep VITE_API_BASE_URL frontend/dist/assets/*.js` should show the CloudFront domain, never `localhost`) before every `npm run build` that gets deployed
- [ ] Known risk, not yet fixed: the full-report export's 3 sequential Gemini calls can exceed API Gateway's 30s cap at `GEMINI_TIMEOUT_SECONDS=20` (worst case `3 × 20s = 60s`) - see "Why API Gateway, not a Lambda Function URL" above
- [ ] `alembic upgrade head` run against Neon before the first deploy
- [ ] DynamoDB cache table created with TTL enabled on `expires_at`
- [ ] `/docs` and `/redoc` are disabled (automatic when `ENVIRONMENT=production`)
