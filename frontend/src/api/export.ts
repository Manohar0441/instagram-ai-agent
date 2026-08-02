import { apiFetch } from "./client";
import type { ExportWindowDays, FullReportExportResponse } from "./types";

export async function getFullReport(
  days: ExportWindowDays,
): Promise<FullReportExportResponse> {
  return apiFetch<FullReportExportResponse>(`/export/full-report?days=${days}`);
}
