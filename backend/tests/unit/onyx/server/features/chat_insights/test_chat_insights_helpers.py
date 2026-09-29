import csv
import io
import json
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from onyx.configs.constants import QueryHistoryType
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.chat_insights.api import (
    MAX_RANGE_DAYS,
    identity_resolver,
    pseudonym,
    resolve_date_range,
)
from onyx.server.features.chat_insights.export import (
    CSV_COLUMNS,
    ExportFormat,
    build_export_response,
    sessions_to_csv,
    sessions_to_json,
)
from onyx.server.features.chat_insights.models import (
    ChatSessionDetail,
    InsightMessage,
    MessageFeedbackSnapshot,
    SessionFeedbackStatus,
    satisfaction_rate,
    session_feedback_status,
)

_T0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)


def _session() -> ChatSessionDetail:
    return ChatSessionDetail(
        id=uuid4(),
        user_email="jan.kowalski@example.com",
        user_label="jan.kowalski@example.com",
        persona_name="Asystent",
        description="Urlop",
        time_created=_T0,
        deleted=False,
        messages=[
            InsightMessage(
                id=2,
                message_type="user",
                message="Ile dni urlopu mi przysługuje?",
                time_sent=_T0,
                model=None,
                error=None,
                feedback=[],
            ),
            InsightMessage(
                id=3,
                message_type="assistant",
                message='Przysługuje 26 dni, "zgodnie" z KP,\nart. 154.',
                time_sent=_T0,
                model="gpt-5-mini",
                error=None,
                feedback=[
                    MessageFeedbackSnapshot(
                        is_positive=False,
                        feedback_text="stare dane",
                        predefined_feedback="Outdated",
                    ),
                    MessageFeedbackSnapshot(
                        is_positive=True, feedback_text=None, predefined_feedback=None
                    ),
                ],
            ),
        ],
    )


def test_resolve_date_range_defaults_to_last_30_days() -> None:
    start, end, start_dt, end_dt = resolve_date_range(
        None, None, today=date(2026, 9, 30)
    )
    assert (start, end) == (date(2026, 9, 1), date(2026, 9, 30))
    assert start_dt == datetime(2026, 9, 1, tzinfo=timezone.utc)
    # End date is inclusive, so the bound is the next midnight.
    assert end_dt == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_resolve_date_range_rejects_bad_ranges() -> None:
    with pytest.raises(OnyxError):
        resolve_date_range(date(2026, 9, 2), date(2026, 9, 1))
    with pytest.raises(OnyxError):
        resolve_date_range(date(2025, 1, 1), date(2026, 1, 2))
    # A full year is still allowed.
    start, end, _, _ = resolve_date_range(date(2025, 1, 1), date(2025, 12, 31))
    assert (end - start).days < MAX_RANGE_DAYS


def test_identity_resolver_modes() -> None:
    user_id = uuid4()
    normal = identity_resolver(QueryHistoryType.NORMAL)
    assert normal(user_id, "a@example.com") == ("a@example.com", "a@example.com")
    assert normal(None, None) == (None, "anonymous")

    anonymized = identity_resolver(QueryHistoryType.ANONYMIZED)
    email, label = anonymized(user_id, "a@example.com")
    assert email is None
    assert label == pseudonym(user_id)
    assert label.startswith("user-") and len(label) == len("user-") + 8
    # Stable across calls so admins can follow one user.
    assert anonymized(user_id, "a@example.com")[1] == label


def test_feedback_status_and_rate() -> None:
    assert session_feedback_status(1, 1) is SessionFeedbackStatus.MIXED
    assert session_feedback_status(2, 0) is SessionFeedbackStatus.POSITIVE
    assert session_feedback_status(0, 3) is SessionFeedbackStatus.NEGATIVE
    assert session_feedback_status(0, 0) is SessionFeedbackStatus.NONE
    assert satisfaction_rate(3, 1) == 0.75
    assert satisfaction_rate(0, 0) is None


def test_sessions_to_csv_one_row_per_message_with_latest_feedback() -> None:
    session = _session()
    rows = list(csv.reader(io.StringIO(sessions_to_csv([session]))))
    assert rows[0] == CSV_COLUMNS
    assert len(rows) == 3
    user_row = dict(zip(CSV_COLUMNS, rows[1], strict=True))
    assistant_row = dict(zip(CSV_COLUMNS, rows[2], strict=True))
    assert user_row["role"] == "user"
    assert user_row["feedback"] == ""
    assert assistant_row["message"] == 'Przysługuje 26 dni, "zgodnie" z KP,\nart. 154.'
    assert assistant_row["model"] == "gpt-5-mini"
    assert assistant_row["feedback"] == "positive"
    assert assistant_row["user"] == "jan.kowalski@example.com"
    assert assistant_row["session_id"] == str(session.id)


def test_sessions_to_json_round_trips() -> None:
    session = _session()
    parsed = json.loads(sessions_to_json([session]))
    assert parsed[0]["id"] == str(session.id)
    assert parsed[0]["messages"][1]["feedback"][0]["predefined_feedback"] == "Outdated"
    # Non-ASCII stays readable.
    assert "przysługuje" in sessions_to_json([session]).lower()


def test_build_export_response_headers() -> None:
    csv_response = build_export_response([_session()], ExportFormat.CSV, "onyx-chats")
    assert csv_response.media_type == "text/csv; charset=utf-8"
    disposition = csv_response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="onyx-chats-')
    assert disposition.endswith('.csv"')
    assert bytes(csv_response.body).startswith("﻿".encode())

    json_response = build_export_response([], ExportFormat.JSON, "x")
    assert json.loads(bytes(json_response.body)) == []
