import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import "../styles/swiss.css";

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

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
          : "Could not reach the server. Is the API running?"
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

        {/* Precise Swiss Crosshair with Square Node */}
        <div className="swiss-crosshair-container">
          <div className="crosshair-line-h"></div>
          <div className="crosshair-line-v"></div>
          <div className="crosshair-node"></div>
        </div>

        <div className="swiss-sidebar-bottom">
          <p className="sidebar-quote">
            <strong>Built for clarity.</strong>
            <br />
            Designed for performance.
          </p>
        </div>
      </aside>

      {/* RIGHT COLUMN: Main Content */}
      <main className="swiss-main">
        {/* Top Right Language Selector */}
        <div className="swiss-top-right">
          <button className="lang-selector" type="button">
            <span>EN</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
        </div>

        <div className="swiss-content">
          <div className="swiss-header-block">
            <h1 className="swiss-title">Sign in</h1>
            <p className="swiss-subtitle">Welcome back to your account.</p>
          </div>

          {sessionExpired && (
            <div className="swiss-callout">
              <strong>Session expired.</strong> Please sign in again.
            </div>
          )}

          {error && (
            <div className="swiss-callout swiss-callout--error">
              <strong>Error:</strong> {error}
            </div>
          )}

          <form className="swiss-form" onSubmit={handleSubmit}>
            {/* Email Field */}
            <div className="swiss-field-group">
              <label htmlFor="email">Email</label>
              <div className="swiss-input-wrapper">
                <span className="icon-left">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="4" width="20" height="16" rx="2"></rect>
                    <path d="M2 7l10 7 10-7"></path>
                  </svg>
                </span>
                <input
                  id="email"
                  type="email"
                  value={email}
                  placeholder="Enter your email"
                  autoComplete="email"
                  required
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
            </div>
            
            {/* Password Field */}
            <div className="swiss-field-group">
              <label htmlFor="password">Password</label>
              <div className="swiss-input-wrapper">
                <span className="icon-left">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0110 0v4"></path>
                  </svg>
                </span>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button 
                  type="button" 
                  className="icon-right" 
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Toggle password visibility"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    {showPassword ? (
                      <>
                        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                      </>
                    ) : (
                      <>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </>
                    )}
                  </svg>
                </button>
              </div>
            </div>

            <button type="submit" className="swiss-button" disabled={submitting}>
              <span>{submitting ? "Signing in..." : "Sign in"}</span>
              <svg className="button-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </form>

          <div className="swiss-divider">
            <span>or</span>
          </div>

          <footer className="swiss-footer">
            <span className="footer-text">No account yet?</span>{" "}
            <Link to="/register" className="swiss-link">
              <span>Create one</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </Link>
          </footer>
        </div>
      </main>
    </div>
  );
}