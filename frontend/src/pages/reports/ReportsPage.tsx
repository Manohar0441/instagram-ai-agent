import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getReport } from "../../api/insights";
import { enqueueReport } from "../../api/jobs";
import type { PerformanceReportResponse, ReportPeriod } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { ApiErrorState, QueryState } from "../../components/QueryState";
import { Button, Callout, SegmentedControl } from "../../components/ui";
import { useJobPolling } from "../../hooks/useJobPolling";
import { formatDate, formatDateTime } from "../../lib/format";
import "../ai/ai.css";

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
  const [jobId, setJobId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const report = useQuery({
    queryKey: ["report", period],
    queryFn: () => getReport(period),
  });

  const enqueue = useMutation({
    mutationFn: () => enqueueReport(period),
    onSuccess: (response) => {
      setJobId(response.job_id);
      setStartedAt(Date.now());
    },
  });

  const polling = useJobPolling(jobId, startedAt);

  // A finished background job supersedes the synchronous result.
  const displayed = polling.job?.status === "finished" && polling.job.result
    ? polling.job.result
    : report.data;

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
              onChange={(next) => {
                setPeriod(next);
                setJobId(null);
                setStartedAt(null);
              }}
            />
            <Button
              small
              onClick={() => enqueue.mutate()}
              loading={enqueue.isPending || polling.isPolling}
            >
              Regenerate in background
            </Button>
          </>
        }
      />

      <div className="stack-lg">
        {enqueue.isError && <ApiErrorState error={enqueue.error} />}

        {polling.isPolling && (
          <Callout title="Generating in the background">
            The report is queued with a worker. This page updates itself when
            it finishes — you can navigate away and come back.
          </Callout>
        )}

        {polling.timedOut && (
          <Callout tone="error" title="Still running">
            The background job has not finished after five minutes, so polling
            stopped. Check that the RQ worker is running, then try again.
          </Callout>
        )}

        {polling.job?.status === "failed" && (
          <Callout tone="error" title="Background job failed">
            {polling.job.error ?? "The worker did not report a reason."}
          </Callout>
        )}

        <QueryState
          isLoading={report.isLoading}
          error={report.error}
          loadingLabel="Generating report"
        >
          {displayed && <ReportBody report={displayed} />}
        </QueryState>
      </div>
    </>
  );
}
