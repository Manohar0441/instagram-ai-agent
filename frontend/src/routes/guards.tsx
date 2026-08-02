import { Navigate, Outlet, useLocation, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { LoadingPage } from "../components/ui";
import { useOnboardingStatus } from "../onboarding/useOnboardingStatus";

/** Requires a session; sends anonymous callers to login, preserving the target. */
export function RequireAuth() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  return <Outlet />;
}

/** Keeps signed-in users off the login screen. */
export function RedirectIfAuthenticated() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

/**
 * Gates the app behind completed onboarding.
 *
 * The order matters: a Gemini key first, then an Instagram connection,
 * because every analytics and AI endpoint 404s without a connected account.
 */
export function RequireOnboarding() {
  const status = useOnboardingStatus();

  if (status.isLoading) {
    return <LoadingPage label="Checking your setup" />;
  }

  if (!status.aiConfigured) {
    return <Navigate to="/onboarding/gemini" replace />;
  }

  if (!status.instagramConnected) {
    return <Navigate to="/onboarding/instagram" replace />;
  }

  return <Outlet />;
}

/** Keeps fully-onboarded users out of the onboarding flow. */
export function RedirectIfOnboarded() {
  const status = useOnboardingStatus();
  const [params] = useSearchParams();

  if (status.isLoading) {
    return <LoadingPage label="Checking your setup" />;
  }

  // A user returning from Meta's redirect carries ?status=connected|error and
  // must see that result even though onboarding may now be complete —
  // otherwise a *failed* connection bounces silently to the dashboard.
  if (params.has("status")) {
    return <Outlet />;
  }

  if (status.aiConfigured && status.instagramConnected) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
