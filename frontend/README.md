# Instalysis — frontend

React + TypeScript + Vite client for the Instalysis Instagram analytics API.

## Running it

The backend must be running first (see [SETUP.md](../Documents/SETUP.md)).

```bash
npm install
```

```bash
npm run dev
```

Opens on **http://localhost:3000**.

The port is pinned with `strictPort: true` and is not arbitrary: the API's
`CORS_ALLOWED_ORIGINS` defaults to `http://localhost:3000`, and because the
backend sets `allow_credentials=True`, a wildcard origin is not permitted by
the CORS spec. If port 3000 is taken, Vite fails loudly rather than silently
moving to 3001 and producing CORS errors that look like auth bugs.

Copy `.env.example` to `.env` if the API is not at `http://localhost:8000`.

## Structure

```
src/
  api/          typed client, one module per backend router
  auth/         token storage, session context, expiry handling
  onboarding/   the AI-key + Instagram-connection status hook
  routes/       route guards
  pages/        one directory per area
  components/   layout, UI primitives, hand-rolled SVG charts
  styles/       design tokens, base styles, grid
  lib/          formatting and JWT helpers
```

## Things that will surprise you

**Login is form-encoded, and the email goes in a field named `username`.**
The backend uses FastAPI's `OAuth2PasswordRequestForm`. This is hidden inside
`api/auth.ts` — no page component should ever need to know.

**There are two kinds of 401.** An expired session and an expired *Instagram*
token both return 401, and only the first should sign the user out. They are
told apart by the `WWW-Authenticate: Bearer` header, which the auth dependency
sets and the Instagram path does not — see `isSessionExpiry` in
`api/client.ts`. Getting this wrong logs people out whenever their Instagram
connection lapses.

**There is no refresh token.** Access tokens last 30 minutes, full stop.
`AuthContext` signs out proactively ~30 seconds before expiry so a
half-written chat message is not lost to a surprise 401. Requests are never
retried on 401 — a retry would fail identically.

**`GET /instagram/media` and `/instagram/insights` are writes.** They pull
from the Graph API and persist to the database. They are wired to an explicit
"Sync from Instagram" button in Settings and must never run on page load.

**Nullable fields are `| null`, not optional.** The API returns `null` for
"never measured" rather than `0`, and the formatters in `lib/format.ts`
render that as an em-dash. Collapsing null to 0 would invent a measurement.

## Routing

```
/login, /register            redirect away if already signed in
/onboarding/gemini           step 1 — the user's own Gemini API key
/onboarding/instagram        step 2 — Meta OAuth, both directions
/settings                    auth only, deliberately NOT onboarding-gated
everything else              auth + completed onboarding + app shell
```

`/settings` sits outside the onboarding gate on purpose: it is where a
rejected key or a broken Instagram connection gets fixed, and gating it would
trap the user in a redirect loop.

## Design system

Swiss / International Typographic Style, defined in `styles/tokens.css`: a
12-column grid with a constant 24px gutter, a seven-step type scale on a 1.25
ratio, three weights, near-monochrome with a single accent, and hairline rules
doing all the separating.

Deliberately absent:

- **no `border-radius`** (`--radius: 0`; the single usage resets browser defaults on form controls)
- **no `box-shadow`** (`--shadow: none`)
- **no gradients**
- **no justified text** — flush left, ragged right throughout
- **no chart library** — charts are hand-rolled SVG in `components/charts/`,
  because every library ships gridlines, shadowed tooltips and legend dots
  that would have to be switched off one at a time

Direction is shown with a glyph *and* the accent, never colour alone. The
focus ring is the one blue in the system, so it can never be confused with the
accent red.

## Checks

```bash
npm run build
```

Runs `tsc -b` and then the production build. Both must be clean.
