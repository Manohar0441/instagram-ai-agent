import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import "../components/layout/layout.css";
import { Button, Callout, Field } from "../components/ui";

export function RegisterPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    full_name: "",
    username: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update(field: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [field]: event.target.value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await register(form);
      // Sign straight in so the user lands in onboarding rather than being
      // asked for the credentials they just chose.
      await signIn(form.email, form.password);
      navigate("/onboarding/gemini", { replace: true });
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
      <div className="centered__panel">
        <div className="centered__brand">Instalysis</div>

        <div className="stack">
          <div>
            <span className="eyebrow">Create account</span>
            <h1 style={{ marginTop: "var(--space-2)" }}>Get started</h1>
          </div>

          {error && <Callout tone="error">{error}</Callout>}

          <form className="stack" onSubmit={handleSubmit}>
            <Field
              label="Full name"
              value={form.full_name}
              autoComplete="name"
              required
              maxLength={200}
              onChange={update("full_name")}
            />
            <Field
              label="Username"
              value={form.username}
              autoComplete="username"
              required
              maxLength={100}
              onChange={update("username")}
            />
            <Field
              label="Email"
              type="email"
              value={form.email}
              autoComplete="email"
              required
              onChange={update("email")}
            />
            <Field
              label="Password"
              type="password"
              value={form.password}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={72}
              hint="At least 8 characters."
              onChange={update("password")}
            />
            <div>
              <Button type="submit" variant="primary" loading={submitting}>
                Create account
              </Button>
            </div>
          </form>

          <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
            Already registered? <Link to="/login">Sign in</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
