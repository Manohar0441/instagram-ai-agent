# Developer Guide

How to work in this codebase: the rules it follows, and step-by-step recipes
for adding each kind of component.

Read [ARCHITECTURE.md](ARCHITECTURE.md) first if you have not — this guide
assumes you know the layering.

---

## The one rule

> **Route → Service → Repository → SQLAlchemy → PostgreSQL**

Nothing skips a layer, and nothing reaches upward.

| Layer | Must | Must not |
| --- | --- | --- |
| **Route** | Validate input, inject dependencies, map exceptions to status codes | Contain business logic or database access |
| **Service** | Hold business rules, orchestrate, own transactions | Import `fastapi`, raise `HTTPException`, write SQL |
| **Repository** | Contain every SQLAlchemy query | Make business decisions or commit |
| **Model** | Define tables | Anything else |

**Why services never raise `HTTPException`:** the same service is called from
HTTP routes, from AI tools, and from background jobs. A worker process has no
request — a service that raised HTTP errors would drag a web framework into a
context with no HTTP in it. Services raise their own exceptions; routes
translate them.

```python
# app/services/user_service.py
class UserServiceError(Exception): ...
class DuplicateEmailError(UserServiceError): ...

# app/api/v1/endpoints/auth.py
except DuplicateEmailError as exc:
    raise HTTPException(status_code=409, detail=str(exc)) from exc
```

---

## Folder responsibilities

| Path | Holds | Add here when… |
| --- | --- | --- |
| `app/api/v1/endpoints/` | Route handlers | Adding an endpoint |
| `app/api/health.py` | Operational probes | Adding a health signal |
| `app/core/` | Settings, logging, middleware, rate limiter, exception handlers | Adding cross-cutting behavior |
| `app/database/` | Engine, session factory, `Base` | Rarely |
| `app/dependencies/` | FastAPI DI providers | Adding a repository or service |
| `app/integrations/` | Outbound clients (Graph API, LangGraph, Redis, queue) | Talking to a new external system |
| `app/models/` | SQLAlchemy models | Adding a table |
| `app/repositories/` | Database queries | Adding a query |
| `app/schemas/` | Pydantic request/response models | Adding an API contract |
| `app/services/` | Business logic, prompts, AI tools | Adding behavior |
| `app/utils/` | Pure functions | Adding logic with no I/O |
| `app/workers/` | Background job functions | Adding an async task |

---

## Coding standards

Conventions this codebase already follows — match them.

**Typing.** Annotate everything. Use modern syntax: `str | None`, `list[str]`,
`dict[str, Any]`.

**Docstrings.** One line on every public function, class, and module. Use the
body to explain *why*, not *what* — the code says what.

```python
def calculate_engagement_rate(engagements: int, reach: int | None = None) -> float | None:
    """Engagement rate as a percentage of reach.

    Returns None when there is no denominator, rather than dividing by zero
    or fabricating a rate from incomplete data.
    """
```

**Comments** earn their place by explaining a non-obvious decision:

```python
# int() is inside the try deliberately: a token with a well-formed but
# non-numeric "sub" is an invalid credential (401), not an internal error.
```

**`None` means "unknown".** Never substitute `0` for missing data — a post
with no reach data is not a post with zero reach. This distinction runs
through the whole analytics layer.

**Naming.** `snake_case` for functions and variables, `PascalCase` for
classes, `_leading_underscore` for private helpers. Repository methods read
as queries (`get_by_email`, `list_by_account_id`); service methods read as
actions (`connect_account`, `generate_report`).

**Imports.** Standard library, then third party, then `app.*` — each group
separated by a blank line, alphabetized within the group.

**Line length.** ~100 characters.

**No secrets in code.** Everything configurable lives in
`app/core/settings.py` and is read from the environment.

---

## Recipes

### Add an endpoint

**1. Schema** — `app/schemas/`:

```python
class WidgetResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
```

**2. Route** — `app/api/v1/endpoints/widgets.py`:

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_widget_service
from app.models.user import User
from app.schemas.widget import WidgetResponse
from app.services.widget_service import WidgetNotFoundError, WidgetService

router = APIRouter(prefix="/widgets", tags=["Widgets"])

CurrentUser = Annotated[User, Depends(get_current_user)]
WidgetServiceDependency = Annotated[WidgetService, Depends(get_widget_service)]


@router.get(
    "/{widget_id}",
    response_model=WidgetResponse,
    summary="Get widget",
    description="Return a widget belonging to the current user.",
    operation_id="getWidget",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No such widget."},
    },
)
def get_widget(
    widget_id: int,
    current_user: CurrentUser,
    widget_service: WidgetServiceDependency,
) -> WidgetResponse:
    """Return a widget through the service layer."""
    try:
        return WidgetResponse.model_validate(
            widget_service.get_widget(current_user.id, widget_id)
        )
    except WidgetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

