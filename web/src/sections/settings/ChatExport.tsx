"use client";

import { useTranslations } from "next-intl";
import { Button, Card } from "@opal/components";
import { Content, InputHorizontal, Section, toast } from "@opal/layouts";
import { SvgDownload } from "@opal/icons";
import { useExportDownload } from "@/lib/chat-insights/hooks";
import type { ExportFormat } from "@/lib/chat-insights/types";
import { buildUserChatExportUrl } from "@/lib/chat-insights/utils";

/** "Export my chats" settings block: downloads the user's own chats. */
export default function ChatExport() {
  const t = useTranslations("settings.chatExport");
  const { download, pendingFormat } = useExportDownload();

  async function handleExport(format: ExportFormat) {
    const error = await download(buildUserChatExportUrl(format), format);
    if (error === null) return;
    console.error("Chat export failed:", error);
    toast.error(t("toasts.failed"));
  }

  return (
    <Section gap={3}>
      <Content
        title={t("title")}
        sizePreset="main-content"
        variant="section"
        width="full"
      />
      <Card border="solid" rounding={4}>
        <Section alignItems="start" height="fit">
          <InputHorizontal
            title={t("exportChats.title")}
            description={t("exportChats.description")}
            center
          >
            <Section
              flexDirection="row"
              justifyContent="end"
              gap={0.5}
              width="fit"
              height="fit"
            >
              <Button
                prominence="secondary"
                icon={SvgDownload}
                disabled={pendingFormat !== null}
                onClick={() => void handleExport("json")}
              >
                {t("exportChats.json")}
              </Button>
              <Button
                prominence="secondary"
                icon={SvgDownload}
                disabled={pendingFormat !== null}
                onClick={() => void handleExport("csv")}
              >
                {t("exportChats.csv")}
              </Button>
            </Section>
          </InputHorizontal>
        </Section>
      </Card>
    </Section>
  );
}
