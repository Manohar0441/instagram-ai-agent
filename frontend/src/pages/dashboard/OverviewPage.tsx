import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getAccountAnalytics, getDashboard } from "../../api/analytics";
import { LineChart } from "../../components/charts/LineChart";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import { EmptyState, SegmentedControl, StatBlock } from "../../components/ui";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatSigned,
} from "../../lib/format";

const DAY_OPTIONS = [
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
] as const;

export function OverviewPage() {
  const [days, setDays] = useState<"7" | "30" | "90">("30");

  // The dashboard endpoint answers the hero in a single call; the account
  // query only exists so the day-window selector can change the numbers
  // without refetching top content and trends alongside them.
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
  });

  const account = useQuery({
    queryKey: ["account-analytics", days],
    queryFn: () => getAccountAnalytics(Number(days)),
  });

  const growth = account.data?.follower_growth ?? null;

  return (
    <>
      <PageHeader
        eyebrow="Analytics"
        title="Overview"
        description={
          account.data
            ? `@${account.data.username} · last updated ${formatDate(account.data.last_updated)}`
            : undefined
        }
        actions={
          <SegmentedControl
            label="Reporting window"
            options={DAY_OPTIONS}
            value={days}
            onChange={setDays}
          />
        }
      />

      <QueryState
        isLoading={dashboard.isLoading || account.isLoading}
        error={dashboard.error ?? account.error}
        loadingLabel="Loading your analytics"
      >
        {account.data && (
          <div className="stack-lg">
            <section className="grid">
              <div className="col-3">
                <StatBlock
                  label="Followers"
                  value={formatNumber(account.data.followers_count)}
                  delta={growth ? formatSigned(growth.absolute) : undefined}
                  deltaDirection={
                    growth
                      ? growth.absolute > 0
                        ? "up"
                        : growth.absolute < 0
                          ? "down"
                          : "flat"
                      : undefined
                  }
                />
              </div>
              <div className="col-3">
                <StatBlock label="Reach" value={formatNumber(account.data.reach)} />
              </div>
              <div className="col-3">
                <StatBlock
                  label="Engagement rate"
                  value={formatPercent(account.data.engagement_rate)}
                />
              </div>
              <div className="col-3">
                <StatBlock label="Posts" value={formatNumber(account.data.media_count)} />
              </div>
            </section>

            <section className="grid">
              <div className="col-3">
                <StatBlock
                  label="Impressions"
                  value={formatNumber(account.data.impressions)}
                />
              </div>
              <div className="col-3">
                <StatBlock
                  label="Profile visits"
                  value={formatNumber(account.data.profile_visits)}
                />
              </div>
              <div className="col-3">
                <StatBlock
                  label="Accounts reached"
                  value={formatNumber(account.data.accounts_reached)}
                />
              </div>
              <div className="col-3">
                <StatBlock
                  label="Accounts engaged"
                  value={formatNumber(account.data.accounts_engaged)}
                />
              </div>
            </section>

            {dashboard.data && dashboard.data.recent_trend.length > 0 && (
              <section className="stack">
                <h2>Reach over time</h2>
                <LineChart
                  label="Reach over the recent period"
                  valueLabel="Reach"
                  points={dashboard.data.recent_trend.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.reach,
                  }))}
                />
                <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
                  <Link to="/trends">See weekly and monthly trends</Link>
                </p>
              </section>
            )}

            <section className="stack">
              <h2>Top performing posts</h2>
              {dashboard.data && dashboard.data.top_content.length > 0 ? (
                <>
                  <MediaTable items={dashboard.data.top_content} />
                  <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
                    <Link to="/top-content">Rank by other metrics</Link>
                  </p>
                </>
              ) : (
                <EmptyState
                  title="No posts analysed yet"
                  body={
                    <>
                      Sync your posts and insights from{" "}
                      <Link to="/settings">Settings</Link> to see rankings here.
                    </>
                  }
                />
              )}
            </section>
          </div>
        )}
      </QueryState>
    </>
  );
}