**3. Register** in `app/api/v1/router.py`:

```python
from app.api.v1.endpoints import ai, analytics, auth, insights, instagram, jobs, users, widgets
api_router.include_router(widgets.router)
```

**4. Add it to the authorization matrix** in
`tests/api/test_authorization.py` — either `PROTECTED_ENDPOINTS` or
`PUBLIC_ENDPOINTS`. This is what prevents an endpoint being exposed by
accident.

**Checklist**

- [ ] `summary`, `description`, `operation_id`, and documented `responses` (they render in Swagger)
- [ ] Scoped to `current_user` — never trust an ID from the client alone
- [ ] Returns `404`, not `403`, for another user's resource
- [ ] `@limiter.limit(settings.RATE_LIMIT_STRICT)` if it is expensive — and then the handler needs a `request: Request` parameter
- [ ] Tests: happy path, validation failure, not-found, cross-user isolation

---

### Add a service

`app/services/widget_service.py`:

```python
from app.repositories.widget_repository import WidgetRepository


class WidgetServiceError(Exception):
    """Base exception for widget failures."""


class WidgetNotFoundError(WidgetServiceError):
    """Raised when a widget does not exist or belongs to another user."""


class WidgetService:
    """Coordinate widget business rules and persistence."""

    def __init__(self, widget_repository: WidgetRepository) -> None:
        self.widget_repository = widget_repository

    def get_widget(self, user_id: int, widget_id: int) -> Widget:
        """Return a widget, provided it belongs to the given user."""
        widget = self.widget_repository.get_by_id(widget_id)
        if widget is None or widget.user_id != user_id:
            # Same error either way: distinguishing them would confirm the
            # widget exists, which is a resource-enumeration oracle.
            raise WidgetNotFoundError(f"Widget {widget_id} was not found.")
        return widget
```

Register a provider in `app/dependencies/services.py`:

```python
def get_widget_service(
    widget_repository: WidgetRepository = Depends(get_widget_repository),
) -> WidgetService:
    """Provide a widget service with its repository dependencies."""
    return WidgetService(widget_repository)
```

Rules: a base exception plus specific subclasses; take dependencies through
`__init__`, never construct them inside; own transaction boundaries by
calling `commit()` after a successful write.

---

### Add a repository

`app/repositories/widget_repository.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.widget import Widget
from app.repositories.base import BaseRepository


class WidgetRepository(BaseRepository[Widget]):
    """Handle persistence operations specific to widgets."""

    def __init__(self, db: Session) -> None:
        super().__init__(Widget, db)

    def list_by_user_id(self, user_id: int) -> list[Widget]:
        """Return a user's widgets, newest first."""
        statement = (
            select(Widget).where(Widget.user_id == user_id).order_by(Widget.created_at.desc())
        )
        return list(self.db.scalars(statement).all())
```

`BaseRepository` already provides `create`, `get_by_id`, `get_all`, and
`delete`.

Register in `app/dependencies/repositories.py`:

```python
def get_widget_repository(db: Session = Depends(get_db)) -> WidgetRepository:
    """Provide a widget repository backed by the request database session."""
    return WidgetRepository(db)
```

**Watch for N+1.** If you find yourself querying inside a loop, fetch in bulk
instead — `MediaInsightRepository.get_latest_by_media_ids` shows the pattern
using a window function for "latest row per group".

---

### Add a database model

**1. Model** — `app/models/widget.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

**2. Register** in `app/models/__init__.py` — Alembic will not see it
otherwise:

```python
from app.models.widget import Widget
```

**3. Migrate**:

```bash
alembic revision --autogenerate -m "add widgets table"
```

Review the generated file, then:

```bash
alembic upgrade head
```

**Conventions:** plural snake_case table names; index every foreign key you
filter by; `ondelete="CASCADE"` unless you have a reason not to; timezone-aware
`DateTime(timezone=True)`; JSONB for shapes that evolve, with
`.with_variant(JSON(), "sqlite")` so tests still run.

See [DATABASE.md § Migrations](DATABASE.md#migrations) for the rules on
`NOT NULL` columns and writing `downgrade()`.

---

### Add an AI tool

Tools are how the chat agent reaches data. Add one to `build_tools` in
`app/services/ai_tools.py`:

```python
def build_tools(analytics_service: AnalyticsService, user_id: int) -> list[BaseTool]:

    @tool
    def get_best_posting_day() -> str:
        """Return the weekday on which this account's posts perform best.

        Use this for questions about *when* to post.
        """
        try:
            result = analytics_service.get_posting_day_breakdown(user_id)
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return result.model_dump_json()

    return [..., get_best_posting_day]
