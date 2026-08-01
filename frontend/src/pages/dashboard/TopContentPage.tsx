import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getTopContent } from "../../api/analytics";
import type { TopContentMetric, TopContentOrder } from "../../api/types";
import { BarChart } from "../../components/charts/BarChart";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import { EmptyState, SegmentedControl } from "../../components/ui";
import { formatNumber, formatPercent, truncate } from "../../lib/format";

const METRIC_OPTIONS = [
  { value: "engagement_rate", label: "Engagement" },
  { value: "reach", label: "Reach" },
  { value: "likes", label: "Likes" },
  { value: "comments", label: "Comments" },
  { value: "impressions", label: "Impressions" },
] as const satisfies readonly { value: TopContentMetric; label: string }[];

const ORDER_OPTIONS = [
  { value: "top", label: "Best" },
  { value: "bottom", label: "Worst" },
] as const satisfies readonly { value: TopContentOrder; label: string }[];

export function TopContentPage() {
  const [metric, setMetric] = useState<TopContentMetric>("engagement_rate");
  const [order, setOrder] = useState<TopContentOrder>("top");

  const content = useQuery({
    queryKey: ["top-content", metric, order],
    queryFn: () => getTopContent(metric, order, 10),
  });

  const items = content.data?.items ?? [];
  const isRate = metric === "engagement_rate";

  return (
    <>
      <PageHeader
        eyebrow="Analytics"
        title="Rankings"
        description="Your best and worst performing posts, by any stored metric."
        actions={
          <>
            <SegmentedControl
              label="Metric"
              options={METRIC_OPTIONS}
              value={metric}
              onChange={setMetric}
            />
            <SegmentedControl
              label="Order"
              options={ORDER_OPTIONS}
              value={order}
              onChange={setOrder}
            />
          </>
        }
      />

      <QueryState
        isLoading={content.isLoading}
        error={content.error}
        loadingLabel="Ranking posts"
      >
        {items.length === 0 ? (
          <EmptyState
            title="Nothing to rank yet"
            body="Rankings need posts with measured insights. Sync from Instagram first."
          />
        ) : (
          <div className="stack-lg">
            <section className="stack">
              <h2>
                {order === "top" ? "Highest" : "Lowest"} by{" "}
                {METRIC_OPTIONS.find((option) => option.value === metric)?.label.toLowerCase()}
              </h2>
              <BarChart
                format={isRate ? (value) => formatPercent(value) : formatNumber}
                data={items.map((item) => ({
                  label: truncate(item.caption, 40),
                  value: isRate
                    ? item.engagement_rate
                    : (item[metric as keyof typeof item] as number | null),
                }))}
              />
            </section>

            <section className="stack">
              <h2>Detail</h2>
              <MediaTable items={items} />
            </section>
          </div>
        )}
      </QueryState>
    </>
  );
}
