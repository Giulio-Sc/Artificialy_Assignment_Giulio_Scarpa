"""Request and response bodies of the HTTP API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import Coordinate, RobotModel
from app.domain.session import Action


class HealthResponse(BaseModel):
    """The fixed body of the health check."""

    status: Literal["ok"] = "ok"


class MapSummary(BaseModel):
    """The shape of the map that has just been loaded."""

    rows: int
    cols: int
    walkable_tiles: int


class CleanRequest(BaseModel):
    """A cleaning session: where the robot starts, which model it is, and how it moves."""

    # Pre-prepared example shown in the /docs "try it out". It succeeds on examples/map.txt,
    # the map the README walkthrough loads: a body generated from the types alone would send
    # steps=0 and be rejected.
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"start": {"x": 0, "y": 0}, "robot_model": "basic",
                "actions": [{"direction": "south", "steps": 2}]}
            ]
        }
    )

    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
