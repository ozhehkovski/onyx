"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type { DateRange } from "@opal/components";
import {
  errorHandlingFetcher,
  FetchError,
  skipRetryOnAuthError,
} from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { buildApiPath } from "@/lib/urlBuilder";
import { downloadExport } from "@/lib/chat-insights/download";
import { buildSessionsUrl, rangeToDateParams } from "@/lib/chat-insights/utils";
import type {
  ExportFormat,
  FeedbackResponse,
  SessionDetail,
  SessionFilters,
  SessionListResponse,
  UsageResponse,
} from "@/lib/chat-insights/types";

const SWR_OPTIONS = {
  revalidateOnFocus: false,
  onErrorRetry: skipRetryOnAuthError,
} as const;

/** True when the backend refuses access, e.g. query history is disabled. */
export function isForbiddenError(error: unknown): boolean {
  return (
    error instanceof FetchError &&
    (error.status === 403 || error.status === 401)
  );
}

export function useChatInsightsUsage(range: DateRange) {
  const url = buildApiPath(SWR_KEYS.chatInsightsUsage, {
    ...rangeToDateParams(range),
  });
  return useSWR<UsageResponse, Error>(url, errorHandlingFetcher, SWR_OPTIONS);
}

export function useChatInsightsFeedback(range: DateRange) {
  const url = buildApiPath(SWR_KEYS.chatInsightsFeedback, {
    ...rangeToDateParams(range),
  });
  return useSWR<FeedbackResponse, Error>(
    url,
    errorHandlingFetcher,
    SWR_OPTIONS
  );
}

/** `page` is 0-based. */
export function useChatInsightsSessions(filters: SessionFilters, page: number) {
  return useSWR<SessionListResponse, Error>(
    buildSessionsUrl(filters, page),
    errorHandlingFetcher,
    { ...SWR_OPTIONS, keepPreviousData: true }
  );
}

export function useChatInsightsSession(sessionId: string) {
  return useSWR<SessionDetail, Error>(
    SWR_KEYS.chatInsightsSession(sessionId),
    errorHandlingFetcher,
    SWR_OPTIONS
  );
}

/**
 * Download state for an export endpoint. `download` resolves to the error
 * (a `FetchError` for HTTP failures) when the export fails, so callers can
 * show their own message.
 */
export function useExportDownload() {
  const [pendingFormat, setPendingFormat] = useState<ExportFormat | null>(null);

  const download = useCallback(
    async (url: string, format: ExportFormat): Promise<Error | null> => {
      setPendingFormat(format);
      try {
        await downloadExport(url, format);
        return null;
      } catch (error) {
        return error instanceof Error ? error : new Error(String(error));
      } finally {
        setPendingFormat(null);
      }
    },
    []
  );

  return { download, pendingFormat };
}
