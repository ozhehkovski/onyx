"""Admin Chat Insights: usage dashboard, chat ratings analytics, query history
and chat export. Also the per-user export of one's own chats."""

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.configs.app_configs import ONYX_QUERY_HISTORY_TYPE
from onyx.configs.constants import QueryHistoryType
from onyx.db.chat_insights import (
    ChatSessionFilters,
    IdentityResolver,
    count_filtered_sessions,
    fetch_daily_feedback,
    fetch_daily_usage,
    fetch_feedback_by_agent,
    fetch_feedback_by_model,
    fetch_feedback_totals,
    fetch_model_usage,
    fetch_negative_reasons,
    fetch_recent_feedback,
    fetch_session_detail,
    fetch_session_summaries,
    fetch_sessions_for_export,
    fetch_top_agents,
    fetch_top_users,
    fetch_usage_totals,
    fetch_user_sessions_for_export,
)
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.chat_insights.export import build_export_response
from onyx.server.features.chat_insights.models import (
    ChatSessionDetail,
    ChatSessionPage,
    ExportFormat,
    FeedbackAnalyticsResponse,
    SessionFeedbackFilter,
    UsageResponse,
)

admin_router = APIRouter(prefix="/admin/chat-insights")
user_router = APIRouter(prefix="/user/chat-export")

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
MAX_EXPORT_SESSIONS = 10_000
ANONYMOUS_LABEL = "anonymous"


def resolve_date_range(
    start: date | None, end: date | None, today: date | None = None
) -> tuple[date, date, datetime, datetime]:
    """Inclusive [start, end] dates → half-open UTC datetime bounds."""
    end_date = end or today or datetime.now(timezone.utc).date()
    start_date = start or end_date - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start_date > end_date:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "start must not be after end")
    if (end_date - start_date).days >= MAX_RANGE_DAYS:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"date range must not exceed {MAX_RANGE_DAYS} days",
        )
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    return start_date, end_date, start_dt, end_dt


def pseudonym(user_id: UUID | None) -> str:
    if user_id is None:
        return ANONYMOUS_LABEL
    digest = hashlib.sha256(str(user_id).encode()).hexdigest()[:8]
    return f"user-{digest}"


def identity_resolver(history_type: QueryHistoryType) -> IdentityResolver:
    def identify(user_id: UUID | None, email: str | None) -> tuple[str | None, str]:
        if history_type == QueryHistoryType.NORMAL and email:
            return email, email
        return None, pseudonym(user_id)

    return identify


def _require_history_enabled() -> None:
    if ONYX_QUERY_HISTORY_TYPE == QueryHistoryType.DISABLED:
        raise OnyxError(
            OnyxErrorCode.ENV_VAR_GATED,
            "Query history is disabled (ONYX_QUERY_HISTORY_TYPE=disabled)",
        )


def _session_filters(
    start: date | None,
    end: date | None,
    feedback: SessionFeedbackFilter,
    user_email: str | None,
    persona_id: int | None,
    q: str | None,
) -> ChatSessionFilters:
    _, _, start_dt, end_dt = resolve_date_range(start, end)
    return ChatSessionFilters(
        start=start_dt,
        end=end_dt,
        feedback=feedback,
        # Email filtering would de-anonymize pseudonymized users.
        user_email=(
            user_email.strip() or None
            if user_email and ONYX_QUERY_HISTORY_TYPE == QueryHistoryType.NORMAL
            else None
        ),
        persona_id=persona_id,
        query=q.strip() or None if q else None,
    )


