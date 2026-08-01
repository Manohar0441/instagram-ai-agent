import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { setKey } from "../../api/ai";
import { ApiError } from "../../api/client";
import "../../components/layout/layout.css";
import { Button, Callout, Field } from "../../components/ui";
import { AI_KEY_QUERY } from "../../onboarding/useOnboardingStatus";

export function GeminiKeyPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await setKey(apiKey.trim());
      await queryClient.invalidateQueries({ queryKey: AI_KEY_QUERY });
      navigate("/onboarding/instagram", { replace: true });
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
      <div className="centered__panel centered__panel--wide">
        <div className="centered__brand">Instalysis</div>

        <div className="stack-lg">
          <div>
            <div className="step-marker">Step 1 of 2</div>
            <h1>Add your Gemini API key</h1>
            <p className="muted" style={{ marginTop: "var(--space-4)" }}>
              Instalysis uses Google Gemini to write insights, recommendations
              and reports from your analytics. The key stays yours — it is
              encrypted before it is stored and is never shown back to you or
              sent anywhere except Google.
            </p>
          </div>

          {error && <Callout tone="error">{error}</Callout>}

          <form className="stack" onSubmit={handleSubmit}>
            <Field
              label="Gemini API key"
              type="password"
              value={apiKey}
              required
              autoComplete="off"
              spellCheck={false}
              placeholder="AQ.Ab8…"
              hint={
                <>
                  Create a free key at{" "}
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    aistudio.google.com/apikey
                  </a>
                  . The free tier is enough to run Instalysis.
                </>
              }
              onChange={(event) => setApiKey(event.target.value)}
            />
            <div className="row">
              <Button type="submit" variant="primary" loading={submitting}>
                Save and continue
              </Button>
            </div>
          </form>

          <div className="rule" style={{ paddingTop: "var(--space-4)" }}>
            <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
              You can change or remove this key at any time from Settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
