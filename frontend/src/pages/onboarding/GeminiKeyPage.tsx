import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { setKey } from "../../api/ai";
import { ApiError } from "../../api/client";
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
    <div className="swiss-layout">
      {/* LEFT COLUMN: Structural Sidebar */}
      <aside className="swiss-sidebar">
        <div className="swiss-sidebar-top">
          <div className="swiss-brand">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 15L7.5 5H11.5L7 15H3Z" fill="#da291c"/>
              <path d="M11 19L15.5 9H19.5L15 19H11Z" fill="#da291c"/>
              <rect x="6" y="12" width="12" height="2.5" fill="#da291c"/>
            </svg>
            Instalysis.
          </div>
        </div>

        <div className="swiss-crosshair-container">
          <div className="crosshair-line-h"></div>
          <div className="crosshair-line-v"></div>
          <div className="crosshair-node"></div>
        </div>

        <div className="swiss-sidebar-bottom">
          <p className="sidebar-quote">
            <strong>Bring your own key.</strong>
            <br />
            Your analytics, billed to your account.
          </p>
        </div>
      </aside>

      {/* RIGHT COLUMN: Main Content */}
      <main className="swiss-main">
        <div className="swiss-content">
          <div className="swiss-header-block">
            <span className="step-marker">Step 1 of 2</span>
            <h1 className="swiss-title">Add your Gemini key</h1>
            <p className="swiss-subtitle">
              Instalysis uses Google Gemini to write insights, recommendations
              and reports from your analytics. The key stays yours — it is
              encrypted before it is stored and never shown back to you or
              sent anywhere except Google.
            </p>
          </div>

          {error && (
            <div className="swiss-callout swiss-callout--error">
              <strong>Error:</strong> {error}
            </div>
          )}

          <form className="swiss-form" onSubmit={handleSubmit}>
            <div className="swiss-field-group">
              <label htmlFor="apiKey">Gemini API key</label>
              <div className="swiss-input-wrapper">
                <span className="icon-left">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="7.5" cy="15.5" r="5.5"></circle>
                    <path d="M21 2l-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"></path>
                  </svg>
                </span>
                <input
                  id="apiKey"
                  type="password"
                  value={apiKey}
                  placeholder="AQ.Ab8…"
                  autoComplete="off"
                  spellCheck={false}
                  required
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </div>
              <p className="field__hint">
                Create a free key at{" "}
                <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer noopener">
                  aistudio.google.com/apikey
                </a>
                . The free tier is enough to run Instalysis.
              </p>
            </div>

            <button type="submit" className="swiss-button" disabled={submitting}>
              <span>{submitting ? "Saving..." : "Save and continue"}</span>
              <svg className="button-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </form>

          <div className="rule" style={{ paddingTop: "var(--space-4)" }}>
            <p className="muted text-xs">
              You can change or remove this key at any time from Settings.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