@admin_router.get("/usage")
def get_usage_dashboard(
    start: date | None = None,
    end: date | None = None,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UsageResponse:
    start_date, end_date, start_dt, end_dt = resolve_date_range(start, end)
    identify = identity_resolver(ONYX_QUERY_HISTORY_TYPE)
    return UsageResponse(
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        totals=fetch_usage_totals(db_session, start_dt, end_dt),
        daily=fetch_daily_usage(db_session, start_dt, end_dt),
        top_users=fetch_top_users(db_session, start_dt, end_dt, identify),
        top_agents=fetch_top_agents(db_session, start_dt, end_dt),
        models=fetch_model_usage(db_session, start_dt, end_dt),
    )


@admin_router.get("/feedback")
def get_feedback_analytics(
    start: date | None = None,
    end: date | None = None,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> FeedbackAnalyticsResponse:
    start_date, end_date, start_dt, end_dt = resolve_date_range(start, end)
    return FeedbackAnalyticsResponse(
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        totals=fetch_feedback_totals(db_session, start_dt, end_dt),
        daily=fetch_daily_feedback(db_session, start_dt, end_dt),
        by_agent=fetch_feedback_by_agent(db_session, start_dt, end_dt),
        by_model=fetch_feedback_by_model(db_session, start_dt, end_dt),
        predefined_reasons=fetch_negative_reasons(db_session, start_dt, end_dt),
        recent=fetch_recent_feedback(
            db_session,
            start_dt,
            end_dt,
            identify=identity_resolver(ONYX_QUERY_HISTORY_TYPE),
            include_content=ONYX_QUERY_HISTORY_TYPE != QueryHistoryType.DISABLED,
        ),
    )


@admin_router.get("/sessions")
def list_chat_sessions(
    start: date | None = None,
    end: date | None = None,
    feedback: SessionFeedbackFilter = SessionFeedbackFilter.ALL,
    user_email: str | None = None,
    persona_id: int | None = None,
    q: str | None = None,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(require_permission(Permission.READ_QUERY_HISTORY)),
    db_session: Session = Depends(get_session),
) -> ChatSessionPage:
    _require_history_enabled()
    filters = _session_filters(start, end, feedback, user_email, persona_id, q)
    return ChatSessionPage(
        total=count_filtered_sessions(db_session, filters),
        page=page,
        page_size=page_size,
        items=fetch_session_summaries(
            db_session,
            filters,
            identity_resolver(ONYX_QUERY_HISTORY_TYPE),
            page=page,
            page_size=page_size,
        ),
    )


def _get_session_or_404(db_session: Session, session_id: UUID) -> ChatSessionDetail:
    detail = fetch_session_detail(
        db_session, session_id, identity_resolver(ONYX_QUERY_HISTORY_TYPE)
    )
    if detail is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Chat session not found")
    return detail


@admin_router.get("/sessions/{session_id}")
def get_chat_session(
    session_id: UUID,
    _: User = Depends(require_permission(Permission.READ_QUERY_HISTORY)),
    db_session: Session = Depends(get_session),
) -> ChatSessionDetail:
    _require_history_enabled()
    return _get_session_or_404(db_session, session_id)


@admin_router.get("/sessions/{session_id}/export")
def export_chat_session(
    session_id: UUID,
    format: ExportFormat = ExportFormat.JSON,
    _: User = Depends(require_permission(Permission.READ_QUERY_HISTORY)),
    db_session: Session = Depends(get_session),
) -> Response:
    _require_history_enabled()
    detail = _get_session_or_404(db_session, session_id)
    return build_export_response([detail], format, prefix=f"onyx-chat-{session_id}")


@admin_router.get("/export")
def export_chat_sessions(
    format: ExportFormat = ExportFormat.JSON,
    start: date | None = None,
    end: date | None = None,
    feedback: SessionFeedbackFilter = SessionFeedbackFilter.ALL,
    user_email: str | None = None,
    persona_id: int | None = None,
    q: str | None = None,
    _: User = Depends(require_permission(Permission.READ_QUERY_HISTORY)),
    db_session: Session = Depends(get_session),
) -> Response:
    _require_history_enabled()
    filters = _session_filters(start, end, feedback, user_email, persona_id, q)
    sessions = fetch_sessions_for_export(
        db_session,
        filters,
        identity_resolver(ONYX_QUERY_HISTORY_TYPE),
        limit=MAX_EXPORT_SESSIONS,
    )
    return build_export_response(sessions, format, prefix="onyx-chats")


@user_router.get("")
def export_my_chats(
    format: ExportFormat = ExportFormat.JSON,
    user: User = Depends(require_permission(Permission.READ_CHAT)),
    db_session: Session = Depends(get_session),
) -> Response:
    sessions = fetch_user_sessions_for_export(
        db_session,
        user.id,
        identity_resolver(QueryHistoryType.NORMAL),
        limit=MAX_EXPORT_SESSIONS,
    )
    return build_export_response(sessions, format, prefix="my-onyx-chats")
