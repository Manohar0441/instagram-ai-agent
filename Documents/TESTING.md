# Testing

289 tests across three layers. The suite contacts **nothing external** — no
database server, no Redis, no Meta, no Gemini — so it runs anywhere, costs
nothing, and is deterministic.

---

## Running the tests

Install the dev dependencies once:

```bash
pip install -r requirements-dev.txt
```

Run everything:

```bash
pytest
```

Expect `289 passed` in roughly 70 seconds. Most of that is bcrypt, which is
deliberately slow by design.

### By layer

```bash
pytest -m unit
```

```bash
pytest -m integration
```

```bash
pytest -m api
```

| Marker | Tests | Time | What it covers |
| --- | ---: | ---: | --- |
| `unit` | 61 | ~2s | Pure functions, no I/O |
| `integration` | 76 | ~17s | Services + repositories against a real (SQLite) database |
| `api` | 152 | ~46s | Full stack over HTTP via `TestClient` |

### Narrowing down

A single file:

```bash
pytest tests/api/test_auth_api.py
```

A single class or test:

```bash
pytest tests/api/test_auth_api.py::TestLogin::test_issues_a_bearer_token
```

By name pattern:

```bash
pytest -k "rate_limit or cache"
```

### Useful flags

```bash
pytest -v
```

```bash
pytest -x
```

```bash
pytest --lf
```

```bash
pytest --durations=10
```

`-x` stops at the first failure; `--lf` re-runs only what failed last time;
`--durations` finds slow tests.

To see `print()` output and log lines from a failing test:

```bash
pytest -s tests/api/test_auth_api.py
```

---

## Coverage

Coverage is not part of the default run. To measure it:

```bash
pip install pytest-cov
```

```bash
pytest --cov=app --cov-report=term-missing
```

An HTML report, which is much easier to read:

```bash
pytest --cov=app --cov-report=html
```

Then open `htmlcov/index.html`.

Enforce a floor in CI:

```bash
pytest --cov=app --cov-fail-under=80
```

> Treat coverage as a *lower bound on confidence*, not a target. A line can
> be executed without being meaningfully checked. The tests that matter most
> here — grounding, authorization isolation, cache-hit counting — assert
> behavior that percentage coverage cannot express.

---

## How the suite is structured

```
tests/
├── conftest.py          # every external boundary is stubbed here
├── unit/                # pure logic
│   ├── test_analytics_calculations.py
│   ├── test_insight_calculations.py
│   ├── test_security_utils.py
│   └── test_cache.py
├── integration/         # services + repositories
│   ├── test_user_and_auth_services.py
│   ├── test_instagram_service.py
│   ├── test_analytics_service.py
│   ├── test_ai_services.py
│   └── test_job_service.py
└── api/                 # full stack over HTTP
    ├── test_auth_api.py
    ├── test_authorization.py
    ├── test_instagram_api.py
    ├── test_analytics_api.py
    ├── test_ai_api.py
    ├── test_insights_api.py
    └── test_production_api.py
```

### What replaces each external dependency

| Real dependency | Test substitute | Why |
| --- | --- | --- |
| PostgreSQL | In-memory SQLite (`StaticPool`) | Real SQL, no server to run |
| Redis | `fakeredis` | Real client API; also avoids multi-second connection timeouts |
| Instagram Graph API | `FakeGraphClient` | Deterministic OAuth and fetch responses |
| Gemini | `CountingStructuredLLM` / scripted agent models | No spend, and generation calls are countable |
| RQ worker | `Queue(is_async=False)` | Jobs execute inline, so results are assertable immediately |

Autouse fixtures reset shared state between tests: tables are emptied, the
rate limiter is cleared, and Redis is swapped for a fresh fake. Tests
therefore cannot leak into each other.

---

## Key fixtures

From [`tests/conftest.py`](tests/conftest.py):

