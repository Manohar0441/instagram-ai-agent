import { useQuery } from "@tanstack/react-query";

import { getRecommendations } from "../../api/insights";
import { PageHeader } from "../../components/layout/PageHeader";
import { QueryState } from "../../components/QueryState";
import { formatDateTime } from "../../lib/format";
import "./ai.css";

function ListBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <section className="list-block">
      <h2 className="list-block__label">{label}</h2>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function TextBlock({ label, text }: { label: string; text: string }) {
  return (
    <section className="list-block">
      <h2 className="list-block__label">{label}</h2>
      <p>{text}</p>
    </section>
  );
}

export function RecommendationsPage() {
  const recommendations = useQuery({
    queryKey: ["recommendations"],
    queryFn: getRecommendations,
  });

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Recommendations"
        description="What to post, when to post it, and how often — derived from the patterns in your own history."
      />

      <QueryState
        isLoading={recommendations.isLoading}
        error={recommendations.error}
        loadingLabel="Generating recommendations"
      >
        {recommendations.data && (
          <div className="stack-lg" style={{ maxWidth: "52rem" }}>
            <TextBlock
              label="Best posting times"
              text={recommendations.data.best_posting_times}
            />
            <TextBlock
              label="Formats that work"
              text={recommendations.data.recommended_content_formats}
            />
            <TextBlock
              label="Posting frequency"
              text={recommendations.data.posting_frequency}
            />
            <ListBlock
              label="Content ideas"
              items={recommendations.data.content_ideas}
            />
            <ListBlock
              label="Engagement and reach tips"
              items={recommendations.data.engagement_reach_tips}
            />

            <p className="generated-at">
              Generated {formatDateTime(recommendations.data.generated_at)}.
              Results are cached for 15 minutes.
            </p>
          </div>
        )}
      </QueryState>
    </>
  );
}
