"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button, Card, Tag, Text } from "@opal/components";
import { IllustrationContent, Section, SettingsLayouts } from "@opal/layouts";
import { SvgArrowLeft } from "@opal/icons";
import SvgNotFound from "@opal/illustrations/not-found";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { FetchError, isNotFoundError } from "@/lib/fetcher";
import {
  isForbiddenError,
  useChatInsightsSession,
} from "@/lib/chat-insights/hooks";
import type {
  SessionDetail,
  SessionMessage,
  SessionMessageFeedback,
} from "@/lib/chat-insights/types";
import { buildSessionExportUrl } from "@/lib/chat-insights/utils";
import {
  HistoryDisabledState,
  InsightsError,
  InsightsLoader,
  exportButtons,
  useInsightFormatters,
} from "@/views/admin/ChatInsights/components";

const route = ADMIN_ROUTES.CHAT_INSIGHTS_HISTORY;

function MessageFeedback({ feedback }: { feedback: SessionMessageFeedback }) {
  const t = useTranslations("admin.chatInsights.session.feedback");
  const comment = feedback.feedback_text ?? feedback.predefined_feedback;
  return (
    <Section
      flexDirection="row"
      justifyContent="start"
      alignItems="center"
      gap={0.5}
      wrap
    >
      {feedback.is_positive === false ? (
        <Tag title={t("negative")} color="red" />
      ) : feedback.is_positive === true ? (
        <Tag title={t("positive")} color="green" />
      ) : (
        <Tag title={t("unrated")} color="gray" />
      )}
      {feedback.predefined_feedback && feedback.feedback_text && (
        <Tag title={feedback.predefined_feedback} color="gray" />
      )}
      {comment && (
        <Text font="secondary-body" color="text-03">
          {comment}
        </Text>
      )}
    </Section>
  );
}

function MessageBubble({ message }: { message: SessionMessage }) {
  const t = useTranslations("admin.chatInsights.session");
  const f = useInsightFormatters();
  const isUser = message.message_type === "user";

  return (
    // Bubble alignment follows the speaker; Section has no self-alignment.
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className="max-w-[85%]">
        <Card
          border="solid"
          rounding={4}
          padding={4}
          color={isUser ? "background-tint-01" : "background-tint-00"}
        >
          <Section alignItems="stretch" justifyContent="start" gap={0.5}>
            <Section
              flexDirection="row"
              justifyContent="start"
              alignItems="center"
              gap={0.5}
              wrap
            >
              <Text font="secondary-action" color="text-04">
                {isUser ? t("roles.user") : t("roles.assistant")}
              </Text>
              <Text font="secondary-body" color="text-03">
                {f.dateTime(message.time_sent)}
              </Text>
              {message.model && (
                <Tag title={t("model", { model: message.model })} />
              )}
            </Section>
            <Text
              as="p"
              font="main-content-body"
              color="text-05"
              wordWrap="wrap-break-word"
            >
              {message.message}
            </Text>
            {message.error && (
              <Text font="secondary-body" color="text-03">
                {t("error", { error: message.error })}
              </Text>
            )}
            {message.feedback.map((feedback, index) => (
              <MessageFeedback key={index} feedback={feedback} />
            ))}
          </Section>
        </Card>
      </div>
    </div>
  );
}

function SessionMeta({ session }: { session: SessionDetail }) {
  const t = useTranslations("admin.chatInsights.session.meta");
  const f = useInsightFormatters();
  return (
    <Section
      flexDirection="row"
      justifyContent="start"
      alignItems="center"
      gap={0.75}
      wrap
    >
      <Text font="secondary-body" color="text-03">
        {t("user", { user: session.user_email ?? session.user_label })}
      </Text>
      <Text font="secondary-body" color="text-03">
        {t("agent", { agent: session.persona_name ?? t("noAgent") })}
      </Text>
      <Text font="secondary-body" color="text-03">
        {t("created", { time: f.dateTime(session.time_created) })}
      </Text>
      {session.deleted && <Tag title={t("deleted")} color="gray" />}
    </Section>
  );
}

function SessionBody({ sessionId }: { sessionId: string }) {
  const t = useTranslations("admin.chatInsights.session");
  const { data, error, isLoading } = useChatInsightsSession(sessionId);

  if (error) {
    if (isForbiddenError(error)) return <HistoryDisabledState />;
    // A malformed id fails validation (422); both read as "not found".
    const invalidId = error instanceof FetchError && error.status === 422;
    if (isNotFoundError(error) || invalidId) {
      return (
        <IllustrationContent
          illustration={SvgNotFound}
          title={t("notFound.title")}
        />
      );
    }
    return <InsightsError error={error} />;
  }
  if (isLoading || !data) return <InsightsLoader />;

  return (
    <>
      <SessionMeta session={data} />
      {data.messages.length === 0 ? (
        <Text font="secondary-body" color="text-03">
          {t("noMessages")}
        </Text>
      ) : (
        <Section alignItems="stretch" justifyContent="start" gap={1}>
          {data.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </Section>
      )}
    </>
  );
}

interface SessionDetailPageProps {
  sessionId: string;
}

export default function ChatInsightsSessionDetailPage({
  sessionId,
}: SessionDetailPageProps) {
  const t = useTranslations("admin.chatInsights.session");
  const router = useRouter();
  const { data } = useChatInsightsSession(sessionId);

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={route.icon}
        title={data?.description || t("title")}
        divider
        actions={[
          <Button
            key="back"
            prominence="tertiary"
            icon={SvgArrowLeft}
            onClick={() => router.push(route.path)}
          >
            {t("back")}
          </Button>,
          ...exportButtons({
            buildUrl: (format) => buildSessionExportUrl(sessionId, format),
          }),
        ]}
      />
      <SettingsLayouts.Body>
        <SessionBody sessionId={sessionId} />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
