import { useQuery } from "@tanstack/react-query";

import { getInsights } from "../../api/insights";
import type { Insight } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { QueryState } from "../../components/QueryState";
import { Panel } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

function InsightCard({ insight }: { insight: Insight }) {
  return (
    <Panel as="article" className="insight">
      <h2 className="insight__title">{insight.title}</h2>
      <p className="insight__summary">{insight.summary}</p>

      {/* The narrative is written by the model; these figures are not. They
          come straight from the analytics layer, which is the whole point —
          so they are inspectable rather than hidden. */}
      <details className="insight__disclosure">
        <summary>Show the data behind this</summary>
        <pre className="insight__data">
          {JSON.stringify(insight.supporting_data, null, 2)}
        </pre>
      </details>
    </Panel>
  );
}

export function InsightsPage() {
  const insights = useQuery({
    queryKey: ["insights"],
    queryFn: getInsights,
  });

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Insights"
        description="Five readings of your account, written from your stored analytics. The prose is generated; every number is measured."
      />

      <QueryState
        isLoading={insights.isLoading}
        error={insights.error}
        loadingLabel="Generating insights"
      >
        {insights.data && (
          <div className="stack-lg" style={{ maxWidth: "52rem" }}>
            <InsightCard insight={insights.data.account_performance} />
            <InsightCard insight={insights.data.content_performance} />
            <InsightCard insight={insights.data.growth_trend} />
            <InsightCard insight={insights.data.engagement_trend} />
            <InsightCard insight={insights.data.audience_behavior} />

            <p className="generated-at">
              Generated {formatDateTime(insights.data.generated_at)}. Results are
              cached for 15 minutes.
            </p>
          </div>
        )}
      </QueryState>
    </>
  );
}
