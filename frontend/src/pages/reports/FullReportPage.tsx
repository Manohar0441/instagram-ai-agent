import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";

import { getFullReport } from "../../api/export";
import type {
  AIFailure,
  ExportWindowDays,
  InsightsSection,
  RecommendationsSection,
  ReportSection,
} from "../../api/types";
import { LineTrendChart, RankBarChart, TrendChart } from "../../components/charts/Chart";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import { Badge, Button, Callout, Panel, SegmentedControl, StatCard } from "../../components/ui";
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatSigned,
} from "../../lib/format";

// Fixed rather than responsive: ResponsiveContainer's ResizeObserver
// reliably renders blank in a print layout. 720px is the A4 portrait
// content width at the @page margins set in swiss.css.
const CHART_WIDTH = 720;

const WINDOW_OPTIONS = [
  { value: "7", label: "7d" },
  { value: "14", label: "14d" },
  { value: "30", label: "30d" },
  { value: "90", label: "90d" },
  { value: "180", label: "180d" },
  { value: "365", label: "1y" },
] as const;

type WindowValue = (typeof WINDOW_OPTIONS)[number]["value"];

function Section({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="stack export-section">
      <h2>{title}</h2>
      {caption && <p className="chart-panel__caption">{caption}</p>}
      {children}
    </section>
  );
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="detail-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function AIUnavailable({ failure }: { failure: AIFailure }) {
  return (
    <Callout tone="error" title="This section could not be generated">
      {failure.message}
    </Callout>
  );
}

function SectionMeta({
  status,
  servedFromCache,
}: {
  status: "ok" | "unavailable";
  servedFromCache: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <Badge variant={status === "ok" ? "default" : "accent"}>
        {status === "ok" ? "Generated" : "Unavailable"}
      </Badge>
      {status === "ok" && servedFromCache && <Badge>From cache</Badge>}
    </div>
  );
}

function InsightsBlock({ section }: { section: InsightsSection }) {
  return (
    <Section title="AI insights">
      <SectionMeta status={section.status} servedFromCache={section.served_from_cache} />
      {section.status === "unavailable" && section.failure && (
        <AIUnavailable failure={section.failure} />
      )}
      {section.data && (
        <div className="stack-lg">
          {(
            [
              ["account_performance", "Account performance"],
              ["content_performance", "Content performance"],
              ["growth_trend", "Growth trend"],
              ["engagement_trend", "Engagement trend"],
              ["audience_behavior", "Audience behavior"],
            ] as const
          ).map(([key, label]) => (
            <Panel as="article" className="insight" key={key}>
              <h3 className="insight__title">{label}</h3>
              <p className="insight__summary">{section.data![key].summary}</p>
            </Panel>
          ))}
          <p className="generated-at">Generated {formatDateTime(section.data.generated_at)}.</p>
        </div>
      )}
      <Panel className="detail-list">
        <dl className="stack-sm">
          <DetailRow label="Period covered" value={`${section.inputs.period_days} days`} />
          <DetailRow
            label="Post sample seen by the AI"
            value={`${section.inputs.sample.returned} of a ${section.inputs.sample.limit} limit, unwindowed`}
          />
        </dl>
      </Panel>
    </Section>
  );
}

function RecommendationsBlock({ section }: { section: RecommendationsSection }) {
  return (
    <Section title="AI recommendations">
      <SectionMeta status={section.status} servedFromCache={section.served_from_cache} />
      {section.status === "unavailable" && section.failure && (
        <AIUnavailable failure={section.failure} />
      )}
      {section.data && (
        <div className="stack-lg">
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Best posting times</h3>
            <p>{section.data.best_posting_times}</p>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Formats that work</h3>
            <p>{section.data.recommended_content_formats}</p>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Posting frequency</h3>
            <p>{section.data.posting_frequency}</p>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Content ideas</h3>
            <ul>
              {section.data.content_ideas.map((idea, index) => (
                <li key={index}>{idea}</li>
              ))}
            </ul>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Engagement and reach tips</h3>
            <ul>
              {section.data.engagement_reach_tips.map((tip, index) => (
                <li key={index}>{tip}</li>
              ))}
            </ul>
          </Panel>
          <p className="generated-at">Generated {formatDateTime(section.data.generated_at)}.</p>
        </div>
      )}
      <Panel className="detail-list">
        <dl className="stack-sm">
          <DetailRow
            label="Recent-sample size (within this window)"
            value={section.inputs.recent_sample_size}
          />
          <DetailRow
            label="Post sample seen by the AI"
            value={`${section.inputs.sample.returned} of a ${section.inputs.sample.limit} limit, unwindowed`}
          />
        </dl>
      </Panel>
    </Section>
  );
}

