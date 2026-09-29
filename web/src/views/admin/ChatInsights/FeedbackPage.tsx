"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  Card,
  InputDateRangePicker,
  Table,
  Tag,
  Text,
  createTableColumns,
  rangeForInclusiveDays,
  type DateRange,
} from "@opal/components";
import { Section, SettingsLayouts } from "@opal/layouts";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { useAdminRouteTitle } from "@/lib/adminNavLabels";
import { useChatInsightsFeedback } from "@/lib/chat-insights/hooks";
import type {
  FeedbackByAgent,
  FeedbackByModel,
  FeedbackReason,
  FeedbackResponse,
  RecentFeedback,
} from "@/lib/chat-insights/types";
import {
  AnalyticsChart,
  chartSeries,
  resolveChartState,
} from "@/sections/usage/AnalyticsChart";
import {
  EmptyTableState,
  InsightsCard,
  InsightsError,
  InsightsLoader,
  KpiGrid,
  KpiTile,
  LabelCell,
  NumberCell,
  sessionDetailHref,
  useInsightFormatters,
} from "@/views/admin/ChatInsights/components";

const route = ADMIN_ROUTES.CHAT_INSIGHTS_FEEDBACK;

type Formatters = ReturnType<typeof useInsightFormatters>;

function useRateFormatter() {
  const t = useTranslations("admin.chatInsights.common");
  const f = useInsightFormatters();
  return (rate: number | null) =>
    rate === null ? t("notAvailable") : f.percent(rate);
}

// Both breakdown tables share every column but the first.
interface RatingRow {
  positive: number;
  negative: number;
  satisfaction_rate: number | null;
}

