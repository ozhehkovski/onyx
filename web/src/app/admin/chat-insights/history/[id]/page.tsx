"use client";

import { use } from "react";
import ChatInsightsSessionDetailPage from "@/views/admin/ChatInsights/SessionDetailPage";

export default function ChatInsightsSessionRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ChatInsightsSessionDetailPage sessionId={decodeURIComponent(id)} />;
}
