# Milestone 9 — Code Review, Security Audit & Optimization

A quality pass over the finished backend: what was found, what was changed,
and what was deliberately left alone.

---

## 1. Security findings

### SEC-1 (High) — Unauthenticated user enumeration and PII exposure · **Fixed**

`GET /api/v1/users` returned **every** user record, including email
addresses, with **no authentication at all**. `GET /api/v1/users/{id}` was
likewise open. `POST /api/v1/users` was an unauthenticated duplicate of
`POST /auth/register` that also bypassed that endpoint's strict
brute-force rate limit (5/min), leaving registration abuse limited only by
the 100/min default.

**Fix.** `GET /users` and `POST /users` were removed; `GET /users/{id}` now
requires authentication and returns only the caller's own record. A request
for someone else's ID returns **404, not 403** — a 403 would confirm the ID
exists and turn the endpoint into an enumeration oracle.

> **This is a breaking API change.** Registration is now solely
> `POST /auth/register`, and there is no list-all-users endpoint. Both were
> removed rather than merely protected: registration must be unauthenticated
> by definition (so the duplicate could not be safely gated), and there is no
> role system that could legitimately authorize a list-all operation. If you
> need either back — say, for an admin console — the right shape is an
> explicit admin role, not a reopened public endpoint.

### SEC-2 (Medium) — OAuth state tokens were valid API credentials · **Fixed**

All tokens were signed with the same key and neither decoder checked what
kind of token it had been handed. An Instagram OAuth **state** token was
therefore accepted as a bearer **access** token. This matters because a
state token is not a secret in practice: it travels in a query string, so it
lands in the browser address bar, in browser history, and in the `Referer`
header sent to `facebook.com`.

Confirmed before fixing:

```
decoded OK as access token: {'sub': '1', 'exp': ..., 'type': 'instagram_oauth_state'}
>>> An OAuth state token is accepted as a bearer access token.
```

**Fix.** Access tokens now carry `"type": "access"` and `decode_access_token`
verifies it, mirroring the check the state decoder already performed. Both
directions are covered by regression tests.

> **Deploy note:** access tokens issued before this change lack the `type`
> claim and are now rejected, so every signed-in user is logged out once on
> deploy. Tokens live 30 minutes, so no other action is needed.

### SEC-3 (Low) — Invalid token subject returned 500 instead of 401 · **Fixed**

`int(token_data.sub)` sat outside the `try` in `get_current_user`, so a
token with a well-formed but non-numeric `sub` raised `ValueError` and
surfaced as a 500. A malformed credential is a 401. Moved inside the guard.

### Verified as already correct — no change made

