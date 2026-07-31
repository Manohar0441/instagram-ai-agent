# Local Development Setup

Get the platform running locally. The fastest path is
[Quick start](#quick-start); the rest of the document explains each step and
covers running without Docker.

> **You do not need Meta or OpenAI credentials to run this.** Without them
> the Instagram and AI endpoints return a clear `503`; everything else —
> registration, login, the database, the docs — works normally.

---

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| **Python** | 3.12+ | 3.10 works, but the Docker image targets 3.12 |
| **Git** | any recent | |
| **Docker Desktop** | 4.x+ | Easiest way to get Postgres and Redis. Optional — see [Running without Docker](#running-without-docker) |
| **Docker Compose** | v2 | Bundled with Docker Desktop; use `docker compose`, not `docker-compose` |
| **PostgreSQL** | 16 | Only if you are not using Docker |
| **Redis** | 7 | Only if you are not using Docker |

Verify:

```bash
python --version && git --version && docker --version && docker compose version
```

---

## Quick start

Five commands, assuming Docker is running.

```bash
git clone <your-repo-url> && cd AI-Instalysis
```

```bash
cp .env.example .env
```

```bash
docker compose up -d
```

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

```bash
alembic upgrade head && uvicorn app.main:app --reload
```

Then open **http://localhost:8000/docs**.

> On macOS/Linux the activate command is `source .venv/bin/activate`.

Before doing anything real, generate proper secrets — see
[step 3](#3-configure-environment-variables).

---

## Installation, step by step

### 1. Clone and enter the repository

```bash
git clone <your-repo-url>
```

```bash
cd AI-Instalysis
```

### 2. Create a virtual environment

**Windows (PowerShell)**

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python -m venv .venv && source .venv/bin/activate
```

Your prompt should now be prefixed with `(.venv)`.

Install dependencies:

```bash
pip install -r requirements.txt
```

For the test suite as well:

```bash
pip install -r requirements-dev.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

`.env` is gitignored. **The copy works as-is for local development** — it
ships with a working `JWT_SECRET_KEY` and `TOKEN_ENCRYPTION_KEY` so you can
start immediately.

> ⚠️ Those two values are **committed to source control and therefore
> public**. They are fine for local work and useless for anything else.
> Before deploying, generate real ones:
>
> ```bash
> python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
> ```
>
> ```bash
> python -c "from cryptography.fernet import Fernet; print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
> ```
>
> Setting `ENVIRONMENT=production` while either sample value is still in
> place makes the app **refuse to start**, so this cannot be forgotten
> silently.

The full variable reference — what is required, what is optional, and what
each does — is in [`.env.example`](.env.example) itself.

Optional integrations:

<details>
<summary><strong>Instagram / Meta credentials</strong></summary>

Needed only for `/instagram/*`.

1. Create an app at <https://developers.facebook.com/apps> (type: **Business**).
2. Add the **Facebook Login for Business** product.
3. Under *Valid OAuth Redirect URIs*, add exactly:
   `http://localhost:8000/api/v1/instagram/callback`
4. Copy the App ID and App Secret into `.env`:

```
INSTAGRAM_APP_ID=your-app-id
INSTAGRAM_APP_SECRET=your-app-secret
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/v1/instagram/callback
```

You also need an Instagram **Business or Creator** account linked to a
Facebook Page — personal Instagram accounts cannot be connected, which is a
Meta platform restriction rather than a limitation of this app.
</details>

<details>
<summary><strong>OpenAI credentials</strong></summary>

Needed only for `/ai/*`, `/insights`, `/recommendations`, `/reports/*`.

Create a key at <https://platform.openai.com/api-keys>:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

`gpt-4o-mini` is the default because it is inexpensive; any tool-calling
OpenAI model works.
</details>

### 4. Start PostgreSQL and Redis

```bash
docker compose up -d
```

This starts only the two datastores — the app itself runs on your host with
hot reload, which is nicer to develop against.

Confirm both are healthy:

```bash
docker compose ps
```

### 5. Run migrations

```bash
alembic upgrade head
```

Verify:

```bash
alembic current
```

Expect `4f946de6dbf1 (head)`.

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

`--reload` restarts on file changes. Omit it to approximate production.

### 7. Verify the installation

```bash
curl http://localhost:8000/health
```

A healthy response reports both dependencies up:

```json
{
  "status": "healthy",
  "app": "Instagram AI Agent",
  "version": "1.0.0",
  "environment": "development",
  "uptime_seconds": 3.1,
  "checks": { "database": true, "redis": true }
}
```

If `status` is `degraded`, check which dependency is `false` and see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Now exercise the API end to end:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"username\":\"dev\",\"full_name\":\"Dev User\",\"email\":\"dev@example.com\",\"password\":\"supersecret123\"}"
```

```bash
curl -X POST http://localhost:8000/api/v1/auth/login -d "username=dev@example.com" -d "password=supersecret123"
```

Copy the `access_token` from that response and call a protected endpoint:

```bash
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer PASTE_TOKEN_HERE"
```

Getting your own user record back means the whole stack — HTTP, auth,
database — is working.

### 8. Seed data (optional)

There is no seed script. Analytics data comes from a real connected Instagram
account, and fabricating it in the database would produce misleading numbers.

To explore analytics without Meta credentials, the test suite seeds a
realistic account with known values — see `seed_connected_account` in
[`tests/conftest.py`](tests/conftest.py), which you can adapt into a script
if you want a populated development database.

### 9. Start a background worker (optional)

Only needed for `POST /jobs/reports/{period}`. In a second terminal, with the
virtual environment active:

```bash
python -m app.worker
```

---

## Running with Docker

`docker-compose.yml` (development) runs **only Postgres and Redis**.
`docker-compose.prod.yml` runs the **full stack** including the app and
worker.

### Development datastores

```bash
docker compose up -d
```

```bash
docker compose ps
```

```bash
docker compose logs -f postgres
```

```bash
docker compose stop
```

```bash
docker compose down
```

To also delete the database volume — this destroys all local data:

```bash
docker compose down -v
```

### Full stack

Build and start everything:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically via `docker/entrypoint.sh` before the server
starts.

Follow logs for one service:

```bash
docker compose -f docker-compose.prod.yml logs -f app
```

Restart a service:

```bash
docker compose -f docker-compose.prod.yml restart app
```

Rebuild after changing dependencies or the Dockerfile:

```bash
docker compose -f docker-compose.prod.yml build --no-cache app
```

Run more workers:

```bash
docker compose -f docker-compose.prod.yml up -d --scale worker=3
```

Open a shell inside the app container:

```bash
docker compose -f docker-compose.prod.yml exec app sh
```

Stop everything:

```bash
docker compose -f docker-compose.prod.yml down
```

---

## Running without Docker

### PostgreSQL

Install PostgreSQL 16 ([downloads](https://www.postgresql.org/download/)),
then create the database:

```bash
psql -U postgres -c "CREATE DATABASE instagram_ai;"
```

Point `.env` at it:

```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/instagram_ai
```

Confirm the connection:

```bash
psql -U postgres -d instagram_ai -c "SELECT version();"
```

### Redis

Install Redis 7. On Windows, either use WSL2 or
[Memurai](https://www.memurai.com/); Redis has no official Windows build.

```bash
redis-server
```

Confirm it answers:

```bash
redis-cli ping
```

Expect `PONG`. Keep `REDIS_URL=redis://localhost:6379` in `.env`.

> Redis is required for the app to report *ready*, but the app degrades
> gracefully if it disappears at runtime: caching falls back to regenerating
> and only background jobs stop working.

### Migrations and the server

Identical to the Docker path:

```bash
alembic upgrade head
```

```bash
uvicorn app.main:app --reload
```

### Background worker

```bash
python -m app.worker
```

The worker needs the same `.env`, since it connects to both Postgres and
Redis directly.

---

## Accessing services

| Service | URL | Notes |
| --- | --- | --- |
| API root | <http://localhost:8000/> | Version banner |
| **Swagger UI** | <http://localhost:8000/docs> | Interactive; use **Authorize** for bearer auth |
| **ReDoc** | <http://localhost:8000/redoc> | Reference-style docs |
| OpenAPI schema | <http://localhost:8000/openapi.json> | Raw spec |
| Health | <http://localhost:8000/health> | Summary with dependency checks |
| Readiness | <http://localhost:8000/health/ready> | `503` when a dependency is down |
| Liveness | <http://localhost:8000/health/live> | Process-only check |
| **Metrics** | <http://localhost:8000/metrics> | Prometheus format |
| PostgreSQL | `localhost:5432` | user `postgres`, db `instagram_ai` |
| Redis | `localhost:6379` | |

`/docs`, `/redoc`, and `/openapi.json` are **disabled** when
`ENVIRONMENT=production`.

Connect to the datastores directly:

```bash
docker compose exec postgres psql -U postgres -d instagram_ai
```

```bash
docker compose exec redis redis-cli
```

---

## Running the tests

```bash
pytest
```

289 tests, no external services required — the database, Redis, Meta, and
OpenAI are all stubbed. See [TESTING.md](TESTING.md).

---

## Next steps

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the system fits together
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — every endpoint
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — adding features
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — when something breaks
