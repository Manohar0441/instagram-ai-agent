import { apiFetch } from "./client";
import type { JobEnqueuedResponse, JobStatusResponse, ReportPeriod } from "./types";

export async function enqueueReport(
  period: ReportPeriod,
): Promise<JobEnqueuedResponse> {
  return apiFetch<JobEnqueuedResponse>(`/jobs/reports/${period}`, {
    method: "POST",
  });
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/jobs/${jobId}`);
}
