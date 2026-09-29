/** Response shapes of the `/api/admin/chat-insights/*` endpoints. */

/** Calendar day, `YYYY-MM-DD`. */
export type CalendarDay = string;
/** ISO-8601 UTC timestamp. */
export type IsoDateTime = string;

export type ExportFormat = "json" | "csv";

export const SESSION_FEEDBACK_FILTERS = [
  "all",
  "positive",
  "negative",
  "mixed",
  "none",
] as const;
export type SessionFeedbackFilter = (typeof SESSION_FEEDBACK_FILTERS)[number];

export type SessionFeedback = Exclude<SessionFeedbackFilter, "all">;

// ── Usage ─────────────────────────────────────────────────────────────────

export interface UsageTotals {
  sessions: number;
  user_messages: number;
  assistant_messages: number;
  active_users: number;
  avg_messages_per_session: number;
}

export interface UsageDailyEntry {
  date: CalendarDay;
  sessions: number;
  user_messages: number;
  active_users: number;
}

export interface UsageTopUser {
  user_id: string | null;
  user_email: string | null;
  user_label: string;
  sessions: number;
  user_messages: number;
  last_active: IsoDateTime;
}

export interface UsageTopAgent {
  persona_id: number | null;
  name: string;
  sessions: number;
  user_messages: number;
  unique_users: number;
}

export interface UsageModelEntry {
  model: string;
  assistant_messages: number;
}

export interface UsageResponse {
  start: CalendarDay;
  end: CalendarDay;
  totals: UsageTotals;
  daily: UsageDailyEntry[];
  top_users: UsageTopUser[];
  top_agents: UsageTopAgent[];
  models: UsageModelEntry[];
}

// ── Feedback ──────────────────────────────────────────────────────────────

export interface FeedbackTotals {
  positive: number;
  negative: number;
  assistant_messages: number;
  /** positive / (positive + negative), 0..1. */
  satisfaction_rate: number | null;
  /** Rated assistant messages / assistant messages, 0..1. */
  rating_coverage: number | null;
}

export interface FeedbackDailyEntry {
  date: CalendarDay;
  positive: number;
  negative: number;
}

export interface FeedbackByAgent {
  persona_id: number | null;
  name: string;
  positive: number;
  negative: number;
  satisfaction_rate: number | null;
}

export interface FeedbackByModel {
  model: string;
  positive: number;
  negative: number;
  satisfaction_rate: number | null;
}

export interface FeedbackReason {
  reason: string;
  count: number;
}

export interface RecentFeedback {
  feedback_id: number;
  chat_session_id: string;
  message_id: number;
  is_positive: boolean | null;
  feedback_text: string | null;
  predefined_feedback: string | null;
  user_email: string | null;
  user_label: string;
  persona_name: string | null;
  time: IsoDateTime;
  query: string | null;
  answer_preview: string | null;
}

export interface FeedbackResponse {
  start: CalendarDay;
  end: CalendarDay;
  totals: FeedbackTotals;
  daily: FeedbackDailyEntry[];
  by_agent: FeedbackByAgent[];
  by_model: FeedbackByModel[];
  predefined_reasons: FeedbackReason[];
  recent: RecentFeedback[];
}

// ── Query history ─────────────────────────────────────────────────────────

export interface SessionListItem {
  id: string;
  user_email: string | null;
  user_label: string;
  persona_id: number | null;
  persona_name: string | null;
  first_user_message: string | null;
  message_count: number;
  time_created: IsoDateTime;
  time_updated: IsoDateTime;
  feedback: SessionFeedback;
  positive_count: number;
  negative_count: number;
  onyxbot_flow: boolean;
  deleted: boolean;
}

export interface SessionListResponse {
  total: number;
  page: number;
  page_size: number;
  items: SessionListItem[];
}

export interface SessionMessageFeedback {
  is_positive: boolean | null;
  feedback_text: string | null;
  predefined_feedback: string | null;
}

export interface SessionMessage {
  id: number;
  message_type: "user" | "assistant";
  message: string;
  time_sent: IsoDateTime;
  model: string | null;
  error: string | null;
  feedback: SessionMessageFeedback[];
}

export interface SessionDetail {
  id: string;
  user_email: string | null;
  user_label: string;
  persona_name: string | null;
  description: string | null;
  time_created: IsoDateTime;
  deleted: boolean;
  messages: SessionMessage[];
}

/** Filters shared by the session list and the bulk export. */
export interface SessionFilters {
  start?: CalendarDay;
  end?: CalendarDay;
  feedback: SessionFeedbackFilter;
  userEmail: string;
  personaId?: number;
  q: string;
}
