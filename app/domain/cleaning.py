"""Execution of a cleaning session on a map."""

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from itertools import repeat
from uuid import uuid4

from app.domain.models import CleaningMap, Coordinate, Direction, RobotModel
from app.domain.session import Action, SessionError, SessionReport, SessionState


class InvalidStartError(ValueError):
    """The requested start coordinate is not a walkable tile of the current map."""


def run_session(
    cleaning_map: CleaningMap,
    robot_model: RobotModel,
    start: Coordinate,
    actions: Sequence[Action],
) -> SessionReport:
    """Run one cleaning session, stopping at the first collision.

    The starting tile is visited before the first action and does not count as a step.
    """
    if not cleaning_map.is_walkable(start):
        raise InvalidStartError("The start coordinate must be a walkable tile of the current map.")

    started_at = datetime.now(UTC)
    position = start
    cleaned_tiles: list[Coordinate] = []
    successful_steps = 0
    error: SessionError | None = None

    _visit(cleaning_map, robot_model, position, cleaned_tiles)
    for direction in _single_steps(actions):
        target = _neighbour(position, direction)
        # A wall and a coordinate outside the map are both non-walkable, and the contract
        # treats them as the same collision.
        if not cleaning_map.is_walkable(target):
            error = SessionError(message=_collision_message(cleaning_map, target), position=target)
            break
        position = target
        successful_steps += 1
        _visit(cleaning_map, robot_model, position, cleaned_tiles)

    finished_at = datetime.now(UTC)
    return SessionReport(
        id=str(uuid4()),
        started_at=started_at,
        finished_at=finished_at,
        state=SessionState.ERROR if error else SessionState.COMPLETED,
        robot_model=robot_model,
        submitted_actions=len(actions),
        successful_steps=successful_steps,
        cleaned_tiles=cleaned_tiles,
        final_position=position,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        error=error,
    )


def _single_steps(actions: Sequence[Action]) -> Iterator[Direction]:
    """Flatten the actions into the single steps they are executed as."""
    for action in actions:
        yield from repeat(action.direction, action.steps)


def _collision_message(cleaning_map: CleaningMap, target: Coordinate) -> str:
    if cleaning_map.contains(target):
        return "The robot cannot enter a non-walkable tile."
    return "The robot cannot leave the map."


def _neighbour(position: Coordinate, direction: Direction) -> Coordinate:
    delta_x, delta_y = direction.delta
    return Coordinate(x=position.x + delta_x, y=position.y + delta_y)


def _visit(
    cleaning_map: CleaningMap,
    robot_model: RobotModel,
    position: Coordinate,
    cleaned_tiles: list[Coordinate],
) -> None:
    """Let the robot process the tile it stands on, recording any cleaning operation."""
    # Performing the operation and reporting it happen together, so the two cannot diverge.
    if robot_model.cleans(dirty=cleaning_map.is_dirty(position)):
        cleaning_map.mark_clean(position)
        cleaned_tiles.append(position)
