import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { clearKey, setKey } from "../api/ai";
import { ApiError } from "../api/client";
import { disconnect, syncInsights, syncMedia } from "../api/instagram";
import { PageHeader } from "../components/layout/PageHeader";
import { Button, Callout, Field, LoadingPage, Panel } from "../components/ui";
import { formatDate, formatNumber } from "../lib/format";
import {
  AI_KEY_QUERY,
  INSTAGRAM_PROFILE_QUERY,
  useOnboardingStatus,
} from "../onboarding/useOnboardingStatus";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.detail
    : "Could not reach the server. Is the API running?";
}

export function SettingsPage() {
  const status = useOnboardingStatus();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [apiKey, setApiKey] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const saveKey = useMutation({
    mutationFn: (key: string) => setKey(key),
    onSuccess: async () => {
      setApiKey("");
      setNotice("Gemini API key updated.");
      await queryClient.invalidateQueries({ queryKey: AI_KEY_QUERY });
    },
  });

  const removeKey = useMutation({
    mutationFn: clearKey,
    onSuccess: async () => {
      setNotice("Gemini API key removed.");
      await queryClient.invalidateQueries({ queryKey: AI_KEY_QUERY });
    },
  });

  const sync = useMutation({
    mutationFn: async () => {
      // Order matters: insights are keyed to stored media, so the posts have
      // to be pulled in first.
      await syncMedia(50);
      await syncInsights();
    },
    onSuccess: () => {
      setNotice("Synced the latest posts and insights from Instagram.");
      // Every analytics view is now stale.
      queryClient.invalidateQueries();
    },
  });

  const disconnectAccount = useMutation({
    mutationFn: disconnect,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: INSTAGRAM_PROFILE_QUERY });
      navigate("/onboarding/instagram", { replace: true });
    },
  });

  if (status.isLoading) {
    return <LoadingPage label="Loading settings" />;
  }

  function handleSaveKey(event: FormEvent) {
    event.preventDefault();
    setNotice(null);
    saveKey.mutate(apiKey.trim());
  }

  const account = status.account;

  return (
    <>
      <PageHeader
        eyebrow="Account"
        title="Settings"
        description="Manage the Gemini key that powers AI features and the Instagram account Instalysis reads from."
      />

      <div className="stack-lg" style={{ maxWidth: "48rem" }}>
        {notice && <Callout>{notice}</Callout>}

        {/* ---------------------------------------------- Gemini key */}
        <section className="stack">
          <h2>Gemini API key</h2>

          {status.aiStatus?.source === "user" ? (
            <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
              Using your own key, ending in{" "}
              <span className="mono">…{status.aiStatus.hint}</span>. Model:{" "}
              <span className="mono">{status.aiStatus.model}</span>.
            </p>
          ) : status.aiStatus?.source === "server" ? (
            <Callout title="Using the server's shared key">
              You have not set a key of your own, so Instalysis is falling back
              to the one configured on the server. Add your own below to use
              your own Gemini quota.
            </Callout>
          ) : (
            <Callout tone="error" title="No key configured">
              AI features are unavailable until you add a Gemini API key.
            </Callout>
          )}

          {saveKey.isError && (
            <Callout tone="error">{errorMessage(saveKey.error)}</Callout>
          )}
          {removeKey.isError && (
            <Callout tone="error">{errorMessage(removeKey.error)}</Callout>
          )}

          <form className="stack" onSubmit={handleSaveKey}>
            <Field
              label={status.aiStatus?.has_own_key ? "Replace key" : "Add your key"}
              type="password"
              value={apiKey}
              autoComplete="off"
              spellCheck={false}
              placeholder="AQ.Ab8…"
              required
              hint={
                <>
                  Get one at{" "}
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    aistudio.google.com/apikey
                  </a>
                  .
                </>
              }
              onChange={(event) => setApiKey(event.target.value)}
            />
            <div className="row row-wrap">
              <Button type="submit" variant="primary" loading={saveKey.isPending}>
                Save key
              </Button>
              {status.aiStatus?.has_own_key && (
                <Button
                  type="button"
                  variant="danger"
                  loading={removeKey.isPending}
                  onClick={() => {
                    setNotice(null);
                    removeKey.mutate();
                  }}
                >
                  Remove my key
                </Button>
              )}
            </div>
          </form>
        </section>

        {/* ---------------------------------------------- Instagram */}
        <section className="stack rule" style={{ paddingTop: "var(--space-8)" }}>
          <h2>Instagram account</h2>

          {status.instagramTokenExpired && (
            <Callout tone="error" title="Instagram authorization expired">
              Long-lived tokens last about 60 days. Reconnect to keep syncing
              new posts and insights.
            </Callout>
          )}

          {account ? (
            <>
              <Panel className="detail-list">
                <dl className="stack-sm">
                  <div className="detail-row">
                    <dt>Username</dt>
                    <dd className="mono">@{account.username}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Account type</dt>
                    <dd>{account.account_type ?? "—"}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Followers</dt>
                    <dd className="tabular">{formatNumber(account.followers_count)}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Posts</dt>
                    <dd className="tabular">{formatNumber(account.media_count)}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Connected</dt>
                    <dd>{formatDate(account.connected_at)}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Token expires</dt>
                    <dd>{formatDate(account.token_expires_at)}</dd>
                  </div>
                </dl>
              </Panel>

              {sync.isError && <Callout tone="error">{errorMessage(sync.error)}</Callout>}
              {disconnectAccount.isError && (
                <Callout tone="error">{errorMessage(disconnectAccount.error)}</Callout>
              )}

              <div className="row row-wrap">
                <Button
                  onClick={() => {
                    setNotice(null);
                    sync.mutate();
                  }}
                  loading={sync.isPending}
                >
                  Sync from Instagram
                </Button>
                <Button
                  variant="danger"
                  loading={disconnectAccount.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Disconnect this account? Stored posts, insights and analytics for it will be deleted.",
                      )
                    ) {
                      disconnectAccount.mutate();
                    }
                  }}
                >
                  Disconnect
                </Button>
              </div>

              <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
                Syncing pulls fresh posts and insights from Meta into
                Instalysis. Analytics are computed from what has been synced,
                so run this after posting.
              </p>
            </>
          ) : (
            <>
              <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                No Instagram account is connected.
              </p>
              <div>
                <Button variant="primary" onClick={() => navigate("/onboarding/instagram")}>
                  Connect an account
                </Button>
              </div>
            </>
          )}
        </section>

        <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
          <Link to="/dashboard">Back to the dashboard</Link>
        </p>
      </div>
    </>
  );
}