function ReportBlock({ section }: { section: ReportSection }) {
  return (
    <Section title="Period report">
      <SectionMeta status={section.status} servedFromCache={section.served_from_cache} />
      <Panel className="detail-list">
        <dl className="stack-sm">
          <DetailRow label="Report period" value={section.period_label} />
          <DetailRow
            label="Covers this export's window"
            value={section.covers_export_window ? "Yes" : `No — covers ${section.period_days} days`}
          />
        </dl>
      </Panel>
      {section.status === "unavailable" && section.failure && (
        <AIUnavailable failure={section.failure} />
      )}
      {section.data && (
        <div className="stack-lg">
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">
              {formatDate(section.data.period_start)} — {formatDate(section.data.period_end)}
            </h3>
            <p>{section.data.summary}</p>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Key strengths</h3>
            <ul>
              {section.data.key_strengths.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Areas for improvement</h3>
            <ul>
              {section.data.areas_for_improvement.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </Panel>
          <Panel as="section" className="list-block">
            <h3 className="list-block__label">Next steps</h3>
            <ul>
              {section.data.actionable_next_steps.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </Panel>
          {section.data.top_performing_content.length > 0 && (
            <div className="stack">
              <h3>Top performing</h3>
              <MediaTable items={section.data.top_performing_content} />
            </div>
          )}
          {section.data.underperforming_content.length > 0 && (
            <div className="stack">
              <h3>Underperforming</h3>
              <MediaTable items={section.data.underperforming_content} />
            </div>
          )}
          <p className="generated-at">Generated {formatDateTime(section.data.generated_at)}.</p>
        </div>
      )}
    </Section>
  );
}

export function FullReportPage() {
  const [days, setDays] = useState<WindowValue>("30");

  const report = useQuery({
    queryKey: ["full-report", days],
    queryFn: () => getFullReport(Number(days) as ExportWindowDays),
  });

  const bundle = report.data;

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Full report"
        description="Every section that feeds the AI, alongside what it said about it — auditable, printable, one page."
        actions={
          <>
            <SegmentedControl
              label="Window"
              options={WINDOW_OPTIONS}
              value={days}
              onChange={setDays}
            />
            <Button small onClick={() => window.print()} disabled={!bundle}>
              Download PDF
            </Button>
          </>
        }
      />

      <QueryState
        isLoading={report.isLoading}
        error={report.error}
        loadingLabel="Assembling the full report"
      >
        {bundle && (
          <div className="stack-lg export-report">
            {bundle.meta.ai_sections_ok < bundle.meta.ai_sections_total && (
              <Callout tone="error" title="Some AI sections are unavailable">
                {bundle.meta.ai_sections_ok} of {bundle.meta.ai_sections_total} AI sections
                generated. The analytics below are unaffected — every input the AI would have
                seen is still shown.
              </Callout>
            )}

            <Panel className="detail-list">
              <dl className="stack-sm">
                <DetailRow label="Account" value={`@${bundle.meta.username}`} />
                <DetailRow
                  label="Window"
                  value={`${formatDate(bundle.meta.window_start)} — ${formatDate(bundle.meta.window_end)} (${bundle.meta.days} days)`}
                />
                <DetailRow label="Generated" value={formatDateTime(bundle.meta.generated_at)} />
              </dl>
            </Panel>

            <Section title="Account analytics">
              <div className="grid">
                <div className="col-3">
                  <StatCard
                    label="Followers"
                    value={formatNumber(bundle.analytics.account.followers_count)}
                    delta={
                      bundle.analytics.account.follower_growth
                        ? formatSigned(bundle.analytics.account.follower_growth.absolute)
                        : undefined
                    }
                  />
                </div>
                <div className="col-3">
                  <StatCard label="Reach" value={formatNumber(bundle.analytics.account.reach)} />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Engagement rate"
                    value={formatPercent(bundle.analytics.account.engagement_rate)}
                  />
                </div>
                <div className="col-3">
                  <StatCard label="Posts" value={formatNumber(bundle.analytics.account.media_count)} />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Impressions"
                    value={formatNumber(bundle.analytics.account.impressions)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Profile visits"
                    value={formatNumber(bundle.analytics.account.profile_visits)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Accounts reached"
                    value={formatNumber(bundle.analytics.account.accounts_reached)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Accounts engaged"
                    value={formatNumber(bundle.analytics.account.accounts_engaged)}
                  />
                </div>
              </div>
            </Section>

            <Section title="Trends" caption={`Granularity: ${bundle.analytics.trends.granularity}`}>
              <div className="stack-lg">
                <TrendChart
                  title="Reach"
                  seriesName="Reach"
                  width={CHART_WIDTH}
                  points={bundle.analytics.trends.points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.reach,
                  }))}
                />
                <LineTrendChart
                  title="Average engagement rate"
                  seriesName="Engagement %"
                  width={CHART_WIDTH}
                  points={bundle.analytics.trends.points.map((point) => ({
                    label: formatDate(point.period_start),
                    value: point.average_engagement_rate,
                  }))}
                />
                <Panel className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Period</th>
                        <th scope="col" className="numeric">Posts</th>
                        <th scope="col" className="numeric">Reach</th>
                        <th scope="col" className="numeric">Impressions</th>
                        <th scope="col" className="numeric">Followers</th>
                        <th scope="col" className="numeric">Avg engagement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bundle.analytics.trends.points.map((point) => (
                        <tr key={point.period_start}>
                          <td>{formatDate(point.period_start)}</td>
                          <td className="numeric">{formatNumber(point.posts_count)}</td>
                          <td className="numeric">{formatNumber(point.reach)}</td>
                          <td className="numeric">{formatNumber(point.impressions)}</td>
                          <td className="numeric">{formatNumber(point.followers_count)}</td>
                          <td className="numeric">{formatPercent(point.average_engagement_rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
              </div>
            </Section>

            <Section
              title="Content inventory"
              caption={
                <>
                  {bundle.analytics.inventory.total_in_window} posts in this window
                  {bundle.analytics.inventory.excluded_undated_count > 0 &&
                    ` (${bundle.analytics.inventory.excluded_undated_count} excluded — no timestamp)`}
                  {bundle.analytics.inventory.truncated &&
                    ` — showing the first ${bundle.analytics.inventory.limit}`}
                  .
                </>
              }
            >
              <MediaTable items={bundle.analytics.inventory.items} />
            </Section>

            <Section title="Top performing content">
              <MediaTable items={bundle.analytics.top_content.items} />
            </Section>

            <Section title="Underperforming content">
              <MediaTable items={bundle.analytics.bottom_content.items} />
            </Section>

            <Section
              title="Posting time"
              caption="All times UTC — a post shown at 14:00 was published at 14:00 UTC, not local time."
            >
              <div className="stack-lg">
                <RankBarChart
                  title="Average engagement by weekday"
                  width={CHART_WIDTH}
                  points={Object.entries(
                    bundle.analytics.breakdowns.posting_time.average_engagement_by_weekday as Record<
                      string,
                      number
                    >,
                  ).map(([weekday, rate]) => ({ label: weekday, value: rate }))}
                />
                <Panel className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Hour (UTC)</th>
                        <th scope="col" className="numeric">Avg engagement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(
                        bundle.analytics.breakdowns.posting_time.average_engagement_by_hour as Record<
                          string,
                          number
                        >,
                      ).map(([hour, rate]) => (
                        <tr key={hour}>
                          <td>{hour}:00</td>
                          <td className="numeric">{formatPercent(rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
              </div>
            </Section>

            <Section title="Content format breakdown">
              <Panel className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Format</th>
                      <th scope="col" className="numeric">Posts</th>
                      <th scope="col" className="numeric">Avg engagement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(
                      bundle.analytics.breakdowns.content_format as Record<
                        string,
                        { post_count: number; average_engagement_rate: number }
                      >,
                    ).map(([format, stats]) => (
                      <tr key={format}>
                        <td>{format}</td>
                        <td className="numeric">{formatNumber(stats.post_count)}</td>
                        <td className="numeric">{formatPercent(stats.average_engagement_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            </Section>

            <Section title="Posting frequency and content summary">
              <div className="grid">
                <div className="col-3">
                  <StatCard
                    label="Posts / week"
                    value={formatNumber(bundle.analytics.breakdowns.posting_frequency.posts_per_week as number | null)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Posts in window"
                    value={formatNumber(bundle.analytics.breakdowns.content_summary.post_count)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Total likes"
                    value={formatNumber(bundle.analytics.breakdowns.content_summary.total_likes)}
                  />
                </div>
                <div className="col-3">
                  <StatCard
                    label="Total comments"
                    value={formatNumber(bundle.analytics.breakdowns.content_summary.total_comments)}
                  />
                </div>
              </div>
            </Section>

            <InsightsBlock section={bundle.insights} />
            <RecommendationsBlock section={bundle.recommendations} />
            <ReportBlock section={bundle.report} />

            <Section title="Methodology">
              <Panel className="detail-list">
                <dl className="stack-sm">
                  <DetailRow label="Trend granularity rule" value={bundle.methodology.granularity_rule} />
                  <DetailRow label="Report period rule" value={bundle.methodology.report_period_rule} />
                  <DetailRow
                    label="Breakdown sample sizes"
                    value={`AI saw ${bundle.methodology.breakdown_divergence.ai_sample_size} posts; this window contains ${bundle.methodology.breakdown_divergence.window_sample_size}`}
                  />
                  {bundle.methodology.breakdown_divergence.differs && (
                    <DetailRow label="Divergence" value={bundle.methodology.breakdown_divergence.explanation} />
                  )}
                  <DetailRow label="Media sample limit" value={bundle.methodology.media_sample_limit} />
                  <DetailRow label="Inventory limit" value={bundle.methodology.inventory_limit} />
                  <DetailRow label="Ranked content limit" value={bundle.methodology.ranked_content_limit} />
                  <DetailRow label="Timezone" value={bundle.methodology.timezone} />
                  <DetailRow label="Cache TTL" value={`${bundle.methodology.cache_ttl_seconds}s`} />
                </dl>
              </Panel>
            </Section>
          </div>
        )}
      </QueryState>
    </>
  );
}