```

**Non-negotiable: never add `user_id` as a tool parameter.** It is captured
by closure precisely so it is *structurally absent* from the tool's JSON
schema — the model has no field in which to name a different user, and an
injected `user_id` argument is dropped by the schema binding. Making it a
parameter would let a prompt-injected value reach the service layer.

Other rules:

- **The docstring is the prompt.** The model chooses tools by reading it —
  say what it returns *and when to use it*.
- **Call only services**, never a repository or the database.
- **Return a string** (`model_dump_json()` is the convention).
- **Catch `InstagramAccountNotConnectedError`** and return the message so the
  agent can explain it conversationally, rather than raising.

Add a test asserting the new tool's schema has no `user_id` — the existing
one iterates all tools, so it covers new ones automatically.

---

### Add a LangGraph node

The graph lives in `app/integrations/ai_agent.py`. Today it is the standard
agent ↔ tools loop. To insert a step — say, a guardrail before the model:

```python
def build_agent_graph(llm: BaseChatModel, tools: list[BaseTool]) -> CompiledStateGraph:
    llm_with_tools = llm.bind_tools(tools)

    def screen_input(state: MessagesState) -> dict:
        """Reject anything that shouldn't reach the model."""
        return {"messages": []}          # no-op; add real logic here

    def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("screen", screen_input)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))

    graph.set_entry_point("screen")
    graph.add_edge("screen", "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()
```

A node takes state and returns a **partial** state update; `MessagesState`
appends to `messages` rather than replacing it. Use
`add_conditional_edges` for branching, and keep `AI_RECURSION_LIMIT` in mind
— every extra node consumes budget from the same allowance.

> Adding a *tool* does not require touching the graph. Only change the graph
> when you need a genuinely new step in the workflow.

---

### Add a background job

**1. Job function** — `app/workers/jobs.py`:

```python
def rebuild_widget_cache_job(user_id: int) -> dict[str, Any]:
    """Rebuild a user's widget cache in the background.

    Workers run in a separate process with no request context, so this
    builds its own session and service graph rather than using FastAPI DI.
    """
    db = SessionLocal()
    try:
        service = WidgetService(WidgetRepository(db))
        return service.rebuild_cache(user_id).model_dump(mode="json")
    finally:
        db.close()
```

**2. Enqueue** from a service, tagging ownership:

```python
job = self.queue.enqueue(
    rebuild_widget_cache_job,
    user_id,
    meta={"user_id": user_id},        # checked on read - do not omit
    job_timeout=DEFAULT_JOB_TIMEOUT_SECONDS,
)
```

Rules: build your own session; return JSON-serializable data (RQ pickles
results); always set `meta={"user_id": ...}` so `get_job_status` can refuse
another user's job; jobs must be importable — a function defined in
`__main__` cannot be dispatched to a worker.

---

### Add a configuration setting

In `app/core/settings.py`:

```python
WIDGET_REFRESH_SECONDS: int = 300
```

Then document it in `.env.example` with a comment explaining what it does and
what changing it costs. Unknown `.env` keys are rejected, so anything you add
to `.env` must exist here too.

If it must be safe in production, extend `_validate_production_settings` so
the app refuses to boot when it is misconfigured — failing at startup beats
failing under load.

---

## Best practices

**Add the failure case first.** Most of this codebase's exception types exist
because a missing connection, an expired token, or an unreachable dependency
was thought about before the happy path was written.

**Prefer honest nulls to invented numbers.** `completion_rate` is `null`
because computing it would require data the Graph API does not reliably
return. Reporting an estimate as fact is worse than reporting nothing.

**Let optional dependencies fail open.** Cache reads fall back to
regenerating; a Redis outage costs latency, not availability. Ask what
happens to a request when a dependency disappears.

**Keep ingestion separate from analysis.** Analytics reads only stored data.
Adding a Graph API call to an analytics path would couple dashboard latency
to Meta's uptime and rate limits.

**Watch for repeated work across an aggregate.** `/analytics/dashboard`
originally re-fetched the same data three times, once per section — 13
queries where 7 do. If an endpoint composes several others, share the fetch.

**When you fix a bug, add the test that would have caught it.** Every
security fix in [CODE_REVIEW.md](CODE_REVIEW.md) has a matching regression
test.

**Run the suite before you push.**

```bash
pytest
```

---

## Where to look

| Task | Start at |
| --- | --- |
| Trace a request end to end | [ARCHITECTURE.md § Walkthrough](ARCHITECTURE.md#end-to-end-walkthrough) |
| Understand an endpoint's contract | [API_DOCUMENTATION.md](API_DOCUMENTATION.md) |
| Understand the schema | [DATABASE.md](DATABASE.md) |
| Write or run tests | [TESTING.md](TESTING.md) |
| Diagnose a failure | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| See known issues and trade-offs | [CODE_REVIEW.md](CODE_REVIEW.md) |
