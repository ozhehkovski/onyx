"use client";

import type { ReactNode } from "react";
import type { Route } from "next";
import { useFormatter, useTranslations } from "next-intl";
import { Button, Card, MessageCard, Tag, Text } from "@opal/components";
import { IllustrationContent, PageLoader, Section, toast } from "@opal/layouts";
import { SvgDownload, SvgX } from "@opal/icons";
import SvgNoAccess from "@opal/illustrations/no-access";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { isForbiddenError, useExportDownload } from "@/lib/chat-insights/hooks";
import type { ExportFormat, SessionFeedback } from "@/lib/chat-insights/types";

/** Admin detail page of one chat session. */
export function sessionDetailHref(sessionId: string): Route {
  // SAFETY: matches the typed `/admin/chat-insights/history/[id]` route;
  // typed routes only accept literal slugs, not a runtime id.
  return `${ADMIN_ROUTES.CHAT_INSIGHTS_HISTORY.path}/${encodeURIComponent(sessionId)}` as Route;
}

// ── Formatting ────────────────────────────────────────────────────────────

/** Locale-aware formatters for counts, rates and timestamps. */
export function useInsightFormatters() {
  const format = useFormatter();
  return {
    count: (value: number) => format.number(value),
    decimal: (value: number) =>
      format.number(value, { maximumFractionDigits: 1 }),
    percent: (value: number) =>
      format.number(value, { style: "percent", maximumFractionDigits: 1 }),
    dateTime: (iso: string) =>
      format.dateTime(new Date(iso), {
        dateStyle: "medium",
        timeStyle: "short",
      }),
  };
}

// ── Layout pieces ─────────────────────────────────────────────────────────

interface KpiTileProps {
  label: string;
  value: string;
  hint?: string;
}

export function KpiTile({ label, value, hint }: KpiTileProps) {
  return (
    <Card border="solid" rounding={4} padding={4}>
      <Section alignItems="start" justifyContent="start" gap={0.5}>
        <Text font="secondary-body" color="text-03">
          {label}
        </Text>
        <span className="tabular-nums">
          <Text font="heading-h2" color="text-05">
            {value}
          </Text>
        </span>
        {hint && (
          <Text font="secondary-body" color="text-03">
            {hint}
          </Text>
        )}
      </Section>
    </Card>
  );
}

interface KpiGridProps {
  children: ReactNode;
}

export function KpiGrid({ children }: KpiGridProps) {
  // Responsive column count has no Section equivalent.
  return (
    <div className="grid w-full grid-cols-2 gap-4 lg:grid-cols-4">
      {children}
    </div>
  );
}

interface InsightsCardProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function InsightsCard({
  title,
  description,
  children,
}: InsightsCardProps) {
  return (
    <Card border="solid" rounding={4} padding={6}>
      <Section alignItems="stretch" justifyContent="start" gap={1}>
        <Section alignItems="start" justifyContent="start" gap={0.125}>
          <Text font="heading-h3">{title}</Text>
          {description && (
            <Text font="secondary-body" color="text-03">
              {description}
            </Text>
          )}
        </Section>
        {children}
      </Section>
    </Card>
  );
}

// ── Table cells ───────────────────────────────────────────────────────────

interface CellProps {
  value: string;
}

export function NumberCell({ value }: CellProps) {
  return (
    <span className="tabular-nums">
      <Text font="main-ui-body" color="text-05" wordWrap="whitespace-nowrap">
        {value}
      </Text>
    </span>
  );
}

export function LabelCell({ value }: CellProps) {
  return (
    <Text font="main-ui-body" color="text-05" maxLines={1}>
      {value}
    </Text>
  );
}

export function EmptyTableState() {
  const t = useTranslations("admin.chatInsights.common");
  return (
    <Text font="secondary-body" color="text-03">
      {t("emptyTable")}
    </Text>
  );
}

// ── States ────────────────────────────────────────────────────────────────

export function InsightsLoader() {
  return (
    <Section padding={8}>
      <PageLoader />
    </Section>
  );
}

interface InsightsErrorProps {
  error: unknown;
}

/** Load failure. A 403 reads as "no access" rather than a crash. */
export function InsightsError({ error }: InsightsErrorProps) {
  const t = useTranslations("admin.chatInsights.common");
  if (isForbiddenError(error)) {
    return (
      <IllustrationContent
        illustration={SvgNoAccess}
        title={t("forbidden.title")}
        description={t("forbidden.description")}
      />
    );
  }
  return (
    <MessageCard variant="error" icon={SvgX} title={t("loadError.title")} />
  );
}

/** Shown when the backend refuses query history (disabled or no access). */
export function HistoryDisabledState() {
  const t = useTranslations("admin.chatInsights.history");
  return (
    <IllustrationContent
      illustration={SvgNoAccess}
      title={t("disabled.title")}
      description={t("disabled.description")}
    />
  );
}

// ── Tags ──────────────────────────────────────────────────────────────────

interface FeedbackTagProps {
  feedback: SessionFeedback;
}

export function FeedbackTag({ feedback }: FeedbackTagProps) {
  const t = useTranslations("admin.chatInsights.common.feedbackTag");
  switch (feedback) {
    case "positive":
      return <Tag title={t("positive")} color="green" />;
    case "negative":
      return <Tag title={t("negative")} color="red" />;
    case "mixed":
      return <Tag title={t("mixed")} color="amber" />;
    case "none":
      return <Tag title={t("none")} color="gray" />;
  }
}

// ── Export ────────────────────────────────────────────────────────────────

interface ExportButtonsProps {
  buildUrl: (format: ExportFormat) => string;
}

/** "Export JSON" / "Export CSV" header actions. */
export function exportButtons({ buildUrl }: ExportButtonsProps): ReactNode[] {
  return [
    <ExportButton key="json" format="json" buildUrl={buildUrl} />,
    <ExportButton key="csv" format="csv" buildUrl={buildUrl} />,
  ];
}

interface ExportButtonProps {
  format: ExportFormat;
  buildUrl: (format: ExportFormat) => string;
}

function ExportButton({ format, buildUrl }: ExportButtonProps) {
  const t = useTranslations("admin.chatInsights.common.export");
  const { download, pendingFormat } = useExportDownload();

  async function handleClick() {
    const error = await download(buildUrl(format), format);
    if (error === null) return;
    console.error("Chat export failed:", error);
    toast.error(
      isForbiddenError(error) ? t("toasts.forbidden") : t("toasts.failed")
    );
  }

  return (
    <Button
      prominence="secondary"
      icon={SvgDownload}
      disabled={pendingFormat !== null}
      onClick={() => void handleClick()}
    >
      {format === "json" ? t("json") : t("csv")}
    </Button>
  );
}
