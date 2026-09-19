"""Request and response bodies of the HTTP API."""

from typing import Literal

from pydantic import BaseModel

from app.domain.models import Coordinate, RobotModel
from app.domain.session import Action


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class MapSummary(BaseModel):
    rows: int
    cols: int
    walkable_tiles: int


class CleanRequest(BaseModel):
    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
