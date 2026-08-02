import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getTrends } from "../../api/analytics";
import type { TrendGranularity } from "../../api/types";
import { LineTrendChart, TrendChart } from "../../components/charts/Chart";
import { PageHeader } from "../../components/layout/PageHeader";
import { QueryState } from "../../components/QueryState";
import { EmptyState, Panel, SegmentedControl } from "../../components/ui";
import { formatDate, formatNumber, formatPercent } from "../../lib/format";

const GRANULARITY_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
] as const satisfies readonly { value: TrendGranularity; label: string }[];

const DAY_OPTIONS = [
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
  { value: "365", label: "1 year" },
] as const;

export function TrendsPage() {
  const [granularity, setGranularity] = useState<TrendGranularity>("daily");
  const [days, setDays] = useState<"30" | "90" | "365">("30");

  const trends = useQuery({
    queryKey: ["trends", granularity, days],
    queryFn: () => getTrends(granularity, Number(days)),
  });

  const points = trends.data?.points ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Analytics"
        title="Trends"
        description="How reach, impressions and engagement have moved over time."
        actions={
          <>
            <SegmentedControl
              label="Granularity"
              options={GRANULARITY_OPTIONS}
              value={granularity}
              onChange={setGranularity}
            />
            <SegmentedControl
              label="Period"
              options={DAY_OPTIONS}
              value={days}
              onChange={setDays}
            />
          </>
        }
      />

      <QueryState
        isLoading={trends.isLoading}
        error={trends.error}
        loadingLabel="Loading trends"
      >
        {points.length === 0 ? (
          <EmptyState
            title="No trend data for this period"
            body="Trends are built from stored daily snapshots. Try a longer period, or sync from Instagram to start collecting them."
          />
        ) : (
          <div className="stack-lg">
            <section className="grid">
              <div className="col-6">
                <TrendChart
                  title="Reach"
                  seriesName="Reach"
                  points={points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.reach,
                  }))}
                />
              </div>
              <div className="col-6">
                <LineTrendChart
                  title="Followers"
                  seriesName="Followers"
                  points={points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.followers_count,
                  }))}
                />
              </div>
              <div className="col-6">
                <TrendChart
                  title="Impressions"
                  seriesName="Impressions"
                  points={points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.impressions,
                  }))}
                />
              </div>
              <div className="col-6">
                <LineTrendChart
                  title="Average engagement rate"
                  seriesName="Engagement %"
                  points={points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.average_engagement_rate,
                  }))}
                />
              </div>
            </section>

            <section className="stack">
              <h2>Breakdown</h2>
              <Panel className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Period</th>
                      <th scope="col" className="numeric">
                        Posts
                      </th>
                      <th scope="col" className="numeric">
                        Reach
                      </th>
                      <th scope="col" className="numeric">
                        Impressions
                      </th>
                      <th scope="col" className="numeric">
                        Profile visits
                      </th>
                      <th scope="col" className="numeric">
                        Followers
                      </th>
                      <th scope="col" className="numeric">
                        Avg engagement
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {points.map((point) => (
                      <tr key={point.period_start}>
                        <td>{formatDate(point.period_start)}</td>
                        <td className="numeric">{formatNumber(point.posts_count)}</td>
                        <td className="numeric">{formatNumber(point.reach)}</td>
                        <td className="numeric">{formatNumber(point.impressions)}</td>
                        <td className="numeric">{formatNumber(point.profile_visits)}</td>
                        <td className="numeric">{formatNumber(point.followers_count)}</td>
                        <td className="numeric">
                          {formatPercent(point.average_engagement_rate)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            </section>
          </div>
        )}
      </QueryState>
    </>
  );
}
