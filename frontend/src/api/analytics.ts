import { apiFetch } from "./client";
import type {
  AccountAnalyticsResponse,
  DashboardResponse,
  MediaAnalyticsResponse,
  TopContentMetric,
  TopContentOrder,
  TopContentResponse,
  TrendGranularity,
  TrendsResponse,
} from "./types";

export async function getDashboard(): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>("/analytics/dashboard");
}

export async function getAccountAnalytics(
  days = 30,
): Promise<AccountAnalyticsResponse> {
  return apiFetch<AccountAnalyticsResponse>(`/analytics/account?days=${days}`);
}

export async function getMediaAnalytics(
  limit = 25,
  mediaType?: string,
): Promise<MediaAnalyticsResponse[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (mediaType) params.set("media_type", mediaType);
  return apiFetch<MediaAnalyticsResponse[]>(`/analytics/media?${params}`);
}

export async function getTrends(
  granularity: TrendGranularity = "daily",
  days = 30,
): Promise<TrendsResponse> {
  const params = new URLSearchParams({ granularity, days: String(days) });
  return apiFetch<TrendsResponse>(`/analytics/trends?${params}`);
}

export async function getTopContent(
  metric: TopContentMetric = "engagement_rate",
  order: TopContentOrder = "top",
  limit = 5,
): Promise<TopContentResponse> {
  const params = new URLSearchParams({ metric, order, limit: String(limit) });
  return apiFetch<TopContentResponse>(`/analytics/top-content?${params}`);
}
