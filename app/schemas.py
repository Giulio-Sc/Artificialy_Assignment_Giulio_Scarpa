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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "start": {"x": 0, "y": 0},
                    "robot_model": "basic",
                    "actions": [
                        {"direction": "east", "steps": 2},
                        {"direction": "south", "steps": 1},
                    ],
                }
            ]
        }
    )

    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
