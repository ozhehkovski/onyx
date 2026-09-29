"""Queries for the admin Chat Insights pages: usage, chat ratings, query history
and chat export."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, Select, and_, cast, distinct, exists, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased, selectinload
from sqlalchemy.sql.elements import ColumnElement

from onyx.configs.constants import MessageType
from onyx.db.enums import IncognitoRecordMode
from onyx.db.models import ChatMessage, ChatMessageFeedback, ChatSession, Persona, User
from onyx.server.features.chat_insights.models import (
    AgentFeedback,
    ChatSessionDetail,
    ChatSessionSummary,
    DailyFeedback,
    DailyUsage,
    FeedbackReason,
    FeedbackTotals,
    InsightMessage,
    MessageFeedbackSnapshot,
    ModelFeedback,
    ModelUsage,
    RecentFeedback,
    SessionFeedbackFilter,
    TopAgent,
    TopUser,
    UsageTotals,
    satisfaction_rate,
    session_feedback_status,
)

# Maps (user_id, email) to the (email, label) pair shown to admins, so the
# API layer can anonymize identities without a second pass over results.
IdentityResolver = Callable[[UUID | None, str | None], tuple[str | None, str]]

_CONVERSATION_TYPES = (MessageType.USER, MessageType.ASSISTANT)
_UNKNOWN_MODEL = "unknown"
_DEFAULT_AGENT_NAME = "—"
_PREVIEW_CHARS = 300

# fastapi-users declares these as plain attributes, so use the table columns
# to keep SQL expressions typed.
_USER_EMAIL = User.__table__.c.email
_USER_ID = User.__table__.c.id


@dataclass(frozen=True)
class ChatSessionFilters:
    start: datetime
    end: datetime
    feedback: SessionFeedbackFilter = SessionFeedbackFilter.ALL
    user_email: str | None = None
    persona_id: int | None = None
    query: str | None = None


_DateTimeColumn = ColumnElement[datetime] | InstrumentedAttribute[datetime]


def _utc_day(column: _DateTimeColumn) -> ColumnElement[date]:
    return cast(func.timezone("UTC", column), Date)


def _in_range(
    column: _DateTimeColumn, start: datetime, end: datetime
) -> ColumnElement[bool]:
    return and_(column >= start, column < end)


def _recorded_session() -> ColumnElement[bool]:
    """Sessions whose conversation content is stored in Postgres."""
    return or_(
        ChatSession.incognito_record_mode.is_(None),
        ChatSession.incognito_record_mode != IncognitoRecordMode.USAGE_ONLY,
    )


def _day_range(start: datetime, end: datetime) -> list[date]:
    first = start.date()
    last = (end - timedelta(microseconds=1)).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


# ---------------------------------------------------------------------------
# Usage dashboard
# ---------------------------------------------------------------------------


def fetch_usage_totals(
    db_session: Session, start: datetime, end: datetime
) -> UsageTotals:
    in_range = _in_range(ChatMessage.time_sent, start, end)
    row = db_session.execute(
        select(
            func.count(distinct(ChatMessage.chat_session_id)),
            func.count().filter(ChatMessage.message_type == MessageType.USER),
            func.count().filter(ChatMessage.message_type == MessageType.ASSISTANT),
            func.count(distinct(ChatSession.user_id)).filter(
                ChatMessage.message_type == MessageType.USER
            ),
        )
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .where(in_range, ChatMessage.message_type.in_(_CONVERSATION_TYPES))
    ).one()
    sessions, user_messages, assistant_messages, active_users = (
        int(row[0]),
        int(row[1]),
        int(row[2]),
        int(row[3]),
    )
    return UsageTotals(
        sessions=sessions,
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        active_users=active_users,
        avg_messages_per_session=(
            round((user_messages + assistant_messages) / sessions, 2)
            if sessions
            else 0.0
        ),
    )


def fetch_daily_usage(
    db_session: Session, start: datetime, end: datetime
) -> list[DailyUsage]:
    day = _utc_day(ChatMessage.time_sent).label("day")
    rows = db_session.execute(
        select(
            day,
            func.count(distinct(ChatMessage.chat_session_id)),
            func.count(),
            func.count(distinct(ChatSession.user_id)),
        )
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .where(
            _in_range(ChatMessage.time_sent, start, end),
            ChatMessage.message_type == MessageType.USER,
        )
        .group_by(day)
    ).all()
    by_day = {row[0]: row for row in rows}
    result: list[DailyUsage] = []
    for current in _day_range(start, end):
        row = by_day.get(current)
        result.append(
            DailyUsage(
                date=current.isoformat(),
                sessions=int(row[1]) if row else 0,
                user_messages=int(row[2]) if row else 0,
                active_users=int(row[3]) if row else 0,
            )
        )
    return result


def fetch_top_users(
    db_session: Session,
    start: datetime,
    end: datetime,
    identify: IdentityResolver,
    limit: int = 10,
) -> list[TopUser]:
    user_messages = func.count().label("user_messages")
    rows = db_session.execute(
        select(
            ChatSession.user_id,
            _USER_EMAIL,
            func.count(distinct(ChatMessage.chat_session_id)),
            user_messages,
            func.max(ChatMessage.time_sent),
        )
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .outerjoin(User, _USER_ID == ChatSession.user_id)
        .where(
            _in_range(ChatMessage.time_sent, start, end),
            ChatMessage.message_type == MessageType.USER,
        )
        .group_by(ChatSession.user_id, _USER_EMAIL)
        .order_by(user_messages.desc())
        .limit(limit)
    ).all()
    result: list[TopUser] = []
    for user_id, email, sessions, messages, last_active in rows:
        shown_email, label = identify(user_id, email)
        result.append(
            TopUser(
                user_id=str(user_id) if user_id and shown_email else None,
                user_email=shown_email,
                user_label=label,
                sessions=int(sessions),
                user_messages=int(messages),
                last_active=last_active,
            )
        )
    return result


def fetch_top_agents(
    db_session: Session, start: datetime, end: datetime, limit: int = 10
) -> list[TopAgent]:
    user_messages = func.count().label("user_messages")
    rows = db_session.execute(
        select(
            ChatSession.persona_id,
            Persona.name,
            func.count(distinct(ChatMessage.chat_session_id)),
            user_messages,
            func.count(distinct(ChatSession.user_id)),
        )
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .outerjoin(Persona, Persona.id == ChatSession.persona_id)
        .where(
            _in_range(ChatMessage.time_sent, start, end),
            ChatMessage.message_type == MessageType.USER,
        )
        .group_by(ChatSession.persona_id, Persona.name)
        .order_by(user_messages.desc())
        .limit(limit)
    ).all()
    return [
        TopAgent(
            persona_id=persona_id,
            name=name or _DEFAULT_AGENT_NAME,
            sessions=int(sessions),
            user_messages=int(messages),
            unique_users=int(users),
        )
        for persona_id, name, sessions, messages, users in rows
    ]


def fetch_model_usage(
    db_session: Session, start: datetime, end: datetime
) -> list[ModelUsage]:
    model = func.coalesce(ChatMessage.model_display_name, _UNKNOWN_MODEL).label("model")
    count = func.count().label("count")
    rows = db_session.execute(
        select(model, count)
        .where(
            _in_range(ChatMessage.time_sent, start, end),
            ChatMessage.message_type == MessageType.ASSISTANT,
        )
        .group_by(model)
        .order_by(count.desc())
    ).all()
    return [ModelUsage(model=row[0], assistant_messages=int(row[1])) for row in rows]


# ---------------------------------------------------------------------------
# Chat ratings analytics
# ---------------------------------------------------------------------------

_POSITIVE = ChatMessageFeedback.is_positive.is_(True)
_NEGATIVE = ChatMessageFeedback.is_positive.is_(False)


def _feedback_base(start: datetime, end: datetime) -> Select:
    """Feedback rows on assistant messages sent in range.

    chat_feedback has no timestamp, so the rated message's send time dates it.
    """
    return (
        select()
        .select_from(ChatMessageFeedback)
        .join(ChatMessage, ChatMessage.id == ChatMessageFeedback.chat_message_id)
        .where(_in_range(ChatMessage.time_sent, start, end))
    )


def fetch_feedback_totals(
    db_session: Session, start: datetime, end: datetime
) -> FeedbackTotals:
    positive, negative, rated = db_session.execute(
        _feedback_base(start, end).add_columns(
            func.count().filter(_POSITIVE),
            func.count().filter(_NEGATIVE),
            func.count(distinct(ChatMessage.id)).filter(
                ChatMessageFeedback.is_positive.is_not(None)
            ),
        )
    ).one()
    assistant_messages = int(
        db_session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                _in_range(ChatMessage.time_sent, start, end),
                ChatMessage.message_type == MessageType.ASSISTANT,
            )
        )
        or 0
    )
    return FeedbackTotals(
        positive=int(positive),
        negative=int(negative),
        assistant_messages=assistant_messages,
        satisfaction_rate=satisfaction_rate(int(positive), int(negative)),
        rating_coverage=(
            min(int(rated) / assistant_messages, 1.0) if assistant_messages else None
        ),
    )


def fetch_daily_feedback(
    db_session: Session, start: datetime, end: datetime
) -> list[DailyFeedback]:
    day = _utc_day(ChatMessage.time_sent).label("day")
    rows = db_session.execute(
        _feedback_base(start, end)
        .add_columns(
            day, func.count().filter(_POSITIVE), func.count().filter(_NEGATIVE)
        )
        .group_by(day)
    ).all()
    by_day = {row[0]: row for row in rows}
    return [
        DailyFeedback(
            date=current.isoformat(),
            positive=int(by_day[current][1]) if current in by_day else 0,
            negative=int(by_day[current][2]) if current in by_day else 0,
        )
        for current in _day_range(start, end)
    ]


def fetch_feedback_by_agent(
    db_session: Session, start: datetime, end: datetime
) -> list[AgentFeedback]:
    total = func.count().label("total")
    rows = db_session.execute(
        _feedback_base(start, end)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .outerjoin(Persona, Persona.id == ChatSession.persona_id)
        .add_columns(
            ChatSession.persona_id,
            Persona.name,
            func.count().filter(_POSITIVE),
            func.count().filter(_NEGATIVE),
            total,
        )
        .group_by(ChatSession.persona_id, Persona.name)
        .order_by(total.desc())
    ).all()
    return [
        AgentFeedback(
            persona_id=persona_id,
            name=name or _DEFAULT_AGENT_NAME,
            positive=int(positive),
            negative=int(negative),
            satisfaction_rate=satisfaction_rate(int(positive), int(negative)),
        )
        for persona_id, name, positive, negative, _ in rows
    ]


def fetch_feedback_by_model(
    db_session: Session, start: datetime, end: datetime
) -> list[ModelFeedback]:
    model = func.coalesce(ChatMessage.model_display_name, _UNKNOWN_MODEL).label("model")
    total = func.count().label("total")
    rows = db_session.execute(
        _feedback_base(start, end)
        .add_columns(
            model, func.count().filter(_POSITIVE), func.count().filter(_NEGATIVE), total
        )
        .group_by(model)
        .order_by(total.desc())
    ).all()
    return [
        ModelFeedback(
            model=name,
            positive=int(positive),
            negative=int(negative),
            satisfaction_rate=satisfaction_rate(int(positive), int(negative)),
        )
        for name, positive, negative, _ in rows
    ]


def fetch_negative_reasons(
    db_session: Session, start: datetime, end: datetime, limit: int = 10
) -> list[FeedbackReason]:
    count = func.count().label("count")
    rows = db_session.execute(
        _feedback_base(start, end)
        .add_columns(ChatMessageFeedback.predefined_feedback, count)
        .where(_NEGATIVE, ChatMessageFeedback.predefined_feedback.is_not(None))
        .group_by(ChatMessageFeedback.predefined_feedback)
        .order_by(count.desc())
        .limit(limit)
    ).all()
    return [FeedbackReason(reason=reason, count=int(n)) for reason, n in rows]


def fetch_recent_feedback(
    db_session: Session,
    start: datetime,
    end: datetime,
    identify: IdentityResolver,
    include_content: bool,
    limit: int = 50,
) -> list[RecentFeedback]:
    # Correlated lookup of the user message the rated answer replies to.
    parent_message = aliased(ChatMessage, name="parent_message")
    query_text = (
        select(parent_message.message)
        .where(parent_message.id == ChatMessage.parent_message_id)
        .correlate(ChatMessage)
        .scalar_subquery()
    )
    rows = db_session.execute(
        _feedback_base(start, end)
        .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
        .outerjoin(User, _USER_ID == ChatSession.user_id)
        .outerjoin(Persona, Persona.id == ChatSession.persona_id)
        .add_columns(
            ChatMessageFeedback.id,
            ChatMessageFeedback.is_positive,
            ChatMessageFeedback.feedback_text,
            ChatMessageFeedback.predefined_feedback,
            ChatMessage.chat_session_id,
            ChatMessage.id,
            ChatMessage.time_sent,
            ChatMessage.message,
            query_text,
            ChatSession.user_id,
            _USER_EMAIL,
            Persona.name,
        )
        .order_by(ChatMessage.time_sent.desc(), ChatMessageFeedback.id.desc())
        .limit(limit)
    ).all()
    result: list[RecentFeedback] = []
    for (
        feedback_id,
        is_positive,
        feedback_text,
        predefined_feedback,
        session_id,
        message_id,
        time_sent,
        answer,
        query,
        user_id,
        email,
        persona_name,
    ) in rows:
        shown_email, label = identify(user_id, email)
        result.append(
            RecentFeedback(
                feedback_id=feedback_id,
                chat_session_id=session_id,
                message_id=message_id,
                is_positive=is_positive,
                feedback_text=feedback_text,
                predefined_feedback=predefined_feedback,
                user_email=shown_email,
                user_label=label,
                persona_name=persona_name,
                time=time_sent,
                query=query if include_content else None,
                answer_preview=(
                    answer[:_PREVIEW_CHARS] if include_content and answer else None
                ),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Query history
# ---------------------------------------------------------------------------


def _feedback_counts_subquery() -> Select:
    return (
        select(
            ChatMessage.chat_session_id.label("session_id"),
            func.count().filter(_POSITIVE).label("positive"),
            func.count().filter(_NEGATIVE).label("negative"),
        )
        .select_from(ChatMessageFeedback)
        .join(ChatMessage, ChatMessage.id == ChatMessageFeedback.chat_message_id)
        .group_by(ChatMessage.chat_session_id)
    )


def _filtered_sessions(filters: ChatSessionFilters) -> Select:
    """Session rows with feedback counts, filtered. Columns:
    ChatSession, user email, persona name, positive count, negative count."""
    counts = _feedback_counts_subquery().subquery()
    positive = func.coalesce(counts.c.positive, 0)
    negative = func.coalesce(counts.c.negative, 0)
    stmt = (
        select(
            ChatSession,
            _USER_EMAIL,
            Persona.name,
            positive.label("positive"),
            negative.label("negative"),
        )
        .outerjoin(User, _USER_ID == ChatSession.user_id)
        .outerjoin(Persona, Persona.id == ChatSession.persona_id)
        .outerjoin(counts, counts.c.session_id == ChatSession.id)
        .where(
            _in_range(ChatSession.time_created, filters.start, filters.end),
            _recorded_session(),
        )
    )
    if filters.feedback == SessionFeedbackFilter.POSITIVE:
        stmt = stmt.where(positive > 0)
    elif filters.feedback == SessionFeedbackFilter.NEGATIVE:
        stmt = stmt.where(negative > 0)
    elif filters.feedback == SessionFeedbackFilter.MIXED:
        stmt = stmt.where(positive > 0, negative > 0)
    elif filters.feedback == SessionFeedbackFilter.NONE:
        stmt = stmt.where(positive == 0, negative == 0)
    if filters.user_email:
        stmt = stmt.where(_USER_EMAIL.icontains(filters.user_email, autoescape=True))
    if filters.persona_id is not None:
        stmt = stmt.where(ChatSession.persona_id == filters.persona_id)
    if filters.query:
        stmt = stmt.where(
            exists().where(
                ChatMessage.chat_session_id == ChatSession.id,
                ChatMessage.message_type.in_(_CONVERSATION_TYPES),
                ChatMessage.message.icontains(filters.query, autoescape=True),
            )
        )
    return stmt


def count_filtered_sessions(db_session: Session, filters: ChatSessionFilters) -> int:
    subquery = _filtered_sessions(filters).subquery()
    return int(db_session.scalar(select(func.count()).select_from(subquery)) or 0)


def fetch_session_summaries(
    db_session: Session,
    filters: ChatSessionFilters,
    identify: IdentityResolver,
    page: int,
    page_size: int,
) -> list[ChatSessionSummary]:
    first_message = (
        select(ChatMessage.message)
        .where(
            ChatMessage.chat_session_id == ChatSession.id,
            ChatMessage.message_type == MessageType.USER,
        )
        .order_by(ChatMessage.time_sent, ChatMessage.id)
        .limit(1)
        .correlate(ChatSession)
        .scalar_subquery()
    )
    message_count = (
        select(func.count())
        .where(
            ChatMessage.chat_session_id == ChatSession.id,
            ChatMessage.message_type.in_(_CONVERSATION_TYPES),
        )
        .correlate(ChatSession)
        .scalar_subquery()
    )
    rows = db_session.execute(
        _filtered_sessions(filters)
        .add_columns(first_message, message_count)
        .order_by(ChatSession.time_created.desc(), ChatSession.id)
        .offset(page * page_size)
        .limit(page_size)
    ).all()
    result: list[ChatSessionSummary] = []
    for chat, email, persona_name, positive, negative, first, count in rows:
        shown_email, label = identify(chat.user_id, email)
        result.append(
            ChatSessionSummary(
                id=chat.id,
                user_email=shown_email,
                user_label=label,
                persona_id=chat.persona_id,
                persona_name=persona_name,
                first_user_message=first,
                message_count=int(count or 0),
                time_created=chat.time_created,
                time_updated=chat.time_updated,
                feedback=session_feedback_status(int(positive), int(negative)),
                positive_count=int(positive),
                negative_count=int(negative),
                onyxbot_flow=chat.onyxbot_flow,
                deleted=chat.deleted,
            )
        )
    return result


def _to_detail(
    chat: ChatSession,
    email: str | None,
    persona_name: str | None,
    identify: IdentityResolver,
) -> ChatSessionDetail:
    shown_email, label = identify(chat.user_id, email)
    conversation = sorted(
        (m for m in chat.messages if m.message_type in _CONVERSATION_TYPES),
        key=lambda m: (m.time_sent, m.id),
    )
    return ChatSessionDetail(
        id=chat.id,
        user_email=shown_email,
        user_label=label,
        persona_name=persona_name,
        description=chat.description,
        time_created=chat.time_created,
        deleted=chat.deleted,
        messages=[
            InsightMessage(
                id=message.id,
                message_type=(
                    "user" if message.message_type == MessageType.USER else "assistant"
                ),
                message=message.message,
                time_sent=message.time_sent,
                model=message.model_display_name,
                error=message.error,
                feedback=[
                    MessageFeedbackSnapshot(
                        is_positive=feedback.is_positive,
                        feedback_text=feedback.feedback_text,
                        predefined_feedback=feedback.predefined_feedback,
                    )
                    for feedback in message.chat_message_feedbacks
                ],
            )
            for message in conversation
        ],
    )


def _with_messages(stmt: Select) -> Select:
    return stmt.options(
        selectinload(ChatSession.messages).selectinload(
            ChatMessage.chat_message_feedbacks
        )
    )


def fetch_session_detail(
    db_session: Session, session_id: UUID, identify: IdentityResolver
) -> ChatSessionDetail | None:
    row = db_session.execute(
        _with_messages(
            select(ChatSession, _USER_EMAIL, Persona.name)
            .outerjoin(User, _USER_ID == ChatSession.user_id)
            .outerjoin(Persona, Persona.id == ChatSession.persona_id)
            .where(ChatSession.id == session_id, _recorded_session())
        )
    ).one_or_none()
    if row is None:
        return None
    chat, email, persona_name = row
    return _to_detail(chat, email, persona_name, identify)


def fetch_sessions_for_export(
    db_session: Session,
    filters: ChatSessionFilters,
    identify: IdentityResolver,
    limit: int,
) -> list[ChatSessionDetail]:
    rows = db_session.execute(
        _with_messages(
            _filtered_sessions(filters)
            .order_by(ChatSession.time_created.desc(), ChatSession.id)
            .limit(limit)
        )
    ).all()
    return [
        _to_detail(chat, email, persona_name, identify)
        for chat, email, persona_name, _, _ in rows
    ]


def fetch_user_sessions_for_export(
    db_session: Session,
    user_id: UUID,
    identify: IdentityResolver,
    limit: int,
) -> list[ChatSessionDetail]:
    rows: Sequence = db_session.execute(
        _with_messages(
            select(ChatSession, _USER_EMAIL, Persona.name)
            .outerjoin(User, _USER_ID == ChatSession.user_id)
            .outerjoin(Persona, Persona.id == ChatSession.persona_id)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.deleted.is_(False),
                _recorded_session(),
            )
            .order_by(ChatSession.time_created.desc())
            .limit(limit)
        )
    ).all()
    return [
        _to_detail(chat, email, persona_name, identify)
        for chat, email, persona_name in rows
    ]
