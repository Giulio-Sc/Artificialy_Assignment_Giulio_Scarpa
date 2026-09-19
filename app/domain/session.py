"""The report produced by a cleaning session."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictInt, field_serializer

from app.domain.models import Coordinate, Direction, RobotModel


class Action(BaseModel):
    """A number of single steps in one direction."""

    direction: Direction
    steps: Annotated[StrictInt, Field(gt=0)]


class SessionState(StrEnum):
    COMPLETED = "completed"
    ERROR = "error"


class SessionError(BaseModel):
    code: Literal["collision"] = "collision"
    message: str
    position: Coordinate


class SessionReport(BaseModel):
    """The outcome of a single cleaning session, as returned by the API."""

    id: str
    started_at: datetime
    finished_at: datetime
    state: SessionState
    robot_model: RobotModel
    submitted_actions: int
    successful_steps: int
    cleaned_tiles: list[Coordinate]
    final_position: Coordinate
    duration_ms: int
    error: SessionError | None = None

    @field_serializer("started_at", "finished_at")
    def _serialize_timestamp(self, moment: datetime) -> str:
        return format_rfc3339(moment)


def format_rfc3339(moment: datetime) -> str:
    """Format an instant as an RFC 3339 UTC timestamp, e.g. 2026-07-11T09:30:00.012Z."""
    moment = moment.astimezone(UTC)
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"
