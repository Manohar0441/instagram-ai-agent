/* One interface per Pydantic schema in app/schemas/.
 *
 * Nullable backend fields are `| null`, never optional. The API deliberately
 * returns null for "we have no data" rather than 0, and the UI must render
 * an em-dash for those — collapsing them to 0 would invent a measurement.
 */

// ---------------------------------------------------------------- auth

export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserCreate {
  username: string;
  full_name: string;
  email: string;
  password: string;
}

export interface UserResponse {
  id: number;
  username: string;
  full_name: string;
  email: string;
  created_at: string;
}

// ------------------------------------------------------------------ ai

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  response: string;
  tools_used: string[];
  /** What the question was understood to be asking. "out_of_scope" means it
   *  was refused before reaching the model. */
  intent: string;
}

export interface AIHealthResponse {
  status: "ok" | "unavailable";
  model: string;
  configured: boolean;
  details: string | null;
}

export interface AIKeyUpdateRequest {
  api_key: string;
}

export interface AIKeyStatusResponse {
  configured: boolean;
  has_own_key: boolean;
  source: "user" | "server" | "none";
  hint: string | null;
  model: string;
}

// ----------------------------------------------------------- instagram

export interface InstagramConnectResponse {
  authorization_url: string;
}

export interface InstagramAccountResponse {
  id: number;
  instagram_user_id: string;
  username: string;
  account_type: string | null;
  biography: string | null;
  profile_picture_url: string | null;
  followers_count: number | null;
  media_count: number | null;
  token_expires_at: string | null;
  connected_at: string;
}

export interface InstagramMediaResponse {
  id: number;
  media_id: string;
  media_type: string;
  caption: string | null;
  media_url: string | null;
  permalink: string | null;
  posted_at: string | null;
}

export interface AccountInsightResponse {
  period: string;
  metrics: Record<string, unknown>;
  fetched_at: string;
}

export interface MediaInsightResponse {
  media_id: string;
  metrics: Record<string, unknown>;
  fetched_at: string;
}

export interface InsightsResponse {
  account_insights: AccountInsightResponse;
  media_insights: MediaInsightResponse[];
}

// ----------------------------------------------------------- analytics

export interface GrowthMetric {
  absolute: number;
  percentage: number | null;
}

export interface AccountAnalyticsResponse {
  instagram_user_id: string;
  username: string;
  followers_count: number | null;
  follower_growth: GrowthMetric | null;
  media_count: number | null;
  reach: number | null;
  impressions: number | null;
  profile_visits: number | null;
  accounts_reached: number | null;
  accounts_engaged: number | null;
  engagement_rate: number | null;
  period_days: number;
  last_updated: string | null;
}

export interface MediaAnalyticsResponse {
  media_id: string;
  media_type: string;
  caption: string | null;
  permalink: string | null;
  posted_at: string | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  reach: number | null;
  impressions: number | null;
  engagement_rate: number | null;
  watch_time: number | null;
  completion_rate: number | null;
  insights_fetched_at: string | null;
}

export type TrendGranularity = "daily" | "weekly" | "monthly";

export interface TrendPoint {
  period_start: string;
  reach: number | null;
  impressions: number | null;
  profile_visits: number | null;
  followers_count: number | null;
  posts_count: number;
  average_engagement_rate: number | null;
}

export interface TrendsResponse {
  granularity: TrendGranularity;
  points: TrendPoint[];
}

export type TopContentMetric =
  | "engagement_rate"
  | "reach"
  | "likes"
  | "comments"
  | "impressions";

export type TopContentOrder = "top" | "bottom";

export interface TopContentResponse {
  metric: string;
  order: TopContentOrder;
  items: MediaAnalyticsResponse[];
}

export interface DashboardResponse {
  account: AccountAnalyticsResponse;
  top_content: MediaAnalyticsResponse[];
  recent_trend: TrendPoint[];
}

// ------------------------------------------------------- ai insights

export interface Insight {
  title: string;
  summary: string;
  supporting_data: Record<string, unknown>;
}

export interface PerformanceInsightsResponse {
  account_performance: Insight;
  content_performance: Insight;
  growth_trend: Insight;
  engagement_trend: Insight;
  audience_behavior: Insight;
  generated_at: string;
}

export interface RecommendationsResponse {
  best_posting_times: string;
  recommended_content_formats: string;
  content_ideas: string[];
  posting_frequency: string;
  engagement_reach_tips: string[];
  generated_at: string;
}

export type ReportPeriod = "weekly" | "monthly";

export interface PerformanceReportResponse {
  period: ReportPeriod;
  period_start: string;
  period_end: string;
  summary: string;
  top_performing_content: MediaAnalyticsResponse[];
  underperforming_content: MediaAnalyticsResponse[];
  key_strengths: string[];
  areas_for_improvement: string[];
  actionable_next_steps: string[];
  generated_at: string;
}

// ---------------------------------------------------------------- jobs

export interface JobEnqueuedResponse {
  job_id: string;
  status: "queued";
}

/** RQ's own status vocabulary, passed through unchanged by the backend. */
export type JobStatus =
  | "queued"
  | "started"
  | "deferred"
  | "finished"
  | "failed"
  | "stopped"
  | "scheduled"
  | "canceled";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  /** On success this is a PerformanceReportResponse serialized to JSON. */
  result: PerformanceReportResponse | null;
  error: string | null;
}
