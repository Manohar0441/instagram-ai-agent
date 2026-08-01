import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getConnectUrl } from "../../api/instagram";
import "../../components/layout/layout.css";
import { Button, Callout } from "../../components/ui";
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
    <div className="centered">
      <div className="centered__panel centered__panel--wide">
        <div className="centered__brand">Instalysis</div>

        <div className="stack-lg">
          <div>
            <div className="step-marker">Step 2 of 2</div>
            <h1>Connect your Instagram account</h1>
            <p className="muted" style={{ marginTop: "var(--space-4)" }}>
              Instalysis reads your posts and insights through the Instagram
              Graph API. You will be sent to Meta to approve access, then
              returned here.
            </p>
          </div>

          {error && <Callout tone="error">{error}</Callout>}

          <div className="stack">
            <Button variant="primary" onClick={handleConnect} loading={starting}>
              Continue to Instagram
            </Button>
          </div>

          <div className="rule stack-sm" style={{ paddingTop: "var(--space-4)" }}>
            <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
              You need an Instagram <strong>Business</strong> or{" "}
              <strong>Creator</strong> account linked to a Facebook Page.
              Personal accounts cannot expose insights through the API.
            </p>
            <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
              Your access token is encrypted before it is stored, and can be
              revoked at any time from Settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
