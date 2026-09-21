"""The report produced by a cleaning session."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_serializer

from app.domain.models import Coordinate, Direction, RobotModel


class Action(BaseModel):
    """A number of single steps in one direction."""

    direction: Direction
    steps: Annotated[StrictInt, Field(gt=0)]


class SessionState(StrEnum):
    """How a session ended: all actions finished, or a collision stopped it."""

    COMPLETED = "completed"
    ERROR = "error"


class SessionError(BaseModel):
    """Why a session stopped early, and the coordinate the robot could not enter."""

    code: Literal["collision"] = "collision"
    message: str
    position: Coordinate


class SessionReport(BaseModel):
    """The outcome of a single cleaning session, as returned by the API."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    id: str
    started_at: datetime
    finished_at: datetime
    state: SessionState
    robot_model: RobotModel
    submitted_actions: int
    "How many actions were submitted for the session."
    successful_steps: int
    "Movements that succeeded; processing the starting tile is not a step."
    cleaned_tiles: list[Coordinate]
    "Tiles cleaned, in cleaning order; a basic robot may report the same tile twice."
    final_position: Coordinate
    "Where the robot stopped, which after a collision is the last valid coordinate."
    duration_ms: int
    error: SessionError | None = None
    "Absent for a completed session, and the collision details for one in state 'error'."

    @field_serializer("started_at", "finished_at")
    def _serialize_timestamp(self, moment: datetime) -> str:
        return format_rfc3339(moment)


def format_rfc3339(moment: datetime) -> str:
    """Format an instant as an RFC 3339 UTC timestamp, e.g. 2026-07-11T09:30:00.012Z."""
    moment = moment.astimezone(UTC)
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"
