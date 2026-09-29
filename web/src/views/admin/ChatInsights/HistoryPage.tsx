"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  InputDateRangePicker,
  InputSingleSelect,
  InputTypeIn,
  Pagination,
  Table,
  Tag,
  Text,
  createTableColumns,
  rangeForInclusiveDays,
  type DateRange,
} from "@opal/components";
import { Section, SettingsLayouts } from "@opal/layouts";
import { SvgUser } from "@opal/icons";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { useAdminRouteTitle } from "@/lib/adminNavLabels";
import {
  isForbiddenError,
  useChatInsightsSessions,
} from "@/lib/chat-insights/hooks";
import {
  SESSION_FEEDBACK_FILTERS,
  type SessionFeedbackFilter,
  type SessionFilters,
  type SessionListItem,
} from "@/lib/chat-insights/types";
import {
  buildSessionsExportUrl,
  isSessionFeedbackFilter,
  rangeToDateParams,
} from "@/lib/chat-insights/utils";
import {
  EmptyTableState,
  FeedbackTag,
  HistoryDisabledState,
  InsightsError,
  InsightsLoader,
  LabelCell,
  NumberCell,
  exportButtons,
  sessionDetailHref,
  useInsightFormatters,
} from "@/views/admin/ChatInsights/components";

const route = ADMIN_ROUTES.CHAT_INSIGHTS_HISTORY;

/** Delay before a typed filter hits the backend. */
const TEXT_FILTER_DEBOUNCE_MS = 400;

function useDebounced(value: string): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(
      () => setDebounced(value),
      TEXT_FILTER_DEBOUNCE_MS
    );
    return () => clearTimeout(timer);
  }, [value]);
  return debounced;
}

const tc = createTableColumns<SessionListItem>();

