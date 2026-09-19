"""Rendering of the cleaning-session history as RFC 4180 CSV."""

import csv
from collections.abc import Iterable
from io import StringIO

from app.domain.session import SessionReport, format_rfc3339

HEADER = (
    "id",
    "started_at",
    "state",
    "robot_model",
    "submitted_actions",
    "successful_steps",
    "cleaned_tiles",
    "duration_ms",
)


def render_history_csv(sessions: Iterable[SessionReport]) -> str:
    """Render one row per session, oldest first, preceded by the header row."""
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for session in sessions:
        writer.writerow(
            (
                session.id,
                format_rfc3339(session.started_at),
                session.state.value,
                session.robot_model.value,
                session.submitted_actions,
                session.successful_steps,
                len(session.cleaned_tiles),
                session.duration_ms,
            )
        )
    return buffer.getvalue()
