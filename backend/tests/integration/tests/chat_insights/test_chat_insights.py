"""Chat Insights (MIT): usage dashboard, chat ratings, query history and chat
export, including the per-user export and admin-only access."""

import csv
import io
from datetime import datetime, timezone

import pytest

from tests.integration.common_utils.constants import API_SERVER_URL
from tests.integration.common_utils.http_client import client
from tests.integration.common_utils.managers.chat import ChatSessionManager
from tests.integration.common_utils.test_models import (
    DATestLLMProvider,
    DATestUser,
)

INSIGHTS_URL = f"{API_SERVER_URL}/admin/chat-insights"


def _chat_with_rating(
    user: DATestUser,
    question: str,
    answer: str,
    is_positive: bool | None,
    reason: str | None = None,
) -> str:
    session = ChatSessionManager.create(user_performing_action=user)
    response = ChatSessionManager.send_message(
        chat_session_id=session.id,
        message=question,
        user_performing_action=user,
        mock_llm_response=answer,
    )
    assert response.error is None
    if is_positive is not None:
        ChatSessionManager.create_chat_message_feedback(
            message_id=response.assistant_message_id,
            is_positive=is_positive,
            user_performing_action=user,
            feedback_text="stare dane" if not is_positive else None,
            predefined_feedback=reason,
        )
    return str(session.id)


@pytest.fixture
def rated_chats(
    reset: None,  # noqa: ARG001
    admin_user: DATestUser,
    basic_user: DATestUser,
    llm_provider: DATestLLMProvider,  # noqa: ARG001
) -> dict[str, str]:
    return {
        "liked": _chat_with_rating(
            basic_user, "Ile dni urlopu?", "26 dni.", is_positive=True
        ),
        "disliked": _chat_with_rating(
            basic_user,
            "Limit zakupów IT?",
            "5 000 zł.",
            is_positive=False,
            reason="Outdated information",
        ),
        "unrated": _chat_with_rating(
            admin_user, "Godziny pracy biura?", "8:00-18:00.", is_positive=None
        ),
    }


def test_usage_dashboard_counts_messages_and_users(
    rated_chats: dict[str, str], admin_user: DATestUser
) -> None:
    response = client.get(f"{INSIGHTS_URL}/usage", headers=admin_user.headers)
    response.raise_for_status()
    body = response.json()

    assert body["totals"]["sessions"] == len(rated_chats)
    assert body["totals"]["user_messages"] == 3
    assert body["totals"]["assistant_messages"] == 3
    assert body["totals"]["active_users"] == 2
    today = datetime.now(timezone.utc).date().isoformat()
    assert body["end"] == today
    assert len(body["daily"]) == 30
    assert body["daily"][-1]["user_messages"] == 3
    assert {user["user_messages"] for user in body["top_users"]} == {1, 2}


def test_feedback_analytics(
    rated_chats: dict[str, str], admin_user: DATestUser
) -> None:
    response = client.get(f"{INSIGHTS_URL}/feedback", headers=admin_user.headers)
    response.raise_for_status()
    body = response.json()

    assert body["totals"]["positive"] == 1
    assert body["totals"]["negative"] == 1
    assert body["totals"]["satisfaction_rate"] == pytest.approx(0.5)
    assert body["totals"]["rating_coverage"] == pytest.approx(2 / 3)
    assert body["predefined_reasons"] == [
        {"reason": "Outdated information", "count": 1}
    ]
    [negative] = [item for item in body["recent"] if item["is_positive"] is False]
    assert negative["chat_session_id"] == rated_chats["disliked"]
    assert negative["query"] == "Limit zakupów IT?"
    assert negative["feedback_text"] == "stare dane"


def test_query_history_filters_and_detail(
    rated_chats: dict[str, str], admin_user: DATestUser, basic_user: DATestUser
) -> None:
    def session_ids(**params: str) -> set[str]:
        response = client.get(
            f"{INSIGHTS_URL}/sessions", params=params, headers=admin_user.headers
        )
        response.raise_for_status()
        return {item["id"] for item in response.json()["items"]}

    assert session_ids() == set(rated_chats.values())
    assert session_ids(feedback="positive") == {rated_chats["liked"]}
    assert session_ids(feedback="negative") == {rated_chats["disliked"]}
    assert session_ids(feedback="none") == {rated_chats["unrated"]}
    assert session_ids(q="urlopu") == {rated_chats["liked"]}
    assert session_ids(user_email=basic_user.email) == {
        rated_chats["liked"],
        rated_chats["disliked"],
    }

    detail = client.get(
        f"{INSIGHTS_URL}/sessions/{rated_chats['disliked']}",
        headers=admin_user.headers,
    )
    detail.raise_for_status()
    messages = detail.json()["messages"]
    assert [m["message_type"] for m in messages] == ["user", "assistant"]
    assert messages[1]["feedback"][0]["is_positive"] is False


def test_chat_export_csv_and_json(
    rated_chats: dict[str, str], admin_user: DATestUser
) -> None:
    csv_response = client.get(
        f"{INSIGHTS_URL}/export",
        params={"format": "csv", "feedback": "negative"},
        headers=admin_user.headers,
    )
    csv_response.raise_for_status()
    assert "attachment" in csv_response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(csv_response.text.lstrip("﻿"))))
    assert {row["session_id"] for row in rows} == {rated_chats["disliked"]}
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert rows[1]["feedback"] == "negative"

    json_response = client.get(
        f"{INSIGHTS_URL}/sessions/{rated_chats['liked']}/export",
        params={"format": "json"},
        headers=admin_user.headers,
    )
    json_response.raise_for_status()
    [session] = json_response.json()
    assert session["id"] == rated_chats["liked"]


def test_user_exports_only_own_chats(
    rated_chats: dict[str, str], basic_user: DATestUser
) -> None:
    response = client.get(
        f"{API_SERVER_URL}/user/chat-export",
        params={"format": "json"},
        headers=basic_user.headers,
    )
    response.raise_for_status()
    assert {session["id"] for session in response.json()} == {
        rated_chats["liked"],
        rated_chats["disliked"],
    }


def test_basic_user_cannot_read_insights(
    rated_chats: dict[str, str],  # noqa: ARG001
    basic_user: DATestUser,
) -> None:
    for path in ("usage", "feedback", "sessions", "export"):
        response = client.get(f"{INSIGHTS_URL}/{path}", headers=basic_user.headers)
        assert response.status_code == 403, path
