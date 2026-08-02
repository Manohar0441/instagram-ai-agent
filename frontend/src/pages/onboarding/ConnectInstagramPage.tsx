import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getConnectUrl } from "../../api/instagram";
import { INSTAGRAM_PROFILE_QUERY } from "../../onboarding/useOnboardingStatus";

/* The backend sends stable codes rather than prose so the copy lives here,
 * where it can be written for the person reading it. */
const ERROR_COPY: Record<string, string> = {
  access_denied:
    "You declined the permission request. Instalysis needs read access to your Instagram insights to show any analytics.",
  missing_parameters:
    "Instagram sent an incomplete response. Start the connection again.",
  invalid_state:
    "That connection link expired — they are valid for 10 minutes. Start again.",
  already_connected:
    "An Instagram account is already connected. Disconnect it in Settings before connecting a different one.",
  token_expired:
    "Instagram's authorization expired before the connection finished. Please try again.",
  not_configured:
    "Instagram integration is not configured on the server. The INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET settings are missing.",
  provider_error:
    "Instagram rejected the request. This is usually temporary — try again in a moment.",
  unknown_error: "Something went wrong connecting your account. Please try again.",
};

export function ConnectInstagramPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();

  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const callbackStatus = params.get("status");
  const callbackCode = params.get("code");

  // Handle the inbound half of the OAuth trip: Meta redirected to the
  // backend, which redirected here with the outcome.
  useEffect(() => {
    if (callbackStatus === "connected") {
      queryClient.invalidateQueries({ queryKey: INSTAGRAM_PROFILE_QUERY }).then(() => {
        navigate("/dashboard", { replace: true });
      });
      return;
    }

    if (callbackStatus === "error") {
      setError(ERROR_COPY[callbackCode ?? "unknown_error"] ?? ERROR_COPY.unknown_error);
      // Clear the params so a refresh doesn't re-show a stale failure.
      setParams({}, { replace: true });
    }
  }, [callbackStatus, callbackCode, queryClient, navigate, setParams]);

  async function handleConnect() {
    setError(null);
    setStarting(true);

    try {
      const { authorization_url } = await getConnectUrl();
      // A full navigation, not a fetch: Meta's consent screen sets its own
      // cookies and refuses to be embedded or read cross-origin.
      window.location.assign(authorization_url);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Could not reach the server. Is the API running?",
      );
      setStarting(false);
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
            <strong>One last step.</strong>
            <br />
            Connect the account you want to analyse.
          </p>
        </div>
      </aside>

      {/* RIGHT COLUMN: Main Content */}
      <main className="swiss-main">
        <div className="swiss-content">
          <div className="swiss-header-block">
            <span className="step-marker">Step 2 of 2</span>
            <h1 className="swiss-title">Connect Instagram</h1>
            <p className="swiss-subtitle">
              Instalysis reads your posts and insights through the Instagram
              API. You will be sent to Meta to approve access, then returned
              here.
            </p>
          </div>

          {error && (
            <div className="swiss-callout swiss-callout--error">
              <strong>Error:</strong> {error}
            </div>
          )}

          <button
            type="button"
            className="swiss-button"
            onClick={handleConnect}
            disabled={starting}
          >
            <span>{starting ? "Redirecting..." : "Continue to Instagram"}</span>
            <svg className="button-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>

          <div className="rule stack-sm" style={{ paddingTop: "var(--space-4)" }}>
            <p className="muted text-xs">
              You need an Instagram <strong>Business</strong> or{" "}
              <strong>Creator</strong> account linked to a Facebook Page.
              Personal accounts cannot expose insights through the API.
            </p>
            <p className="muted text-xs">
              Your access token is encrypted before it is stored, and can be
              revoked at any time from Settings.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