function useSessionColumns() {
  const t = useTranslations("admin.chatInsights.history");
  const f = useInsightFormatters();
  return [
    tc.qualifier({ content: "icon", getContent: () => SvgUser }),
    tc.column("user_label", {
      header: t("columns.user.header"),
      weight: 18,
      enableSorting: false,
      cell: (label, row) => <LabelCell value={row.user_email ?? label} />,
    }),
    tc.column((row) => row.persona_name, {
      id: "persona_name",
      header: t("columns.agent.header"),
      weight: 14,
      enableSorting: false,
      cell: (name) => <LabelCell value={name ?? t("noAgent")} />,
    }),
    tc.column((row) => row.first_user_message, {
      id: "first_user_message",
      header: t("columns.firstMessage.header"),
      weight: 32,
      enableSorting: false,
      cell: (message, row) => (
        <Section
          flexDirection="row"
          justifyContent="start"
          alignItems="center"
          gap={0.5}
        >
          <Text font="main-ui-body" color="text-05" maxLines={1}>
            {message ?? t("noFirstMessage")}
          </Text>
          {row.deleted && <Tag title={t("deletedTag")} color="gray" />}
        </Section>
      ),
    }),
    tc.column("message_count", {
      header: t("columns.messages.header"),
      weight: 8,
      alignment: "right",
      enableSorting: false,
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    tc.column("feedback", {
      header: t("columns.feedback.header"),
      weight: 10,
      enableSorting: false,
      cell: (feedback) => <FeedbackTag feedback={feedback} />,
    }),
    tc.column("time_created", {
      header: t("columns.created.header"),
      weight: 18,
      alignment: "right",
      enableSorting: false,
      cell: (value) => <NumberCell value={f.dateTime(value)} />,
    }),
  ];
}

interface SessionsTableProps {
  filters: SessionFilters;
  page: number;
  onPageChange: (page: number) => void;
}

function SessionsTable({ filters, page, onPageChange }: SessionsTableProps) {
  const t = useTranslations("admin.chatInsights.history");
  const router = useRouter();
  const columns = useSessionColumns();
  const { data, error, isLoading } = useChatInsightsSessions(filters, page);

  if (error) {
    return isForbiddenError(error) ? (
      <HistoryDisabledState />
    ) : (
      <InsightsError error={error} />
    );
  }
  if (isLoading && !data) return <InsightsLoader />;
  if (!data) return null;

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <Section alignItems="stretch" justifyContent="start" gap={1}>
      <Table
        data={data.items}
        columns={columns}
        getRowId={(row) => row.id}
        getRowLabel={(row) =>
          t("rowLabel", {
            user: row.user_email ?? row.user_label,
          })
        }
        onRowClick={(row) => router.push(sessionDetailHref(row.id))}
        size="md"
        emptyState={<EmptyTableState />}
      />
      {data.total > data.page_size && (
        <Section flexDirection="row" justifyContent="end">
          <Pagination
            variant="count"
            pageSize={data.page_size}
            totalItems={data.total}
            currentPage={page + 1}
            totalPages={totalPages}
            onChange={(next) => onPageChange(next - 1)}
          />
        </Section>
      )}
    </Section>
  );
}

interface FiltersBarProps {
  range: DateRange;
  onRangeChange: (range: DateRange) => void;
  feedback: SessionFeedbackFilter;
  onFeedbackChange: (feedback: SessionFeedbackFilter) => void;
  userEmail: string;
  onUserEmailChange: (value: string) => void;
  q: string;
  onQChange: (value: string) => void;
}

function FiltersBar({
  range,
  onRangeChange,
  feedback,
  onFeedbackChange,
  userEmail,
  onUserEmailChange,
  q,
  onQChange,
}: FiltersBarProps) {
  const t = useTranslations("admin.chatInsights.history.filters");
  const feedbackLabels = {
    all: t("feedback.options.all"),
    positive: t("feedback.options.positive"),
    negative: t("feedback.options.negative"),
    mixed: t("feedback.options.mixed"),
    none: t("feedback.options.none"),
  } satisfies Record<SessionFeedbackFilter, string>;

  return (
    <Section alignItems="stretch" justifyContent="start" gap={0.75}>
      <Section
        flexDirection="row"
        justifyContent="start"
        alignItems="center"
        gap={0.75}
        wrap
      >
        <InputDateRangePicker
          value={range}
          onValueChange={(next) => {
            if (next) onRangeChange(next);
          }}
        />
        <Section width={14} height="fit">
          <InputSingleSelect
            value={feedback}
            defaultOption="all"
            placeholder={t("feedback.placeholder")}
            onValueChange={(value) => {
              if (isSessionFeedbackFilter(value)) onFeedbackChange(value);
            }}
            options={SESSION_FEEDBACK_FILTERS.map((value) => ({
              value,
              title: feedbackLabels[value],
            }))}
          />
        </Section>
      </Section>
      <Section
        flexDirection="row"
        justifyContent="start"
        alignItems="center"
        gap={0.75}
      >
        <InputTypeIn
          searchIcon
          clearButton
          value={q}
          placeholder={t("q.placeholder")}
          aria-label={t("q.placeholder")}
          onChange={(event) => onQChange(event.target.value)}
        />
        <InputTypeIn
          clearButton
          value={userEmail}
          placeholder={t("userEmail.placeholder")}
          aria-label={t("userEmail.placeholder")}
          onChange={(event) => onUserEmailChange(event.target.value)}
        />
      </Section>
    </Section>
  );
}

export default function ChatInsightsHistoryPage() {
  const t = useTranslations("admin.chatInsights.history");
  const adminRouteTitle = useAdminRouteTitle();
  const [range, setRange] = useState<DateRange>(() =>
    rangeForInclusiveDays(30)
  );
  const [feedback, setFeedback] = useState<SessionFeedbackFilter>("all");
  const [userEmail, setUserEmail] = useState("");
  const [q, setQ] = useState("");
  const debouncedUserEmail = useDebounced(userEmail);
  const debouncedQ = useDebounced(q);

  const filters: SessionFilters = {
    ...rangeToDateParams(range),
    feedback,
    userEmail: debouncedUserEmail,
    q: debouncedQ,
  };

  // The page belongs to one filter set: any filter change starts at page 0.
  const filtersKey = JSON.stringify(filters);
  const [pageState, setPageState] = useState({ key: filtersKey, page: 0 });
  const page = pageState.key === filtersKey ? pageState.page : 0;

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={route.icon}
        title={adminRouteTitle(route)}
        description={t("page.description")}
        divider
        actions={exportButtons({
          buildUrl: (format) => buildSessionsExportUrl(filters, format),
        })}
      />
      <SettingsLayouts.Body>
        <FiltersBar
          range={range}
          onRangeChange={setRange}
          feedback={feedback}
          onFeedbackChange={setFeedback}
          userEmail={userEmail}
          onUserEmailChange={setUserEmail}
          q={q}
          onQChange={setQ}
        />
        <SessionsTable
          filters={filters}
          page={page}
          onPageChange={(next) => setPageState({ key: filtersKey, page: next })}
        />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
