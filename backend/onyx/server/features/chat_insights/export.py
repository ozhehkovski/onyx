"""Serializes chat sessions into downloadable JSON or CSV files."""

import csv
import io
import json
from datetime import datetime, timezone

from fastapi.responses import Response

from onyx.server.features.chat_insights.models import ChatSessionDetail, ExportFormat

CSV_COLUMNS = [
    "session_id",
    "session_created",
    "user",
    "agent",
    "message_id",
    "role",
    "time_sent",
    "model",
    "message",
    "feedback",
    "feedback_text",
    "predefined_feedback",
]

_MEDIA_TYPES = {
    ExportFormat.JSON: "application/json",
    ExportFormat.CSV: "text/csv; charset=utf-8",
}


def _feedback_label(is_positive: bool | None) -> str:
    if is_positive is True:
        return "positive"
    if is_positive is False:
        return "negative"
    return ""


def sessions_to_csv(sessions: list[ChatSessionDetail]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for session in sessions:
        for message in session.messages:
            latest = message.feedback[-1] if message.feedback else None
            writer.writerow(
                [
                    str(session.id),
                    session.time_created.isoformat(),
                    session.user_email or session.user_label,
                    session.persona_name or "",
                    message.id,
                    message.message_type,
                    message.time_sent.isoformat(),
                    message.model or "",
                    message.message,
                    _feedback_label(latest.is_positive) if latest else "",
                    (latest.feedback_text or "") if latest else "",
                    (latest.predefined_feedback or "") if latest else "",
                ]
            )
    return buffer.getvalue()


def sessions_to_json(sessions: list[ChatSessionDetail]) -> str:
    return json.dumps(
        [session.model_dump(mode="json") for session in sessions],
        ensure_ascii=False,
        indent=2,
    )


def export_filename(prefix: str, export_format: ExportFormat) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}.{export_format.value}"


def build_export_response(
    sessions: list[ChatSessionDetail], export_format: ExportFormat, prefix: str
) -> Response:
    if export_format == ExportFormat.CSV:
        # BOM so spreadsheet apps detect UTF-8 (Polish characters, etc.).
        body = "﻿" + sessions_to_csv(sessions)
    else:
        body = sessions_to_json(sessions)
    filename = export_filename(prefix, export_format)
    return Response(
        content=body.encode("utf-8"),
        media_type=_MEDIA_TYPES[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
