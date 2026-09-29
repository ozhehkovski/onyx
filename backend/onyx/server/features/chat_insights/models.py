from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class SessionFeedbackFilter(str, Enum):
    ALL = "all"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NONE = "none"


class SessionFeedbackStatus(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NONE = "none"


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


# ---- Usage dashboard ----


class UsageTotals(BaseModel):
    sessions: int
    user_messages: int
    assistant_messages: int
    active_users: int
    avg_messages_per_session: float


class DailyUsage(BaseModel):
    date: str
    sessions: int
    user_messages: int
    active_users: int


class TopUser(BaseModel):
    user_id: str | None
    user_email: str | None
    user_label: str
    sessions: int
    user_messages: int
    last_active: datetime


class TopAgent(BaseModel):
    persona_id: int | None
    name: str
    sessions: int
    user_messages: int
    unique_users: int


class ModelUsage(BaseModel):
    model: str
    assistant_messages: int


class UsageResponse(BaseModel):
    start: str
    end: str
    totals: UsageTotals
    daily: list[DailyUsage]
    top_users: list[TopUser]
    top_agents: list[TopAgent]
    models: list[ModelUsage]


# ---- Chat ratings analytics ----


class FeedbackTotals(BaseModel):
    positive: int
    negative: int
    assistant_messages: int
    satisfaction_rate: float | None
    rating_coverage: float | None


class DailyFeedback(BaseModel):
    date: str
    positive: int
    negative: int


class AgentFeedback(BaseModel):
    persona_id: int | None
    name: str
    positive: int
    negative: int
    satisfaction_rate: float | None


class ModelFeedback(BaseModel):
    model: str
    positive: int
    negative: int
    satisfaction_rate: float | None


class FeedbackReason(BaseModel):
    reason: str
    count: int


class RecentFeedback(BaseModel):
    feedback_id: int
    chat_session_id: UUID
    message_id: int
    is_positive: bool | None
    feedback_text: str | None
    predefined_feedback: str | None
    user_email: str | None
    user_label: str
    persona_name: str | None
    time: datetime
    query: str | None
    answer_preview: str | None


class FeedbackAnalyticsResponse(BaseModel):
    start: str
    end: str
    totals: FeedbackTotals
    daily: list[DailyFeedback]
    by_agent: list[AgentFeedback]
    by_model: list[ModelFeedback]
    predefined_reasons: list[FeedbackReason]
    recent: list[RecentFeedback]


# ---- Query history ----


class ChatSessionSummary(BaseModel):
    id: UUID
    user_email: str | None
    user_label: str
    persona_id: int | None
    persona_name: str | None
    first_user_message: str | None
    message_count: int
    time_created: datetime
    time_updated: datetime
    feedback: SessionFeedbackStatus
    positive_count: int
    negative_count: int
    onyxbot_flow: bool
    deleted: bool


class ChatSessionPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ChatSessionSummary]


class MessageFeedbackSnapshot(BaseModel):
    is_positive: bool | None
    feedback_text: str | None
    predefined_feedback: str | None


class InsightMessage(BaseModel):
    id: int
    message_type: str
    message: str
    time_sent: datetime
    model: str | None
    error: str | None
    feedback: list[MessageFeedbackSnapshot]


class ChatSessionDetail(BaseModel):
    id: UUID
    user_email: str | None
    user_label: str
    persona_name: str | None
    description: str | None
    time_created: datetime
    deleted: bool
    messages: list[InsightMessage]


def session_feedback_status(positive: int, negative: int) -> SessionFeedbackStatus:
    if positive and negative:
        return SessionFeedbackStatus.MIXED
    if positive:
        return SessionFeedbackStatus.POSITIVE
    if negative:
        return SessionFeedbackStatus.NEGATIVE
    return SessionFeedbackStatus.NONE


def satisfaction_rate(positive: int, negative: int) -> float | None:
    rated = positive + negative
    return positive / rated if rated else None
