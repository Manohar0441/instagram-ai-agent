# Architecture

How the system is put together, and why. Read
[§ End-to-end walkthrough](#end-to-end-walkthrough) first if you are new to
the codebase.

---

## 1. System overview

```mermaid
flowchart TB
    Client([Client / Frontend])

    subgraph App["FastAPI application"]
        direction TB
        MW["Middleware stack"]
        Routers["API routers (/api/v1)"]
        Services["Service layer"]
        Repos["Repository layer"]
        MW --> Routers --> Services --> Repos
    end

    Worker["RQ worker process<br/>(app.worker)"]

    PG[("PostgreSQL 16")]
    Redis[("Redis 7")]
    Meta[("Instagram<br/>Graph API")]
    Gemini[("Google Gemini API")]

    Client -->|HTTPS| MW
    Repos --> PG
    Services -->|cache| Redis
    Services -->|enqueue| Redis
    Services -->|OAuth + data| Meta
    Services -->|LLM| Gemini
    Redis -->|dequeue| Worker
    Worker --> PG
    Worker --> Gemini

    Prom["Prometheus"] -.->|scrape /metrics| App
    LB["Load balancer"] -.->|probe /health/ready| App
```

The application process and the worker process run the **same image** with
different commands. The worker has no HTTP surface; it exists so that
report generation can run without holding a request open.

---

## 2. Layered architecture

The core rule, enforced by convention and covered by tests:

> **Route → Service → Repository → SQLAlchemy → PostgreSQL**

```mermaid
flowchart TB
    subgraph L1["API layer · app/api/"]
        direction LR
        A1["Parse + validate request"]
        A2["Inject dependencies"]
        A3["Map exceptions to HTTP codes"]
    end

    subgraph L2["Service layer · app/services/"]
        direction LR
        B1["Business rules"]
        B2["Orchestration"]
        B3["Transactions"]
    end

    subgraph L3["Repository layer · app/repositories/"]
        direction LR
        C1["SQLAlchemy queries"]
    end

    subgraph L4["Data · app/models/"]
        D1["ORM models"]
    end

    L1 --> L2 --> L3 --> L4

    X1["No SQL in routers"] -.-> L1
    X2["No HTTP in services"] -.-> L2
    X3["No business logic in repositories"] -.-> L3
```

| Layer | Does | Never does |
| --- | --- | --- |
| **API** (`app/api/`) | Validates input, injects dependencies, translates service exceptions into status codes | Business logic, database access |
| **Service** (`app/services/`) | Business rules, orchestration, commits transactions, calls external APIs | Touch `Request`/`Response`, raise `HTTPException`, build SQL |
| **Repository** (`app/repositories/`) | Every SQLAlchemy query in the codebase | Business decisions, commits |
| **Model** (`app/models/`) | Table definitions | Anything else |

Supporting packages:

| Package | Role |
| --- | --- |
| `app/core/` | Settings, logging, middleware, rate limiter, exception handlers |
| `app/dependencies/` | FastAPI DI providers — the wiring between layers |
| `app/integrations/` | Outbound clients: Graph API, LangGraph/Gemini, Redis, task queue |
| `app/schemas/` | Pydantic request/response contracts |
| `app/utils/` | Pure functions — hashing, JWT, encryption, cache, analytics maths |
| `app/workers/` | Background job functions |

**Why services never raise `HTTPException`:** the same service is called from
HTTP routers, from AI tools, and from background jobs. A service that raises
HTTP errors would force a web framework into contexts that have no request.
Instead each service defines its own exception hierarchy, and the router maps
it — see `_handle_service_error` in `app/api/v1/endpoints/instagram.py`.

### Dependency injection

```mermaid
flowchart LR
    Route["Route handler"]
    GS["get_*_service()"]
    GR["get_*_repository()"]
    GDB["get_db()"]
    Session["SQLAlchemy Session"]

    Route -->|Depends| GS
    GS -->|Depends| GR
    GR -->|Depends| GDB
    GDB --> Session
```

One session per request, closed in a `finally`. Because the whole chain is
`Depends()`-based, tests swap the database by overriding a single provider
(`app.dependency_overrides[get_db]`).

---

## 3. Database design

Five tables. Full column reference in [DATABASE.md](DATABASE.md).

```mermaid
erDiagram
    users ||--o| instagram_accounts : "connects (1:1)"
    instagram_accounts ||--o{ instagram_media : "has"
    instagram_accounts ||--o{ account_insights : "snapshots"
    instagram_media ||--o{ media_insights : "snapshots"

    users {
        int id PK
        string username UK
        string email UK
        string hashed_password
        datetime created_at
    }
    instagram_accounts {
        int id PK
        int user_id FK "unique - one account per user"
        string instagram_user_id UK
        string access_token "Fernet-encrypted"
        datetime token_expires_at
    }
    instagram_media {
        int id PK
        int instagram_account_id FK
        string media_id UK
        string media_type
        int like_count
        int comments_count
        datetime posted_at
    }
    account_insights {
        int id PK
        int instagram_account_id FK
        string period
        jsonb metrics
        datetime fetched_at
    }
    media_insights {
        int id PK
        int media_id FK
        jsonb metrics
        datetime fetched_at
    }
```

Three design decisions worth knowing:

1. **Metrics are JSONB, not columns.** Meta adds, renames, and retires
   insight metrics between API versions. Storing `{metric_name: value}`
   means a new metric is a code change, not a migration.
2. **Insights are append-only snapshots**, never updated in place. That is
   what makes trends and follower growth computable — history is the data.
   "Current" always means the newest row for that entity.
3. **`account_insights.period` doubles as a discriminator.** `"day"` rows
   hold Graph API account insights; `"profile"` rows hold follower/media
   count snapshots written on every profile refresh. Reusing one table
   avoided a near-identical second one.

---

## 4. Authentication flow

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant AS as AuthService
    participant UR as UserRepository
    participant DB as PostgreSQL

    U->>API: POST /auth/register {username, email, password}
    API->>AS: create_user(...)
    AS->>AS: bcrypt hash (per-hash salt)
    AS->>UR: check username + email are free
    UR->>DB: SELECT
    AS->>UR: INSERT user
    API-->>U: 201 (never returns the hash)

    U->>API: POST /auth/login (email as "username", password)
    API->>AS: login(email, password)
    AS->>UR: get_by_email
    AS->>AS: bcrypt verify
    alt credentials valid
        AS->>AS: sign JWT {sub, exp, type:"access"}
        API-->>U: 200 {access_token, token_type}
    else invalid
        API-->>U: 401 (identical message for unknown email<br/>and wrong password)
    end

    U->>API: GET /analytics/... (Authorization: Bearer ...)
    API->>API: get_current_user: verify signature, exp, type
    API->>UR: load user by sub
    API-->>U: 200
```

**The `type` claim matters.** Every token this app issues carries one, and
every decoder verifies it. Without that check, any token signed with
`JWT_SECRET_KEY` would be interchangeable — including the Instagram OAuth
*state* token, which travels in a URL and therefore reaches browser history
and the `Referer` header sent to `facebook.com`. That was a real flaw, found
and fixed in the Milestone 9 review
([CODE_REVIEW.md § SEC-2](CODE_REVIEW.md#1-security-findings)).

Login and registration are rate limited (`RATE_LIMIT_AUTH`, 5/min) to blunt
brute force.

---

## 5. Instagram OAuth and Graph API integration

Meta does not expose Instagram Business data directly. The path runs through
Facebook Login for Business: a user's Facebook Page is what links to their
Instagram Business account.

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Frontend
    participant API as FastAPI
    participant IS as InstagramService
    participant G as Graph API
    participant DB as PostgreSQL

    FE->>API: GET /instagram/connect (Bearer)
    API->>IS: get_authorization_url(user_id)
    IS->>IS: sign state token {sub, exp 10m, type:"instagram_oauth_state"}
    API-->>FE: 200 {authorization_url}
    Note over FE: Client navigates the browser itself —<br/>the endpoint does not redirect

    FE->>G: browser → consent screen
    U->>G: approves
    G->>API: GET /instagram/callback?code=...&state=...
    Note over API: No Authorization header exists on<br/>a redirect — the signed state identifies the user

    API->>IS: connect_account(code, state)
    IS->>IS: verify state signature, expiry, type
    IS->>G: code → short-lived token
    IS->>G: short-lived → long-lived (~60d)
    IS->>G: GET /me/accounts (Facebook Pages)
    loop each Page
        IS->>G: page → instagram_business_account?
    end
    IS->>G: GET profile fields
    IS->>IS: Fernet-encrypt the token
    IS->>DB: INSERT instagram_account + profile snapshot
    API-->>FE: 200 (no token, no page id in the response)
```

Afterwards, `/instagram/media` and `/instagram/insights` fetch and persist
content and metrics using the stored token.

```mermaid
flowchart LR
    subgraph Client["InstagramGraphClient · app/integrations/"]
        direction TB
        C1["build_authorization_url"]
        C2["exchange_code_for_user_token"]
        C3["exchange_for_long_lived_token"]
        C4["get_facebook_pages"]
        C5["get_linked_instagram_account_id"]
        C6["get_profile / get_media"]
        C7["get_media_insights / get_account_insights"]
    end
    Svc["InstagramService"] --> Client --> Meta[("graph.facebook.com")]
```

The client is the only place that knows Graph API URLs, field lists, and
response shapes; it raises `InstagramAPIError`, which the service translates
into domain errors (`InstagramTokenExpiredError` for 401/403,
`InstagramOAuthError` otherwise). Adding a Graph API call means adding a
method here, not new URL-building in a service.

**Token security.** Access tokens are Fernet-encrypted before storage,
excluded from every response schema, and never interpolated into error
messages. Expiry is checked before use, with a clear "reconnect your account"
error rather than a failed upstream call.

---

## 6. Analytics pipeline

Ingestion and analysis are deliberately separate. Nothing in the analytics
layer calls the Graph API — it reads only what was already stored, so a
dashboard load is fast and cannot exhaust Meta rate limits.

```mermaid
flowchart TB
    subgraph Ingest["Ingestion — on demand"]
        I1["GET /instagram/media"] --> I2["upsert instagram_media"]
        I3["GET /instagram/insights"] --> I4["append media_insights<br/>+ account_insights"]
        I5["GET /instagram/profile"] --> I6["append profile snapshot"]
    end

    DB[("PostgreSQL")]
    I2 --> DB
    I4 --> DB
    I6 --> DB

    subgraph Analyse["Analytics — read only"]
        DB --> A1["latest insight per media<br/>(one window-function query)"]
        A1 --> A2["engagement rate =<br/>(likes+comments+shares+saves) / reach"]
        A2 --> A3["rank · bucket · aggregate"]
    end

    A3 --> O1["/analytics/account"]
    A3 --> O2["/analytics/media"]
    A3 --> O3["/analytics/trends"]
    A3 --> O4["/analytics/top-content"]
    A3 --> O5["/analytics/dashboard"]
```

**Engagement rate** is `(likes + comments + shares + saves) / reach × 100`,
normalized by reach rather than followers. A consequence worth internalizing:
a small post with high engagement can outrank a viral one. That is intended —
it measures how compelling content was to the people who saw it.

**Avoiding N+1.** `get_latest_by_media_ids` fetches the newest insight for
every media item in a single `ROW_NUMBER()` query rather than one query per
post.

**Dashboard sharing.** `get_dashboard` resolves the account once and computes
media analytics once, passing both into all three sections. Calling the three
public methods instead would repeat that work three times — measured at 13
queries versus 7.

---

## 7. AI agent workflow (LangGraph)

`POST /ai/chat` runs a tool-calling loop. The model decides *which* analytics
to fetch; it never decides *whose*.

```mermaid
flowchart TB
    Start([User message]) --> Agent

    Agent["agent node<br/>LLM with tools bound"]
    Tools["tools node<br/>executes requested calls"]

    Agent -->|tool_calls present| Tools
    Tools -->|results appended| Agent
    Agent -->|plain text reply| End([Response])

    subgraph Available["Tools — each closed over user_id"]
        direction TB
        T1["get_account_performance"]
        T2["get_media_performance"]
        T3["get_top_or_lowest_content"]
        T4["get_performance_trends"]
        T5["get_dashboard_summary"]
    end

    Tools -.-> Available
    Available -.->|only ever calls| AS["AnalyticsService"]
```

The graph is built in `app/integrations/ai_agent.py` from `StateGraph`,
`ToolNode`, and `tools_condition`; `AI_RECURSION_LIMIT` caps the loop.

**The security property.** `build_tools(analytics_service, user_id)` returns
closures. `user_id` is captured lexically, so it is *structurally absent*
from every tool's JSON schema — the model has no field in which to place a
different user. A prompt-injected `user_id` argument is dropped by the schema
binding before execution. This is asserted by tests at both the tool level
and over HTTP.

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant AIS as AIService
    participant Graph as LangGraph
    participant LLM as Gemini
    participant AS as AnalyticsService

    U->>API: POST /ai/chat {"message": "which reel did best?"}
    API->>AIS: chat(current_user.id, message)
    AIS->>AIS: build_tools(analytics_service, user_id)
    AIS->>Graph: invoke(system prompt + message)
    Graph->>LLM: messages + tool schemas
    LLM-->>Graph: tool_call get_top_or_lowest_content
    Graph->>AS: (user_id bound by closure)
    AS-->>Graph: real analytics JSON
    Graph->>LLM: tool result
    LLM-->>Graph: grounded natural-language answer
    API-->>U: 200 {response, tools_used}
```

---

## 8. Insights, recommendations, and reports

These differ from chat: the required data is known in advance, so there is no
decision for an agent to make. Each endpoint gathers analytics
deterministically, then makes **one** structured-output LLM call.

```mermaid
flowchart LR
    subgraph Deterministic["Computed in code"]
        D1["AnalyticsService data"]
        D2["posting-time breakdown"]
        D3["format breakdown"]
        D4["posting frequency"]
    end

    D1 & D2 & D3 & D4 --> Ctx["JSON context"]
    Ctx --> LLM["LLM · with_structured_output"]
    LLM --> Narr["Narrative text ONLY<br/>(InsightNarratives etc.)"]

    Narr --> Merge{{"Service merges"}}
    D1 --> Merge
    Merge --> Resp["Response: prose + real figures"]

    Resp --> Cache[("Redis<br/>CACHE_TTL_SECONDS")]
```

### Grounding: how AI output stays truthful

The schema handed to the model contains **only prose fields**. It has no
field for `followers_count`, no field for `top_performing_content`. Those are
attached afterwards by the service, straight from `AnalyticsService`. A
hallucinated number has nowhere to go.

This is verified rather than asserted: in the test suite the stub model
returns fixed prose containing no digits, yet every numeric field in the
response still matches the seeded database exactly.

Caching is per user and per parameter set. A cache miss costs one LLM call; a
hit costs none. If Redis is unavailable the cache **fails open** — the
request regenerates rather than failing.

### Credential resolution

Every AI code path obtains its Gemini key from a single service,
`AICredentialService.resolve_api_key(user_id)`:

1. the user's own stored key, Fernet-decrypted
2. `settings.GOOGLE_API_KEY`, as a development fallback
3. otherwise `AINotConfiguredError`, which routers map to `503`

It lives in one service rather than in the routers for three reasons. The
rule is business logic, so a router applying it would violate the layering.
`app/workers/jobs.py` has no router at all and would need a second copy.
And a security-sensitive precedence rule that exists in four places is one
that will eventually disagree with itself.

`AIService`, `InsightsService`, `RecommendationService` and `ReportService`
each take it as a constructor dependency, exactly as they take
`AnalyticsService` — no new injection pattern was invented for it.

A stored key that fails to decrypt raises rather than falling back to the
server key. Silently using a different account's quota because
`TOKEN_ENCRYPTION_KEY` was rotated is worse than a clear error the user can
fix by re-entering their key.

The cache is safe under this scheme without any extra work: its keys are
already user-scoped (`insights:{user_id}:{days}`), so a result generated with
one user's key can never be served to another.

---

## 9. Background jobs

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant Q as Redis (RQ)
    participant W as Worker process
    participant DB as PostgreSQL

    U->>API: POST /jobs/reports/weekly
    API->>Q: enqueue(generate_report_job, user_id, meta={user_id})
    API-->>U: 202 {job_id}

    W->>Q: dequeue
    W->>DB: opens its own session
    W->>W: generate report
    W->>Q: store result

    U->>API: GET /jobs/{job_id}
    API->>Q: fetch job
    API->>API: verify job.meta.user_id == caller
    API-->>U: 200 {status, result}
```

The job builds its own session and service graph rather than using FastAPI
dependency injection — a worker process has no request to inject from.
Ownership is recorded in job metadata and checked on read, so a leaked job ID
cannot expose another user's analytics.

---

## 10. Cross-cutting concerns

```mermaid
flowchart TB
    Req([Request]) --> M1
    M1["RequestLoggingMiddleware<br/>request id · duration · status"]
    M2["SecurityHeadersMiddleware<br/>nosniff · DENY · HSTS · Referrer-Policy"]
    M3["CORSMiddleware"]
    M4["SlowAPIMiddleware<br/>rate limits"]
    M1 --> M2 --> M3 --> M4 --> Route["Route handler"]
    Route --> Resp([Response])

    Route -.->|unhandled exception| EH["Exception handler<br/>log full trace · return generic 500"]
```

Middleware is registered in reverse (last added runs outermost); the order
above is the effective one. Request logging wraps everything so it records
the full duration including rate-limit rejections.

**Configuration** is a single validated Pydantic `Settings` object. When
`ENVIRONMENT=production` it refuses to start with `DEBUG=true`, a short
`JWT_SECRET_KEY`, or wildcard CORS — misconfiguration fails loudly at boot
rather than silently at runtime.

**Failure isolation** is deliberate: Redis is used for caching and jobs, but
losing it degrades rather than breaks. Cache reads fall through to
regeneration, and rate limiting is intentionally in-process precisely because
the library used does not fail open on storage loss
([DEPLOYMENT.md § Rate limiting](DEPLOYMENT.md#6-rate-limiting)).

---

## End-to-end walkthrough

Following `GET /api/v1/analytics/dashboard` all the way down:

1. **Middleware** — a request ID is generated; security headers and CORS are
   applied; the rate limiter checks the caller's IP bucket.
2. **Routing** — FastAPI matches `app/api/v1/endpoints/analytics.py`.
3. **Dependencies resolve**, innermost first: `get_db()` opens a session →
   four repositories are constructed on it → `get_analytics_service()`
   assembles them. Separately, `get_current_user()` validates the bearer
   token (signature, expiry, `type` claim) and loads the `User`.
4. **Handler** calls `analytics_service.get_dashboard(current_user.id)` and
   nothing else — no logic, no queries.
5. **Service** resolves the connected account (404 if none), then computes
   media analytics **once** and shares it across the account, top-content,
   and trend sections.
6. **Repositories** issue the SQL, including the single window-function query
   that fetches the latest insight per media item.
7. **Calculation utilities** (`app/utils/analytics_calculations.py`) do the
   arithmetic as pure functions — no I/O, exhaustively unit tested.
8. **Response** is validated against `DashboardResponse`; FastAPI serializes
   it.
9. **Unwinding** — the session closes in `get_db`'s `finally`; the logging
   middleware emits one structured line with status and duration; the metrics
   instrumentation records the observation.

The other flows in brief:

| Flow | Path |
| --- | --- |
| **Authentication** | `/auth/register` hashes and stores → `/auth/login` verifies and signs a typed JWT → `get_current_user` validates it on every protected route ([§4](#4-authentication-flow)) |
| **Instagram OAuth** | `/instagram/connect` mints a signed state → Meta consent → `/instagram/callback` exchanges the code, discovers the account, encrypts and stores the token ([§5](#5-instagram-oauth-and-graph-api-integration)) |
| **Analytics** | Ingestion writes append-only snapshots; the analytics layer reads them and derives rates, rankings, and trends ([§6](#6-analytics-pipeline)) |
| **AI agent** | A LangGraph loop picks tools; the tools query `AnalyticsService` with the caller's ID bound by closure ([§7](#7-ai-agent-workflow-langgraph)) |
| **Recommendations** | Deterministic breakdowns computed in code, narrated by one structured LLM call, merged with real figures by the service ([§8](#8-insights-recommendations-and-reports)) |
