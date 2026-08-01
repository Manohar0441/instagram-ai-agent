# API Documentation

Complete reference for all 27 endpoints. Every example response below was
captured from the running application, not written by hand.

Interactive docs are served at **`/docs`** (Swagger UI) and **`/redoc`**
during development. Both are disabled when `ENVIRONMENT=production`.

- **Base URL:** `http://localhost:8000`
- **Versioned prefix:** `/api/v1` (operational endpoints are unversioned)

---

## Contents

- [Authentication](#authentication)
- [Conventions](#conventions)
- [Auth endpoints](#auth-endpoints)
- [Users](#users)
- [Instagram](#instagram)
- [Analytics](#analytics)
- [AI agent](#ai-agent)
- [AI insights & reports](#ai-insights--reports)
- [Background jobs](#background-jobs)
- [Operational](#operational)
- [Error reference](#error-reference)

---

## Authentication

All protected endpoints use a bearer token obtained from
`POST /api/v1/auth/login`:

```
Authorization: Bearer <access_token>
```

Tokens are HS256 JWTs, valid for `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
(default 30). They carry a `type: "access"` claim which is verified on every
request — a token of any other kind (such as an Instagram OAuth state token)
is rejected with `401`.

In Swagger UI, click **Authorize** and paste the token.

> **Note on the login form.** `POST /auth/login` follows the OAuth2 password
> form standard, whose field is named `username`. This API authenticates by
> **email**, so put the email address in the `username` field.

---

## Conventions

| Aspect | Behavior |
| --- | --- |
| Request format | JSON, except `/auth/login` which is `application/x-www-form-urlencoded` |
| Response format | JSON |
| Timestamps | ISO 8601 |
| Missing metrics | `null` — never a fabricated `0`. `null` means "not available", which is distinct from a genuine zero |
| Not-found vs forbidden | Resources belonging to another user return `404`, not `403`, so the API cannot be used to confirm that an ID exists |
| Rate limits | Per client IP. 100/min default, 10/min on AI endpoints, 5/min on login and register. Exceeding returns `429` |

Every response carries an `X-Request-ID` header — include it when reporting a
problem, as it appears in the server logs for that request.

---

## Auth endpoints

### `POST /api/v1/auth/register`

Create a user account. **Public.** Rate limit: 5/min.

**Request body**

| Field | Type | Rules |
| --- | --- | --- |
| `username` | string | 1–100 chars, unique |
| `full_name` | string | 1–200 chars |
| `email` | string | valid email, unique |
| `password` | string | 8–72 chars |

```json
{
  "username": "creator1",
  "full_name": "Creator One",
  "email": "creator1@example.com",
  "password": "supersecret123"
}
```

**`201 Created`**

```json
{
  "id": 1,
  "username": "creator1",
  "full_name": "Creator One",
  "email": "creator1@example.com",
  "created_at": "2026-07-31T19:41:28"
}
```

The password hash is never returned by any endpoint.

**Errors:** `409` username or email already in use · `422` validation failed ·
`429` rate limited · `500` creation failed

---

### `POST /api/v1/auth/login`

Exchange credentials for an access token. **Public.** Rate limit: 5/min.

**Request body** — `application/x-www-form-urlencoded`

| Field | Type | Notes |
| --- | --- | --- |
| `username` | string | **the user's email address** |
| `password` | string | |

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=creator1@example.com" \
  -d "password=supersecret123"
```

**`200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:** `401` invalid credentials — deliberately identical whether the
email is unknown or the password is wrong, so accounts cannot be enumerated ·
`422` · `429`

---

### `GET /api/v1/auth/me`

Return the authenticated user. **Bearer required.**

**`200 OK`**

```json
{
  "id": 1,
  "username": "creator1",
  "full_name": "Creator One",
  "email": "creator1@example.com",
  "created_at": "2026-07-31T19:41:28"
}
```

**Errors:** `401` missing, malformed, expired, or wrong-type token

---

## Users

### `GET /api/v1/users/{user_id}`

Return a user record. **Bearer required.** Users may only retrieve **their
own** record.

| Parameter | In | Type | Notes |
| --- | --- | --- | --- |
| `user_id` | path | integer > 0 | must match the authenticated user |

**`200 OK`** — same shape as `/auth/me`.

**Errors:** `401` · `404` no such user, **or the record belongs to someone
else** · `422` non-integer or non-positive id

> Requesting another user's ID returns `404` rather than `403` on purpose: a
> `403` would confirm the account exists.

---

## Instagram

Connecting an account requires `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`,
and `INSTAGRAM_REDIRECT_URI`. Without them `/connect` returns `503`.

### `GET /api/v1/instagram/connect`

Start the OAuth flow. **Bearer required.**

Returns the Meta consent URL rather than issuing a redirect — the endpoint is
bearer-protected, and a plain browser navigation cannot carry an
`Authorization` header. The client should `fetch` this, then navigate the
browser to `authorization_url`.

**`200 OK`**

```json
{
  "authorization_url": "https://www.facebook.com/v21.0/dialog/oauth?client_id=...&state=eyJhbGciOi..."
}
```

The `state` parameter is a signed JWT that expires in 10 minutes and binds
the callback to the requesting user.

**Errors:** `401` · `503` integration not configured

---

### `GET /api/v1/instagram/callback`

Handle Meta's redirect and store the connection. **Public by necessity** — a
browser redirect carries no `Authorization` header, so the signed `state`
parameter identifies the user instead.

| Parameter | In | Type | Notes |
| --- | --- | --- | --- |
| `code` | query | string? | authorization code from Meta |
| `state` | query | string? | signed state issued by `/connect` |
| `error` | query | string? | present when the user declined |
| `error_description` | query | string? | human-readable reason |

**`200 OK`**

```json
{
  "id": 1,
  "instagram_user_id": "17841400000000000",
  "username": "creator1",
  "account_type": "BUSINESS",
  "biography": "Coffee and code.",
  "profile_picture_url": "https://scontent.cdninstagram.com/v/pic.jpg",
  "followers_count": 1200,
  "media_count": 2,
  "token_expires_at": "2026-09-29T19:41:28",
  "connected_at": "2026-07-31T19:41:28"
}
```

The access token and Facebook Page ID are deliberately absent from this
schema and never returned.

**Errors:** `400` user denied access, or `code`/`state` missing · `401`
invalid, expired, or wrong-type state · `409` this user already has an
account connected, or this Instagram account belongs to another user · `502`
Graph API request failed

---

### `GET /api/v1/instagram/profile`

Refresh from the Graph API and return the connected account. Also writes a
follower-count snapshot used for growth tracking. **Bearer required.**

**`200 OK`** — same shape as the callback response.

**Errors:** `401` token expired or revoked upstream · `404` no account
connected · `502` Graph API failed

---

### `GET /api/v1/instagram/media`

Fetch posts and reels from Instagram and store them. **Bearer required.**

| Parameter | In | Type | Default | Range |
| --- | --- | --- | --- | --- |
| `limit` | query | integer | 25 | 1–100 |

**`200 OK`**

```json
[
  {
    "id": 1,
    "media_id": "17912345678901234",
    "media_type": "IMAGE",
    "caption": "Morning light in the studio.",
    "media_url": "https://scontent.cdninstagram.com/v/1.jpg",
    "permalink": "https://www.instagram.com/p/ABC123/",
    "posted_at": "2026-07-28T19:41:28"
  }
]
```

Repeat calls update existing rows rather than duplicating them.

**Errors:** `401` · `404` · `422` · `502`

---

### `GET /api/v1/instagram/insights`

Fetch and store account-level insights plus insights for each already-stored
media item (call `/instagram/media` first). Capped at 25 media per request.
**Bearer required.**

**`200 OK`**

```json
{
  "account_insights": {
    "period": "day",
    "metrics": { "reach": 5000, "impressions": 6000, "profile_views": 200 },
    "fetched_at": "2026-07-31T19:41:28"
  },
  "media_insights": [
    {
      "media_id": "17912345678901234",
      "metrics": { "reach": 1000, "impressions": 1200, "saved": 5 },
      "fetched_at": "2026-07-31T19:41:28"
    }
  ]
}
```

`metrics` is an open JSON object — its keys are whatever the Graph API
returned, so new Meta metrics appear without a schema change.

**Errors:** `401` · `404` · `502`

---

### `DELETE /api/v1/instagram/disconnect`

Disconnect the account and delete its stored data (media and insights cascade).
**Bearer required.**

**`204 No Content`** · **Errors:** `404` nothing connected

---

## Analytics

All analytics endpoints read **only** stored data — they never call the Graph
API, so they are fast and cannot exhaust Meta's rate limits. Populate data
first via `/instagram/media` and `/instagram/insights`.

**Engagement rate** = `(likes + comments + shares + saves) / reach × 100`.
Because it is normalized by reach, a small post with high engagement can
outrank a viral one.

### `GET /api/v1/analytics/account`

Account-level analytics. **Bearer required.**

| Parameter | In | Type | Default | Range |
| --- | --- | --- | --- | --- |
| `days` | query | integer | 30 | 1–365 |

**`200 OK`**

```json
{
  "instagram_user_id": "17841400000000000",
  "username": "creator1",
  "followers_count": 1200,
  "follower_growth": { "absolute": 200, "percentage": 20.0 },
  "media_count": 2,
  "reach": 5000,
  "impressions": 6000,
  "profile_visits": 200,
  "accounts_reached": 5000,
  "accounts_engaged": 120,
  "engagement_rate": 10.38,
  "period_days": 30,
  "last_updated": "2026-07-31T17:41:28.171394"
}
```

`follower_growth` is `null` until at least two profile snapshots exist within
the window (each `/instagram/profile` call writes one).

**Errors:** `401` · `404` no account connected · `422`

---

### `GET /api/v1/analytics/media`

Per-post analytics, newest first. **Bearer required.**

| Parameter | In | Type | Default | Range |
| --- | --- | --- | --- | --- |
| `limit` | query | integer | 25 | 1–100 |
| `media_type` | query | string? | — | e.g. `IMAGE`, `VIDEO`, `REELS` |

**`200 OK`**

```json
[
  {
    "media_id": "17998765432109876",
    "media_type": "REELS",
    "caption": "60 seconds of process.",
    "permalink": "https://www.instagram.com/reel/XYZ789/",
    "posted_at": "2026-07-30T19:41:28.171394",
    "likes": 500,
    "comments": 80,
    "shares": 60,
    "saves": 100,
    "reach": 8000,
    "impressions": 9000,
    "engagement_rate": 9.25,
    "watch_time": 4500,
    "completion_rate": null,
    "insights_fetched_at": "2026-07-31T18:41:28.171394"
  },
  {
    "media_id": "17912345678901234",
    "media_type": "IMAGE",
    "caption": "Morning light in the studio.",
    "permalink": "https://www.instagram.com/p/ABC123/",
    "posted_at": "2026-07-28T19:41:28.171394",
    "likes": 100,
    "comments": 10,
    "shares": null,
    "saves": 5,
    "reach": 1000,
    "impressions": 1200,
    "engagement_rate": 11.5,
    "watch_time": null,
    "completion_rate": null,
    "insights_fetched_at": "2026-07-31T16:41:28.171394"
  }
]
```

`completion_rate` is always `null`: it requires video duration, which the
Graph API field set this app requests does not reliably return. It is
reported as unavailable rather than estimated.

**Errors:** `401` · `404` · `422`

---

### `GET /api/v1/analytics/trends`

Historical performance in time buckets. **Bearer required.**

| Parameter | In | Type | Default | Allowed |
| --- | --- | --- | --- | --- |
| `granularity` | query | string | `daily` | `daily`, `weekly`, `monthly` |
| `days` | query | integer | 30 | 1–365 |

**`200 OK`**

```json
{
  "granularity": "daily",
  "points": [
    {
      "period_start": "2026-07-28",
      "reach": null,
      "impressions": null,
      "profile_visits": null,
      "followers_count": null,
      "posts_count": 1,
      "average_engagement_rate": 11.5
    },
    {
      "period_start": "2026-07-31",
      "reach": 5000,
      "impressions": 6000,
      "profile_visits": 200,
      "followers_count": 1200,
      "posts_count": 0,
      "average_engagement_rate": null
    }
  ]
}
```

Buckets are chronological. A bucket may hold post activity without account
metrics, or vice versa, depending on when snapshots were taken — hence the
`null`s above.

To compare periods, request a wide enough window and compare buckets (e.g.
`?granularity=monthly&days=60`).

**Errors:** `401` · `404` · `422`

---

### `GET /api/v1/analytics/top-content`

Best- or worst-performing content. **Bearer required.**

| Parameter | In | Type | Default | Allowed |
| --- | --- | --- | --- | --- |
| `limit` | query | integer | 5 | 1–50 |
| `metric` | query | string | `engagement_rate` | `engagement_rate`, `reach`, `likes`, `comments`, `impressions` |
| `order` | query | string | `top` | `top`, `bottom` |

**`200 OK`**

```json
{
  "metric": "engagement_rate",
  "order": "top",
  "items": [ { "media_id": "17912345678901234", "engagement_rate": 11.5, "...": "..." } ]
}
```

`items` entries have the same shape as `/analytics/media`. Posts with no
computable value for the chosen metric are excluded rather than ranked as
zero.

**Errors:** `401` · `404` · `422`

---

### `GET /api/v1/analytics/dashboard`

Account analytics, top content, and a 7-day trend in one call. **Bearer
required.** No parameters.

**`200 OK`**

```json
{
  "account": { "...": "AccountAnalyticsResponse" },
  "top_content": [ { "...": "MediaAnalyticsResponse" } ],
  "recent_trend": [ { "...": "TrendPoint" } ]
}
```

Values are identical to calling `/analytics/account`, `/analytics/top-content`
and `/analytics/trends?days=7` separately, but share one database round of
work (7 queries instead of 13).

**Errors:** `401` · `404`

---

## AI agent

### `POST /api/v1/ai/chat`

Ask a natural-language question about your analytics. **Bearer required.**
Rate limit: 10/min.

The agent runs a LangGraph tool-calling loop over five analytics tools. It
can only read **your** data: the user ID is bound into each tool by closure
and is not part of any tool's schema, so it cannot be influenced by the
prompt.

**Request body**

| Field | Type | Rules |
| --- | --- | --- |
| `message` | string | 1–2000 chars |

```json
{ "message": "Which of my posts performed best this month?" }
```

**`200 OK`**

```json
{
  "response": "Your photo post \"Morning light in the studio\" performed best with an 11.5% engagement rate, ahead of your reel at 9.25% — despite the reel getting 5x more likes, its much larger reach lowers the rate.",
  "tools_used": ["get_top_or_lowest_content"]
}
```

`tools_used` lists the analytics tools consulted, in call order. It is empty
when the model answered without needing data.

**Example questions**

- "How did my account perform this week?"
- "Which reel performed the best?"
- "What is my engagement rate?"
- "Show my follower growth."
- "Compare this month with last month."
- "Summarize my recent performance."

If no Instagram account is connected the request still returns `200` — the
agent explains the situation conversationally rather than erroring.

**Errors:** `401` · `422` empty or over-length message · `502` Gemini request
failed · `503` `GOOGLE_API_KEY` not configured

---

### `GET /api/v1/ai/health`

AI subsystem readiness. **Bearer required.** Checks configuration only — it
does not call Gemini, so it costs nothing and does not depend on Gemini's
uptime.

**`200 OK`**

```json
{
  "status": "ok",
  "model": "gemini-2.0-flash",
  "configured": true,
  "details": null
}
```

When unconfigured, `status` is `"unavailable"` and `details` explains why.
The endpoint still returns `200` — it reports status rather than failing.

---

## AI insights & reports

These four endpoints each cost **one** LLM call on a cache miss and are
cached per user for `CACHE_TTL_SECONDS` (default 900s). If Redis is
unavailable they regenerate rather than fail.

The model is only ever asked to write prose. Every figure is attached by the
service from stored analytics, so a hallucinated number has nowhere to appear.

### `GET /api/v1/insights`

Five generated performance insights. **Bearer required.** Rate limit: 10/min.

**`200 OK`** (abridged)

```json
{
  "account_performance": {
    "title": "Account Performance",
    "summary": "Reach climbed to 5,000 this period, up from 3,000 five days ago, and profile visits followed at 200.",
    "supporting_data": {
      "followers_count": 1200,
      "follower_growth": { "absolute": 200, "percentage": 20.0 },
      "reach": 5000,
      "impressions": 6000,
      "engagement_rate": 10.38,
      "period_days": 30
    }
  },
  "content_performance": {
    "title": "Content Performance",
    "summary": "Your photo post is outperforming your reel on engagement rate despite far fewer likes.",
    "supporting_data": {
      "post_count": 2,
      "average_engagement_rate": 10.38,
      "total_likes": 600,
      "total_comments": 90
    }
  },
  "growth_trend": { "title": "Growth Trend", "summary": "...", "supporting_data": { "follower_growth": { "absolute": 200, "percentage": 20.0 } } },
  "engagement_trend": { "title": "Engagement Trend", "summary": "...", "supporting_data": { "trend_points": [] } },
  "audience_behavior": {
    "title": "Audience Behavior",
    "summary": "With only two posts there isn't yet enough history to identify a reliable best time to post.",
    "supporting_data": {
      "sample_size": 2,
      "average_engagement_by_hour": { "19": 10.38 },
      "average_engagement_by_weekday": { "Tuesday": 11.5, "Thursday": 9.25 }
    }
  },
  "generated_at": "2026-07-31T19:41:29.106541Z"
}
```

Each insight's `supporting_data` is the real analytics the narrative was
based on — useful for rendering a figure next to the prose, and for
verifying the prose.

`audience_behavior` derives from engagement and posting-time patterns only;
the platform holds no demographic data.

**Errors:** `401` · `404` no account connected · `502` · `503`

---

### `GET /api/v1/recommendations`

Personalized recommendations derived from your own history. **Bearer
required.** Rate limit: 10/min.

**`200 OK`**

```json
{
  "best_posting_times": "There isn't enough posting history yet to recommend a specific time with confidence.",
  "recommended_content_formats": "Your single image post is converting reach into engagement better than your reel.",
  "content_ideas": [
    "A behind-the-scenes photo series, mirroring the format of your best performer",
    "A short reel answering the questions your comments raise",
    "A carousel breaking down your most-saved post"
  ],
  "posting_frequency": "You published 2 posts in the last 30 days, roughly 0.47 per week. Increasing cadence would give clearer signal.",
  "engagement_reach_tips": [
    "Ask an explicit question in captions to lift comments",
    "Post consistently for two weeks to build comparable data"
  ],
  "generated_at": "2026-07-31T19:41:29.106541Z"
}
```

Posting-time, format, and frequency statistics are computed in code, not by
the model — it only narrates them. With little history the response says so
rather than inventing a recommendation.

**Errors:** `401` · `404` · `502` · `503`

---

### `GET /api/v1/reports/weekly` · `GET /api/v1/reports/monthly`

A full performance report. **Bearer required.** Rate limit: 10/min.

Weekly covers 7 days with daily trend granularity; monthly covers 30 days
with weekly granularity. Otherwise identical.

**`200 OK`** (abridged)

```json
{
  "period": "weekly",
  "period_start": "2026-07-24",
  "period_end": "2026-07-31",
  "summary": "A short but positive week: reach reached 5,000 and you gained 200 followers, though only two posts are available to judge.",
  "top_performing_content": [ { "media_id": "17912345678901234", "engagement_rate": 11.5, "...": "..." } ],
  "underperforming_content": [ { "media_id": "17998765432109876", "engagement_rate": 9.25, "...": "..." } ],
  "key_strengths": ["Follower growth of 20%", "Strong engagement rate on image content"],
  "areas_for_improvement": ["Low posting volume limits what can be measured"],
  "actionable_next_steps": ["Publish at least three posts next week", "Repeat the format of your top performer"],
  "generated_at": "2026-07-31T19:41:29.106541Z"
}
```

The content lists come from the analytics layer; only `summary`,
`key_strengths`, `areas_for_improvement`, and `actionable_next_steps` are
model-written.

**Errors:** `401` · `404` · `502` · `503`

---

## Background jobs

Report generation can also run asynchronously — useful when you do not want
to hold a request open for an LLM round trip. Requires a running worker
(`python -m app.worker`).

### `POST /api/v1/jobs/reports/{period}`

Queue report generation. **Bearer required.** Rate limit: 10/min.

| Parameter | In | Type | Allowed |
| --- | --- | --- | --- |
| `period` | path | string | `weekly`, `monthly` |

**`202 Accepted`**

```json
{ "job_id": "6f2c1e4a-6b7d-4c1a-9f3e-2b7a5d8c0e11", "status": "queued" }
```

**Errors:** `401` · `422` unsupported period

---

### `GET /api/v1/jobs/{job_id}`

Poll a job. **Bearer required.** Only the user who queued the job can read it.

**`200 OK`**

```json
{
  "job_id": "6f2c1e4a-6b7d-4c1a-9f3e-2b7a5d8c0e11",
  "status": "finished",
  "result": { "period": "weekly", "summary": "...", "...": "..." },
  "error": null
}
```

`status` is one of `queued`, `started`, `finished`, `failed`. `result` holds
the same payload as `GET /reports/{period}` once finished, and is `null`
before that. On failure, `error` describes what went wrong.

**Errors:** `401` · `404` unknown job **or a job belonging to another user**

---

## Operational

Unversioned, unauthenticated, and excluded from request logging.

### `GET /health/live`

Liveness. Checks nothing external — a failure means the process should be
restarted.

```json
{ "status": "alive" }
```

Always `200` if the process is running.

---

### `GET /health/ready`

Readiness. Verifies database and Redis connectivity.

```json
{ "status": "ready", "checks": { "database": true, "redis": true } }
```

`200` when ready, **`503`** when any dependency is unreachable — the signal
for a load balancer to stop routing traffic here without restarting.

---

### `GET /health`

Human-facing summary.

```json
{
  "status": "degraded",
  "app": "Instagram AI Agent",
  "version": "1.0.0",
  "environment": "development",
  "uptime_seconds": 5.2,
  "checks": { "database": false, "redis": true }
}
```

`200` when healthy, `503` when degraded. The example above is a real response
with Postgres stopped.

---

### `GET /metrics`

Prometheus exposition format — request counts, latency histograms, and status
codes. Point a scrape config at `app:8000/metrics`.

---

### `GET /`

Service banner.

```json
{
  "status": "running",
  "app": "Instagram AI Agent",
  "version": "1.0.0",
  "environment": "development"
}
```

---

## Error reference

| Status | Meaning | Typical cause |
| --- | --- | --- |
| `400` | Bad request | OAuth callback missing `code`/`state`, or the user declined |
| `401` | Unauthenticated | Missing/expired/malformed token, wrong token type, bad credentials, or a revoked Instagram token |
| `404` | Not found | No Instagram account connected; unknown ID; **or a resource belonging to another user** |
| `409` | Conflict | Duplicate username/email; an account is already connected |
| `422` | Validation failed | Body or query parameters failed validation |
| `429` | Rate limited | Exceeded the per-IP limit for that endpoint |
| `500` | Server error | Unexpected failure — always a generic message; details are logged server-side |
| `502` | Upstream failed | Instagram Graph API or Gemini request failed |
| `503` | Not configured | `GOOGLE_API_KEY` or the Instagram credentials are missing |

Most errors return a single `detail` string:

```json
{ "detail": "No Instagram account is connected for this user." }
```

Validation errors (`422`) return FastAPI's structured list instead:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address: An email address must have an @-sign.",
      "input": "bad"
    },
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": { "min_length": 8 }
    }
  ]
}
```

`500` responses are always exactly:

```json
{ "detail": "An unexpected error occurred. Please try again later." }
```

Internal details never reach the client; the full stack trace is written to
the server log alongside the request ID.
