import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import "../components/layout/layout.css";
import { Button, Callout, Field } from "../components/ui";

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const sessionExpired = params.get("reason") === "expired";
  const next = params.get("next");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await signIn(email, password);
      navigate(next ?? "/dashboard", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Could not reach the server. Is the API running?",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="centered">
      <div className="centered__panel glass">
        <div className="centered__brand">Instalysis</div>

        <div className="stack">
          <div>
            <span className="eyebrow">Sign in</span>
            <h1 style={{ marginTop: "var(--space-2)" }}>Welcome back</h1>
          </div>

          {sessionExpired && (
            <Callout title="Session expired">
              Sessions last 30 minutes. Sign in again to continue.
            </Callout>
          )}

          {error && <Callout tone="error">{error}</Callout>}

          <form className="stack" onSubmit={handleSubmit}>
            <Field
              label="Email"
              type="email"
              value={email}
              autoComplete="email"
              required
              onChange={(event) => setEmail(event.target.value)}
            />
            <Field
              label="Password"
              type="password"
              value={password}
              autoComplete="current-password"
              required
              onChange={(event) => setPassword(event.target.value)}
            />
            <div>
              <Button type="submit" variant="primary" loading={submitting}>
                Sign in
              </Button>
            </div>
          </form>

          <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
            No account yet? <Link to="/register">Create one</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
