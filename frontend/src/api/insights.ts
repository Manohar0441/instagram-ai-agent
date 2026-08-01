import { apiFetch } from "./client";
import type {
  PerformanceInsightsResponse,
  PerformanceReportResponse,
  RecommendationsResponse,
  ReportPeriod,
} from "./types";

export async function getInsights(): Promise<PerformanceInsightsResponse> {
  return apiFetch<PerformanceInsightsResponse>("/insights");
}

export async function getRecommendations(): Promise<RecommendationsResponse> {
  return apiFetch<RecommendationsResponse>("/recommendations");
}

export async function getReport(
  period: ReportPeriod,
): Promise<PerformanceReportResponse> {
  return apiFetch<PerformanceReportResponse>(`/reports/${period}`);
}
