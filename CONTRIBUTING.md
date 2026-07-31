# Contributing

Thanks for your interest in the project. This document covers the workflow;
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) covers the architectural rules a
change is expected to respect.

---

## Getting set up

Follow [SETUP.md](SETUP.md), then confirm the suite is green before you
change anything:

```bash
pytest
```

Expect `289 passed`. If it fails on a clean checkout, that is a bug worth
reporting on its own.

---

## Workflow

**1. Open an issue first** for anything beyond a small fix. It is cheaper to
agree on an approach than to rework a finished branch.

**2. Branch** from `master`:

```bash
git checkout -b feat/short-description
```

Prefixes: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`.

**3. Make the change**, following the layering in
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md). Keep it focused — an unrelated
refactor in the same branch makes review harder and history less useful.

**4. Add tests.** A change without one is unlikely to be merged:

| Change | Expected coverage |
| --- | --- |
| New endpoint | API tests: happy path, validation failure, auth required, cross-user isolation — plus an entry in the `tests/api/test_authorization.py` matrix |
| New service method | Integration tests, including the failure paths |
| New pure function | Unit tests, including edge cases (empty input, `None`, zero) |
| Bug fix | A regression test that fails before the fix and passes after |

**5. Run the suite:**

```bash
pytest
```

**6. Commit** with a clear message:

```
feat(analytics): add weekday breakdown to trends

Adds average engagement grouped by weekday so the recommendations
engine can suggest posting days from real data rather than generic advice.

Closes #42
```

Use the imperative mood ("add", not "added"). Explain *why* in the body; the
diff already shows what.

**7. Open a pull request** describing what changed, why, how you tested it,
and anything you deliberately left out.

---

## What gets merged easily

- Tests included, and the full suite green
- The layering intact — routes thin, services free of HTTP, queries only in repositories
- New endpoints scoped to the authenticated user, returning `404` (not `403`) for another user's resources
- Public functions typed and given a one-line docstring
- Non-obvious decisions explained in a comment
- Documentation updated when behavior changes
- New config added to both `app/core/settings.py` and `.env.example`

## What causes churn in review

- Database queries in a route handler
- `HTTPException` raised from a service
- `user_id` accepted as an AI tool parameter (see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#add-an-ai-tool) — it is a security boundary)
- Missing data substituted with `0` instead of `null`
- Secrets or environment-specific values hardcoded
- Unrelated changes bundled into one branch
- Tests asserting things the environment cannot honestly verify

---

## Reporting bugs

Include:

1. What you expected, and what happened instead
2. Steps to reproduce
3. The **`X-Request-ID`** from the response header — it appears in the server logs for that exact request
4. Relevant log lines (`LOG_FORMAT=text` is easier to read)
5. Environment: OS, Python version, Docker or not

Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first — most setup problems
are covered there with a fix.

**Never paste secrets** into an issue: no `.env` contents, API keys, JWTs, or
Instagram tokens. Redact before posting.

### Security issues

Do not open a public issue for a vulnerability. Contact the maintainer
privately so it can be fixed before disclosure.

---

## Proposing features

Open an issue describing the problem you are solving, not just the feature
you want. Check the [roadmap](README.md#roadmap) first — the known gaps are
listed there, along with why some things were left undone.

Especially welcome: verifying the Instagram Graph API metric names against a
live Meta app (see [CODE_REVIEW.md](CODE_REVIEW.md#5-recommendations-not-acted-on)),
Instagram token refresh, scheduled ingestion, and a CI pipeline.

---

## Code of conduct

Be respectful and constructive. Assume good faith, critique the code rather
than the person, and remember that everyone reviewing your work is doing so
voluntarily.

---

## License

Contributions are made under the [MIT License](LICENSE).
