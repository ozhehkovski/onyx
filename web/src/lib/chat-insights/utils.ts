import type { DateRange } from "@opal/components";
import { formatDateForApiParam } from "@/lib/dateUtils";
import { SWR_KEYS } from "@/lib/swr-keys";
import { buildApiPath } from "@/lib/urlBuilder";
import {
  SESSION_FEEDBACK_FILTERS,
  type ExportFormat,
  type SessionFeedbackFilter,
  type SessionFilters,
} from "@/lib/chat-insights/types";

export const SESSIONS_PAGE_SIZE = 25;

export const DEFAULT_SESSION_FILTERS: SessionFilters = {
  feedback: "all",
  userEmail: "",
  q: "",
};

interface DateParams {
  start: string | undefined;
  end: string | undefined;
}

/**
 * Inclusive `YYYY-MM-DD` bounds for a picker range. The picker builds its
 * dates from UTC calendar parts, so the local calendar day is the UTC day.
 */
export function rangeToDateParams(range: DateRange): DateParams {
  return {
    start: range ? formatDateForApiParam(range.from) : undefined,
    end: range ? formatDateForApiParam(range.to) : undefined,
  };
}

export function isSessionFeedbackFilter(
  value: string
): value is SessionFeedbackFilter {
  return SESSION_FEEDBACK_FILTERS.some((filter) => filter === value);
}

/** Query params shared by the session list and the bulk export. Empty filters are dropped. */
function sessionFilterParams(filters: SessionFilters) {
  const userEmail = filters.userEmail.trim();
  const q = filters.q.trim();
  return {
    start: filters.start,
    end: filters.end,
    feedback: filters.feedback === "all" ? undefined : filters.feedback,
    user_email: userEmail === "" ? undefined : userEmail,
    persona_id: filters.personaId,
    q: q === "" ? undefined : q,
  };
}

/** `page` is 0-based, as the backend expects. */
export function buildSessionsUrl(
  filters: SessionFilters,
  page: number,
  pageSize: number = SESSIONS_PAGE_SIZE
): string {
  return buildApiPath(SWR_KEYS.chatInsightsSessions, {
    ...sessionFilterParams(filters),
    page,
    page_size: pageSize,
  });
}

export function buildSessionsExportUrl(
  filters: SessionFilters,
  format: ExportFormat
): string {
  return buildApiPath(SWR_KEYS.chatInsightsExport, {
    format,
    ...sessionFilterParams(filters),
  });
}

export function buildSessionExportUrl(
  sessionId: string,
  format: ExportFormat
): string {
  return buildApiPath(SWR_KEYS.chatInsightsSessionExport(sessionId), {
    format,
  });
}

export function buildUserChatExportUrl(format: ExportFormat): string {
  return buildApiPath(SWR_KEYS.userChatExport, { format });
}

/**
 * File name from a `Content-Disposition` header. Prefers the RFC 5987
 * `filename*` form. Returns `fallback` when the header has no usable name.
 */
export function filenameFromContentDisposition(
  header: string | null,
  fallback: string
): string {
  if (!header) return fallback;

  const extended = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      // Malformed percent-encoding: fall through to the plain form.
    }
  }

  const plain = /filename\s*=\s*("([^"]*)"|[^;]+)/.exec(header);
  const name = (plain?.[2] ?? plain?.[1])?.trim();
  return name ? name : fallback;
}

/** Local file name used when the server sends no `Content-Disposition`. */
export function defaultExportFilename(
  format: ExportFormat,
  now: Date = new Date()
): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const stamp =
    `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}` +
    `-${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
  return `onyx-chats-${stamp}.${format}`;
}
