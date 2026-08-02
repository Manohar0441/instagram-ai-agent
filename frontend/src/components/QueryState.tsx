import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import { Callout, EmptyState, LoadingPage } from "./ui";

/* Every AI-backed and analytics screen shares the same three failure shapes,
 * and each one needs different copy. Centralising them keeps the pages
 * focused on their content and stops "no data yet" being reported as a bug. */

export function QueryState({
  isLoading,
  error,
  loadingLabel = "Loading",
  children,
}: {
  isLoading: boolean;
  error: unknown;
  loadingLabel?: string;
  children: ReactNode;
}) {
  if (isLoading) {
    return <LoadingPage label={loadingLabel} />;
  }

  if (error) {
    return <ApiErrorState error={error} />;
  }

  return <>{children}</>;
}

export function ApiErrorState({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) {
    return (
      <Callout tone="error" title="Could not reach the server">
        Check that the API is running at the configured address.
      </Callout>
    );
  }

  // 404 from an analytics endpoint means "no Instagram account connected",
  // which during normal use means the data has not been synced yet.
  if (error.status === 404) {
    return (
      <EmptyState
        title="Nothing to show yet"
        body={
          <>
            No Instagram data has been synced for this account. Open{" "}
            <a href="/settings">Settings</a> and run “Sync from Instagram” to
            pull in your posts and insights.
          </>
        }
      />
    );
  }

  if (error.status === 429) {
    // Two different things return 429: our own per-endpoint throttle
    // (whose detail is a generic "Request failed..." string, since slowapi's
    // handler doesn't send one the client recognises) and Gemini's own quota
    // limit (which does have a specific, already user-facing detail).
    const hasSpecificReason = !error.detail.startsWith("Request failed with status");
    return (
      <Callout tone="error" title="Slow down a moment">
        {hasSpecificReason
          ? error.detail
          : "This is limited to a few requests a minute. Try again shortly."}
      </Callout>
    );
  }

  if (error.status === 503) {
    return (
      <Callout tone="error" title="AI is not configured">
        {error.detail} Add a Gemini API key in <a href="/settings">Settings</a>.
      </Callout>
    );
  }

  if (error.status === 502) {
    return (
      <Callout tone="error" title="Gemini request failed">
        {error.detail}
      </Callout>
    );
  }

  return (
    <Callout tone="error" title="Something went wrong">
      {error.detail}
    </Callout>
  );
}