| Fixture | Gives you |
| --- | --- |
| `client` | `TestClient` bound to the test database |
| `non_raising_client` | Same, but returns the app's 500 response instead of re-raising — needed to assert on error *bodies* |
| `db` | A session for arranging data directly |
| `db_user` | A user row, for service tests that skip HTTP |
| `auth_headers` | Bearer headers for user 1 (registered through the API) |
| `other_auth_headers` | A second user, for isolation tests |
| `connected_account` | A seeded Instagram account with media and insights |
| `fake_structured_llm` | Stub LLM that counts generations |
| `fake_graph_client` | Stub Instagram client |
| `job_queue` | Inline RQ queue |
| `worker_db` | Points background jobs at the test database |

### The seeded account

`seed_connected_account` creates two posts with deliberately instructive
numbers:

| Media | Type | Likes | Comments | Shares | Saves | Reach | **Engagement rate** |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `media_1` | IMAGE | 100 | 10 | – | 5 | 1,000 | **11.5%** |
| `media_2` | REELS | 500 | 80 | 60 | 100 | 8,000 | **9.25%** |

`media_1` ranks **higher** despite five times fewer likes, because engagement
rate is normalized by reach. Several tests assert exactly this — it is the
clearest expression of how the metric works.

---

## Writing tests

### Conventions

1. **Name the behavior, not the method.**
   `test_rejects_an_oauth_state_token`, not `test_decode_access_token_2`.
2. **Mark every test** with `pytestmark = pytest.mark.unit` (or
   `integration` / `api`) at module level.
3. **Group with classes** — `TestLogin`, `TestCaching` — for readable output.
4. **Assert one behavior per test**, so a failure names the problem.
5. **Comment the non-obvious.** If an assertion encodes a security property
   or a counter-intuitive number, say why in a docstring.
6. **Never assert something the environment cannot honestly verify.** SQLite
   does not enforce `ON DELETE CASCADE`; the disconnect test asserts only
   what it can prove and documents the gap.

### Example

```python
import pytest

pytestmark = pytest.mark.api


class TestSomething:
    def test_returns_only_the_callers_data(self, client, connected_account, other_auth_headers):
        """User 1 owns the seeded account; user 2 must not see any of it."""
        response = client.get("/api/v1/analytics/account", headers=other_auth_headers)
        assert response.status_code == 404
```

### Adding a test for a new endpoint

1. Add it to `PROTECTED_ENDPOINTS` or `PUBLIC_ENDPOINTS` in
   `tests/api/test_authorization.py`. That matrix is what stops an endpoint
   being exposed by accident.
2. Cover the happy path, the validation failures, and the not-found case.
3. If it returns another user's data when given their ID, assert it returns
   `404`.

---

## What the suite deliberately does not cover

Being explicit about this matters more than a coverage number:

- **Postgres-specific behavior.** SQLite stands in, so `ON DELETE CASCADE`
  and JSONB operators are not exercised. Verify those against a real
  Postgres.
- **The real Instagram Graph API.** Field names and insight metric names come
  from Meta's v21 documentation and have never run against live credentials.
  If a metric silently returns `null` in production, this is the first place
  to look.
- **Real LLM output quality.** The stub returns fixed prose. The suite proves
  the *plumbing* — that data reaches the model and that figures come from the
  database — not that the model writes well.
- **Load and concurrency.** No performance or race-condition testing. The one
  performance assertion is a query-count regression guard on the dashboard.
- **Docker images.** The Dockerfile and Compose files are not built or run by
  the suite.

---

## Continuous integration

There is no CI pipeline yet. A minimal GitHub Actions workflow:

```yaml
name: tests
on: [push, pull_request]

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: pytest
        env:
          APP_NAME: Instagram AI Agent
          APP_VERSION: 1.0.0
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/instagram_ai
          REDIS_URL: redis://localhost:6379
          JWT_SECRET_KEY: test-secret-key-at-least-32-characters-long
          TOKEN_ENCRYPTION_KEY: 5tPz0Yl9m8gGm2yqKz3xY0dEo4cQyM9wJ8nH1sVbA7E=
```

No service containers are needed — the suite stubs both datastores. The
environment variables exist only because `Settings` requires them at import;
they are never connected to.

Adding `pip-audit` to that workflow would close the dependency-scanning gap
noted in [CODE_REVIEW.md](CODE_REVIEW.md#5-recommendations-not-acted-on).