- **Access tokens are not leaked in error messages.** The Graph API client
  passes tokens as query parameters (Meta's documented style), and
  `httpx.RequestError` carries the full URL on `.request.url`. The client
  interpolates only `str(exc)`, which excludes the URL — verified
  empirically. Noisy `httpx` INFO logging, which would print full URLs, is
  already suppressed to WARNING in `configure_logging`.
- **Passwords** are bcrypt-hashed with a per-hash salt and never returned by
  any endpoint.
- **Instagram access tokens** are Fernet-encrypted at rest and excluded from
  every response schema.
- **Login** returns an identical error for an unknown email and a wrong
  password, so accounts cannot be enumerated through it.
- **The AI agent cannot be steered across users.** `user_id` is bound by
  closure and is structurally absent from every tool's schema, so a
  prompt-injected `user_id` argument is dropped by the schema binding rather
  than reaching the service layer.
- **`.env`** is gitignored and untracked; no secret is committed.
- **Unhandled exceptions** return a generic message while the full trace is
  logged server-side.

---

## 2. Performance findings

### PERF-1 — `/analytics/dashboard` did the same work three times · **Fixed**

The dashboard called the three public analytics methods, each of which
independently re-resolved the account and re-fetched all media plus their
insights. Measured: **13 SELECT statements** for one request.

**Fix.** The dashboard now resolves the account once and computes media
analytics once, passing both into the three section builders. Trend building
also now reuses those computed analytics instead of re-reading media and
insights — the engagement rate it needs is derived from exactly the same
inputs it used to recompute.

**Result: 13 → 7 queries**, with all three sections verified byte-identical
to the standalone endpoints (asserted in both a service test and an API
test, plus a query-count regression guard).

### Already addressed in earlier milestones

- The N+1 on media insights is avoided by a single window-function query
  (`get_latest_by_media_ids`).
- Connection pooling with `pool_pre_ping` is configured.
- AI endpoints cache to Redis, so a repeat request costs no LLM call.

### Accepted, not changed

- `get_media_analytics` computes analytics for all of an account's media
  and then slices to `limit`. Pushing the limit into SQL would require
  changing shared repository ordering semantics for a bounded, per-user
  dataset — not worth the risk here.

---

## 3. Code quality

**Changed**
- Removed `UserService.list_users`, dead once the list endpoint was deleted.
- Split the analytics public methods into thin resolve-then-delegate
  wrappers over private implementations that accept pre-computed data. This
  is what makes the dashboard fix possible without duplicating logic.

**Reviewed and left as-is**
- Layering holds throughout: routers contain no business logic and no
  queries, services contain no HTTP concerns, and only repositories build
  SQLAlchemy statements. The AI layer talks exclusively to services.
- The two bare `except Exception` clauses are in the health probes, where
  catching everything is correct — a health check must never itself raise.
- Naming, docstrings, and error-handling patterns are consistent across
  modules.

---

## 4. Test suite

Replaces the ad-hoc scratchpad scripts used during development with a
committed suite: **289 tests**, all passing.

| Layer | Tests | Location | Covers |
| --- | ---: | --- | --- |
| Unit | 61 | `tests/unit/` | Engagement/growth maths, bucketing, ranking, posting-time and format breakdowns, password hashing, token encryption, JWT issue/verify, cache fail-open |
| Integration | 76 | `tests/integration/` | Services against a real (SQLite) database: users, auth, Instagram OAuth and fetching, analytics, insights/recommendations/reports, background jobs |
| API | 152 | `tests/api/` | Every endpoint over HTTP: auth, authorization matrix, Instagram, analytics, AI chat, insights/reports, health, metrics, security headers, rate limiting, jobs |
| **Total** | **289** | | Full run: ~72s |

Run with:

```bash
pytest
```

Or by layer: `pytest -m unit`, `-m integration`, `-m api`.

No test touches the network, a real database, Redis, Meta, or Gemini —
every boundary is stubbed in `tests/conftest.py`, so the suite costs nothing
to run and is deterministic.

**Notable coverage**
- A parametrized matrix asserts all 20 protected endpoints reject anonymous
  callers, and that the 8 intentionally-public ones stay reachable — so
  accidentally exposing an endpoint fails the build.
- Cross-user isolation is asserted for analytics, Instagram data, user
  records, and background jobs.
- Regression tests for all three security fixes and the dashboard query fix.
- Grounding tests prove AI responses carry real database figures: the stub
  model returns prose containing no numbers, so any correct figure in the
  response must have come from the analytics layer.
- Cache tests count generations to prove a cache hit *skips work*, rather
  than merely returning equivalent data.

**Known limits of the suite**
- SQLite stands in for Postgres. `ON DELETE CASCADE` and JSONB operators are
  therefore not exercised; the disconnect test asserts only what SQLite can
  honestly verify and says so.
- The LLM and Graph API are stubbed, so response *quality* and Meta's real
  API contract remain unverified — as flagged in Milestones 6 and 7.

---

## 5. Recommendations not acted on

1. **Send Graph API tokens in an `Authorization` header** rather than as
   query parameters. Meta supports it and it keeps tokens out of URLs
   entirely. Not changed here because it alters how the app talks to an
   external API that cannot be tested against in this environment — a
   verification risk that outweighs the marginal gain, given tokens are
   already confirmed not to leak into responses or logs.
2. **Add an admin role** if a user-management surface is ever needed again,
   rather than reopening the endpoints removed under SEC-1.
3. **Cache invalidation on data refresh.** Fetching new media does not clear
   cached insights, so AI output can lag by up to `CACHE_TTL_SECONDS`
   (default 15 min). Acceptable today; worth revisiting if the TTL is
   raised.
4. **Dependency vulnerability scanning** in CI (`pip-audit`). Dependencies
   were reviewed by hand here; no scanner ran, so no clean bill of health is
   claimed.