function useRatingColumns<T extends RatingRow>(
  builder: ReturnType<typeof createTableColumns<T>>
) {
  const t = useTranslations("admin.chatInsights.feedback.breakdown");
  const f = useInsightFormatters();
  const rate = useRateFormatter();
  return [
    builder.column((row) => row.positive, {
      id: "positive",
      header: t("columns.positive.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    builder.column((row) => row.negative, {
      id: "negative",
      header: t("columns.negative.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    builder.column((row) => row.satisfaction_rate, {
      id: "satisfaction_rate",
      header: t("columns.satisfaction.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={rate(value)} />,
    }),
  ];
}

const agentColumns = createTableColumns<FeedbackByAgent>();
const modelColumns = createTableColumns<FeedbackByModel>();

function ByAgentTable({ rows }: { rows: FeedbackByAgent[] }) {
  const t = useTranslations("admin.chatInsights.feedback.breakdown");
  const ratingColumns = useRatingColumns(agentColumns);
  const columns = [
    agentColumns.column("name", {
      header: t("columns.agent.header"),
      weight: 40,
      cell: (name) => <LabelCell value={name} />,
    }),
    ...ratingColumns,
  ];
  return (
    <InsightsCard title={t("byAgent.title")}>
      <Table
        data={rows}
        columns={columns}
        getRowId={(row) => `${row.persona_id ?? "none"}-${row.name}`}
        size="md"
        emptyState={<EmptyTableState />}
      />
    </InsightsCard>
  );
}

function ByModelTable({ rows }: { rows: FeedbackByModel[] }) {
  const t = useTranslations("admin.chatInsights.feedback.breakdown");
  const ratingColumns = useRatingColumns(modelColumns);
  const columns = [
    modelColumns.column("model", {
      header: t("columns.model.header"),
      weight: 40,
      cell: (model) => <LabelCell value={model} />,
    }),
    ...ratingColumns,
  ];
  return (
    <InsightsCard title={t("byModel.title")}>
      <Table
        data={rows}
        columns={columns}
        getRowId={(row) => row.model}
        size="md"
        emptyState={<EmptyTableState />}
      />
    </InsightsCard>
  );
}

function ReasonsList({ reasons }: { reasons: FeedbackReason[] }) {
  const t = useTranslations("admin.chatInsights.feedback.reasons");
  return (
    <InsightsCard title={t("title")} description={t("description")}>
      {reasons.length === 0 ? (
        <EmptyTableState />
      ) : (
        <Section alignItems="stretch" justifyContent="start" gap={0.5}>
          {reasons.map((reason) => (
            <Section
              key={reason.reason}
              flexDirection="row"
              justifyContent="between"
              alignItems="center"
              gap={1}
            >
              <Text font="main-ui-body" color="text-05">
                {reason.reason}
              </Text>
              <Tag
                title={t("count", { count: reason.count })}
                color="red"
                size="md"
              />
            </Section>
          ))}
        </Section>
      )}
    </InsightsCard>
  );
}

function RecentFeedbackItem({ item }: { item: RecentFeedback }) {
  const t = useTranslations("admin.chatInsights.feedback.recent");
  const f = useInsightFormatters();
  const comment = item.feedback_text ?? item.predefined_feedback;
  return (
    <Link
      href={sessionDetailHref(item.chat_session_id)}
      aria-label={t("openSession.ariaLabel")}
    >
      <Card border="solid" rounding={3} padding={3}>
        <Section alignItems="stretch" justifyContent="start" gap={0.5}>
          <Section
            flexDirection="row"
            justifyContent="start"
            alignItems="center"
            gap={0.5}
            wrap
          >
            {item.is_positive === false ? (
              <Tag title={t("negative")} color="red" />
            ) : item.is_positive === true ? (
              <Tag title={t("positive")} color="green" />
            ) : (
              <Tag title={t("unrated")} color="gray" />
            )}
            <Text font="secondary-body" color="text-03">
              {t("meta", {
                user: item.user_email ?? item.user_label,
                agent: item.persona_name ?? t("noAgent"),
                time: f.dateTime(item.time),
              })}
            </Text>
          </Section>
          <Text font="main-ui-action" color="text-05" maxLines={2}>
            {item.query ?? t("noQuery")}
          </Text>
          {item.answer_preview && (
            <Text font="secondary-body" color="text-03" maxLines={2}>
              {item.answer_preview}
            </Text>
          )}
          {comment && (
            <Text font="main-ui-body" color="text-04" maxLines={3}>
              {t("comment", { comment })}
            </Text>
          )}
        </Section>
      </Card>
    </Link>
  );
}

function RecentFeedbackList({ items }: { items: RecentFeedback[] }) {
  const t = useTranslations("admin.chatInsights.feedback.recent");
  return (
    <InsightsCard title={t("title")} description={t("description")}>
      {items.length === 0 ? (
        <EmptyTableState />
      ) : (
        <Section alignItems="stretch" justifyContent="start" gap={0.5}>
          {items.map((item) => (
            <RecentFeedbackItem key={item.feedback_id} item={item} />
          ))}
        </Section>
      )}
    </InsightsCard>
  );
}

function FeedbackKpis({ data, f }: { data: FeedbackResponse; f: Formatters }) {
  const t = useTranslations("admin.chatInsights.feedback.kpi");
  const rate = useRateFormatter();
  return (
    <KpiGrid>
      <KpiTile
        label={t("positive.label")}
        value={f.count(data.totals.positive)}
      />
      <KpiTile
        label={t("negative.label")}
        value={f.count(data.totals.negative)}
      />
      <KpiTile
        label={t("satisfaction.label")}
        value={rate(data.totals.satisfaction_rate)}
      />
      <KpiTile
        label={t("coverage.label")}
        value={rate(data.totals.rating_coverage)}
        hint={t("coverage.hint", {
          count: data.totals.assistant_messages,
        })}
      />
    </KpiGrid>
  );
}

function FeedbackContent({ range }: { range: DateRange }) {
  const t = useTranslations("admin.chatInsights.feedback");
  const f = useInsightFormatters();
  const { data, error, isLoading } = useChatInsightsFeedback(range);

  if (error) return <InsightsError error={error} />;
  if (isLoading || !data) return <InsightsLoader />;

  return (
    <>
      <FeedbackKpis data={data} f={f} />
      <AnalyticsChart
        title={t("chart.title")}
        description={t("chart.description")}
        timeRange={range}
        allowDecimals={false}
        state={resolveChartState({
          isLoading: false,
          error: null,
          errorMessage: "",
          emptyMessage: t("chart.empty"),
          series: [
            chartSeries(
              t("chart.series.positive.label"),
              data.daily,
              (entry) => entry.positive
            ),
            chartSeries(
              t("chart.series.negative.label"),
              data.daily,
              (entry) => entry.negative
            ),
          ],
        })}
      />
      <ByAgentTable rows={data.by_agent} />
      <ByModelTable rows={data.by_model} />
      <ReasonsList reasons={data.predefined_reasons} />
      <RecentFeedbackList items={data.recent} />
    </>
  );
}

export default function ChatInsightsFeedbackPage() {
  const t = useTranslations("admin.chatInsights.feedback");
  const adminRouteTitle = useAdminRouteTitle();
  const [range, setRange] = useState<DateRange>(() =>
    rangeForInclusiveDays(30)
  );

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={route.icon}
        title={adminRouteTitle(route)}
        description={t("page.description")}
        divider
        actions={[
          <InputDateRangePicker
            key="range"
            value={range}
            onValueChange={(next) => {
              if (next) setRange(next);
            }}
          />,
        ]}
      />
      <SettingsLayouts.Body>
        <FeedbackContent range={range} />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
