import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getAccountAnalytics, getDashboard } from "../../api/analytics";
import { TrendChart } from "../../components/charts/Chart";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import {
  Button,
  EmptyState,
  Glass,
  SegmentedControl,
  SkeletonCards,
  StatCard,
} from "../../components/ui";
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

type Direction = "up" | "down" | "flat";

function directionOf(value: number | null | undefined): Direction | undefined {
  if (value === null || value === undefined) return undefined;
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

export function OverviewPage() {
  const [days, setDays] = useState<"7" | "30" | "90">("30");

  // One call answers the hero. The account query exists separately so the
  // day-window selector can change those numbers without refetching top
  // content and the trend alongside them.
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });
  const account = useQuery({
    queryKey: ["account-analytics", days],
    queryFn: () => getAccountAnalytics(Number(days)),
  });

  const growth = account.data?.follower_growth ?? null;
  const trend = dashboard.data?.recent_trend ?? [];
  const isLoading = dashboard.isLoading || account.isLoading;

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

      {isLoading ? (
        <div className="stack-lg">
          <SkeletonCards count={4} />
          <SkeletonCards count={4} />
        </div>
      ) : (
        <QueryState
          isLoading={false}
          error={dashboard.error ?? account.error}
          loadingLabel="Loading your analytics"
        >
          {account.data && (
            <div className="stack-lg">
              <section className="grid">
                <div className="col-3">
                  <StatCard
                    label="Followers"
                    icon="◎"
                    value={formatNumber(account.data.followers_count)}
                    delta={growth ? formatSigned(growth.absolute) : undefined}
                    direction={directionOf(growth?.absolute)}
                    note="No growth data yet"
                    tooltip="Total followers, with the change across the selected window."
                    sparkline={trend.map((point) => point.followers_count)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Reach"
                    icon="◈"
                    value={formatNumber(account.data.reach)}
                    tooltip="Unique accounts that saw your content in this window."
                    sparkline={trend.map((point) => point.reach)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Engagement rate"
                    icon="◆"
                    value={formatPercent(account.data.engagement_rate)}
                    tooltip="Interactions normalised by reach — a small, highly engaged audience can beat a large passive one."
                    sparkline={trend.map((point) => point.average_engagement_rate)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Posts"
                    icon="▦"
                    value={formatNumber(account.data.media_count)}
                    tooltip="Total posts on the account."
                  />
                </div>
              </section>

              <section className="grid">
                <div className="col-3">
                  <StatCard
                    label="Impressions"
                    icon="◉"
                    value={formatNumber(account.data.impressions)}
                    tooltip="Total views, including repeat views by the same account."
                    sparkline={trend.map((point) => point.impressions)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Profile visits"
                    icon="◐"
                    value={formatNumber(account.data.profile_visits)}
                    tooltip="Times your profile was opened in this window."
                    sparkline={trend.map((point) => point.profile_visits)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Accounts reached"
                    icon="◑"
                    value={formatNumber(account.data.accounts_reached)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Accounts engaged"
                    icon="◒"
                    value={formatNumber(account.data.accounts_engaged)}
                  />
                </div>
              </section>

              {trend.length > 0 && (
                <section className="grid">
                  <div className="col-8">
                    <TrendChart
                      title="Reach over time"
                      seriesName="Reach"
                      points={trend.map((point) => ({
                        label: formatDate(point.period_start),
                        value: point.reach,
                      }))}
                      caption={
                        <>
                          Gaps are days with no recorded measurement, not days
                          with zero reach. <Link to="/trends">See all trends</Link>
                        </>
                      }
                    />
                  </div>
                  <div className="col-4">
                    <TrendChart
                      title="Followers"
                      seriesName="Followers"
                      points={trend.map((point) => ({
                        label: formatDate(point.period_start),
                        value: point.followers_count,
                      }))}
                    />
                  </div>
                </section>
              )}

              <section className="stack">
                <h2>Top performing posts</h2>
                {dashboard.data && dashboard.data.top_content.length > 0 ? (
                  <Glass>
                    <MediaTable items={dashboard.data.top_content} />
                  </Glass>
                ) : (
                  <EmptyState
                    title="No posts analysed yet"
                    body="Rankings need posts with measured insights. Sync from Instagram to pull them in."
                    actions={
                      <Link to="/settings">
                        <Button variant="primary" small>
                          Go to Settings
                        </Button>
                      </Link>
                    }
                  />
                )}
              </section>
            </div>
          )}
        </QueryState>
      )}
    </>
  );
}
