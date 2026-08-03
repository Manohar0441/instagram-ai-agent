/* One interface per Pydantic schema in app/schemas/.
 *
 * Nullable backend fields are `| null`, never optional. The API deliberately
 * returns null for "we have no data" rather than 0, and the UI must render
 * an em-dash for those — collapsing them to 0 would invent a measurement.
 */

// ---------------------------------------------------------------- auth

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
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

// --------------------------------------------------------------- export

export type ExportWindowDays = 7 | 14 | 30 | 90 | 180 | 365;

export interface ContentSummary {
  post_count: number;
  average_engagement_rate: number | null;
  total_likes: number | null;
  total_comments: number | null;
}

export interface SampleProvenance {
  limit: number;
  returned: number;
  window_filtered: boolean;
}

export type AIFailureReason =
  | "not_configured"
  | "rate_limited"
  | "provider_error"
  | "generation_error"
  | "unexpected_error";

export interface AIFailure {
  reason: AIFailureReason;
  message: string;
  retriable: boolean;
}

export interface InsightsInputs {
  period_days: number;
  account_analytics: AccountAnalyticsResponse;
  content_summary: ContentSummary;
  trend_points: Record<string, unknown>[];
  trend_granularity: TrendGranularity;
  posting_time_breakdown: Record<string, unknown>;
  sample: SampleProvenance;
}

export interface RecommendationsInputs {
  period_days: number;
  posting_time_breakdown: Record<string, unknown>;
  content_format_breakdown: Record<string, unknown>;
  posting_frequency: Record<string, unknown>;
  top_performing_content: MediaAnalyticsResponse[];
  sample: SampleProvenance;
  recent_sample_size: number;
}

export interface ReportInputs {
  period: ReportPeriod;
  period_start: string;
  period_end: string;
  account_analytics: AccountAnalyticsResponse;
  trend_points: Record<string, unknown>[];
  trend_granularity: TrendGranularity;
  top_performing_content: MediaAnalyticsResponse[];
  underperforming_content: MediaAnalyticsResponse[];
  content_limit: number;
}

export interface InsightsSection {
  status: "ok" | "unavailable";
  data: PerformanceInsightsResponse | null;
  failure: AIFailure | null;
  served_from_cache: boolean;
  inputs: InsightsInputs;
}

export interface RecommendationsSection {
  status: "ok" | "unavailable";
  data: RecommendationsResponse | null;
  failure: AIFailure | null;
  served_from_cache: boolean;
  inputs: RecommendationsInputs;
}

export interface ReportSection {
  status: "ok" | "unavailable";
  data: PerformanceReportResponse | null;
  failure: AIFailure | null;
  served_from_cache: boolean;
  inputs: ReportInputs;
  period_label: ReportPeriod;
  period_days: number;
  covers_export_window: boolean;
}

export interface WindowBreakdowns {
  posting_time: Record<string, unknown>;
  content_format: Record<string, unknown>;
  posting_frequency: Record<string, unknown>;
  content_summary: ContentSummary;
  sample: SampleProvenance;
}

export interface ContentInventory {
  items: MediaAnalyticsResponse[];
  total_in_window: number;
  truncated: boolean;
  limit: number;
  excluded_undated_count: number;
}

export interface WindowAnalytics {
  account: AccountAnalyticsResponse;
  trends: TrendsResponse;
  inventory: ContentInventory;
  top_content: TopContentResponse;
  bottom_content: TopContentResponse;
  breakdowns: WindowBreakdowns;
}

export interface BreakdownDivergence {
  ai_sample_size: number;
  window_sample_size: number;
  differs: boolean;
  explanation: string;
}

export interface Methodology {
  granularity_rule: string;
  report_period_rule: string;
  breakdown_divergence: BreakdownDivergence;
  media_sample_limit: number;
  inventory_limit: number;
  ranked_content_limit: number;
  timezone: "UTC";
  cache_ttl_seconds: number;
}

export interface ExportMeta {
  schema_version: 1;
  generated_at: string;
  days: ExportWindowDays;
  window_start: string;
  window_end: string;
  username: string;
  instagram_user_id: string;
  ai_sections_ok: number;
  ai_sections_total: 3;
}

export interface FullReportExportResponse {
  meta: ExportMeta;
  methodology: Methodology;
  analytics: WindowAnalytics;
  insights: InsightsSection;
  recommendations: RecommendationsSection;
  report: ReportSection;
}

// ----------------------------------------------------------------- deals

export type DealStatus = "negotiating" | "confirmed" | "completed" | "cancelled";
export type PaymentStatus = "unpaid" | "partial" | "paid";
export type EarningsPeriod = "weekly" | "monthly" | "yearly";

export interface DealResponse {
  id: number;
  title: string;
  brand_name: string;
  description: string | null;
  deliverables: string | null;
  deal_status: DealStatus;
  shoot_at: string | null;
  payment_amount: number | null;
  currency: string;
  payment_status: PaymentStatus;
  payment_due_date: string | null;
  work_link: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** Same shape as the backend's DealCreate/DealUpdate - a full write payload. */
export interface DealWriteRequest {
  title: string;
  brand_name: string;
  description: string | null;
  deliverables: string | null;
  deal_status: DealStatus;
  shoot_at: string | null;
  payment_amount: number | null;
  currency: string;
  payment_status: PaymentStatus;
  payment_due_date: string | null;
  work_link: string | null;
  notes: string | null;
}

export interface EarningsPeriodPoint {
  period_start: string;
  paid_total: number;
  pending_total: number;
  deals_count: number;
}

export interface CurrencyEarnings {
  currency: string;
  total_paid: number;
  total_pending: number;
  deals_counted: number;
  points: EarningsPeriodPoint[];
}

export interface EarningsSummaryResponse {
  period: EarningsPeriod;
  currencies: CurrencyEarnings[];
  excluded_undated_count: number;
}
