"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  InputDateRangePicker,
  Table,
  createTableColumns,
  rangeForInclusiveDays,
  type DateRange,
} from "@opal/components";
import { SettingsLayouts } from "@opal/layouts";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { useAdminRouteTitle } from "@/lib/adminNavLabels";
import { useChatInsightsUsage } from "@/lib/chat-insights/hooks";
import type {
  UsageModelEntry,
  UsageResponse,
  UsageTopAgent,
  UsageTopUser,
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
  useInsightFormatters,
} from "@/views/admin/ChatInsights/components";

const route = ADMIN_ROUTES.CHAT_INSIGHTS_USAGE;

type Formatters = ReturnType<typeof useInsightFormatters>;

const userColumns = createTableColumns<UsageTopUser>();
const agentColumns = createTableColumns<UsageTopAgent>();
const modelColumns = createTableColumns<UsageModelEntry>();

function TopUsersTable({ rows }: { rows: UsageTopUser[] }) {
  const t = useTranslations("admin.chatInsights.usage.topUsers");
  const f = useInsightFormatters();
  const columns = [
    userColumns.column("user_label", {
      header: t("columns.user.header"),
      weight: 40,
      cell: (label, row) => <LabelCell value={row.user_email ?? label} />,
    }),
    userColumns.column("sessions", {
      header: t("columns.sessions.header"),
      weight: 15,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    userColumns.column("user_messages", {
      header: t("columns.userMessages.header"),
      weight: 15,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    userColumns.column("last_active", {
      header: t("columns.lastActive.header"),
      weight: 30,
      alignment: "right",
      cell: (value) => <NumberCell value={f.dateTime(value)} />,
    }),
  ];
  return (
    <InsightsCard title={t("title")}>
      <Table
        data={rows}
        columns={columns}
        getRowId={(row) => row.user_id ?? row.user_label}
        size="md"
        emptyState={<EmptyTableState />}
      />
    </InsightsCard>
  );
}

function TopAgentsTable({ rows }: { rows: UsageTopAgent[] }) {
  const t = useTranslations("admin.chatInsights.usage.topAgents");
  const f = useInsightFormatters();
  const columns = [
    agentColumns.column("name", {
      header: t("columns.agent.header"),
      weight: 40,
      cell: (name) => <LabelCell value={name} />,
    }),
    agentColumns.column("sessions", {
      header: t("columns.sessions.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    agentColumns.column("user_messages", {
      header: t("columns.userMessages.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
    agentColumns.column("unique_users", {
      header: t("columns.uniqueUsers.header"),
      weight: 20,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
  ];
  return (
    <InsightsCard title={t("title")}>
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

function ModelsTable({ rows }: { rows: UsageModelEntry[] }) {
  const t = useTranslations("admin.chatInsights.usage.models");
  const f = useInsightFormatters();
  const columns = [
    modelColumns.column("model", {
      header: t("columns.model.header"),
      weight: 60,
      cell: (model) => <LabelCell value={model} />,
    }),
    modelColumns.column("assistant_messages", {
      header: t("columns.assistantMessages.header"),
      weight: 40,
      alignment: "right",
      cell: (value) => <NumberCell value={f.count(value)} />,
    }),
  ];
  return (
    <InsightsCard title={t("title")}>
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

function UsageKpis({ data, f }: { data: UsageResponse; f: Formatters }) {
  const t = useTranslations("admin.chatInsights.usage.kpi");
  return (
    <KpiGrid>
      <KpiTile
        label={t("sessions.label")}
        value={f.count(data.totals.sessions)}
      />
      <KpiTile
        label={t("userMessages.label")}
        value={f.count(data.totals.user_messages)}
      />
      <KpiTile
        label={t("activeUsers.label")}
        value={f.count(data.totals.active_users)}
      />
      <KpiTile
        label={t("avgMessages.label")}
        value={f.decimal(data.totals.avg_messages_per_session)}
      />
    </KpiGrid>
  );
}

function UsageContent({ range }: { range: DateRange }) {
  const t = useTranslations("admin.chatInsights.usage");
  const f = useInsightFormatters();
  const { data, error, isLoading } = useChatInsightsUsage(range);

  if (error) return <InsightsError error={error} />;
  if (isLoading || !data) return <InsightsLoader />;

  return (
    <>
      <UsageKpis data={data} f={f} />
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
              t("chart.series.sessions.label"),
              data.daily,
              (entry) => entry.sessions
            ),
            chartSeries(
              t("chart.series.userMessages.label"),
              data.daily,
              (entry) => entry.user_messages
            ),
            chartSeries(
              t("chart.series.activeUsers.label"),
              data.daily,
              (entry) => entry.active_users
            ),
          ],
        })}
      />
      <TopUsersTable rows={data.top_users} />
      <TopAgentsTable rows={data.top_agents} />
      <ModelsTable rows={data.models} />
    </>
  );
}

export default function ChatInsightsUsagePage() {
  const t = useTranslations("admin.chatInsights.usage");
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
        <UsageContent range={range} />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
