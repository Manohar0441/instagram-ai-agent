import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getReport } from "../../api/insights";
import type { PerformanceReportResponse, ReportPeriod } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import { Button, SegmentedControl } from "../../components/ui";
import { formatDate, formatDateTime } from "../../lib/format";

const PERIOD_OPTIONS = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
] as const satisfies readonly { value: ReportPeriod; label: string }[];

function ListBlock({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
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

function ReportBody({ report }: { report: PerformanceReportResponse }) {
  return (
    <div className="stack-lg" style={{ maxWidth: "56rem" }}>
      <section className="list-block">
        <h2 className="list-block__label">
          {formatDate(report.period_start)} — {formatDate(report.period_end)}
        </h2>
        <p>{report.summary}</p>
      </section>

      <ListBlock label="Key strengths" items={report.key_strengths} />
      <ListBlock label="Areas for improvement" items={report.areas_for_improvement} />
      <ListBlock label="Next steps" items={report.actionable_next_steps} />

      {report.top_performing_content.length > 0 && (
        <section className="stack">
          <h2>Top performing</h2>
          <MediaTable items={report.top_performing_content} />
        </section>
      )}

      {report.underperforming_content.length > 0 && (
        <section className="stack">
          <h2>Underperforming</h2>
          <MediaTable items={report.underperforming_content} />
        </section>
      )}

      <p className="generated-at">
        Generated {formatDateTime(report.generated_at)}. Results are cached for
        15 minutes.
      </p>
    </div>
  );
}

export function ReportsPage() {
  const [period, setPeriod] = useState<ReportPeriod>("weekly");

  const report = useQuery({
    queryKey: ["report", period],
    queryFn: () => getReport(period),
  });

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Reports"
        description="A full performance write-up for the period. Content rankings come from your analytics; only the narrative is generated."
        actions={
          <>
            <SegmentedControl
              label="Report period"
              options={PERIOD_OPTIONS}
              value={period}
              onChange={setPeriod}
            />
            <Button small onClick={() => report.refetch()} loading={report.isFetching}>
              Regenerate
            </Button>
            <Link to="/reports/full">
              <Button small variant="primary">
                Download report
              </Button>
            </Link>
          </>
        }
      />

      <div className="stack-lg">
        <QueryState
          isLoading={report.isLoading}
          error={report.error}
          loadingLabel="Generating report"
        >
          {report.data && <ReportBody report={report.data} />}
        </QueryState>
      </div>
    </>
  );
}
