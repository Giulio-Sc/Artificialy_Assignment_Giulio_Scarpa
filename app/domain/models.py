"""Core domain values: coordinates, directions, robot models and the map itself."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictInt


class Coordinate(BaseModel):
    """A zero-based position on the map: (0, 0) is the top-left tile."""

    model_config = ConfigDict(frozen=True)

    x: StrictInt
    y: StrictInt


class Direction(StrEnum):
    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"

    @property
    def delta(self) -> tuple[int, int]:
        """The (x, y) offset of a single step in this direction."""
        return _DELTAS[self]


_DELTAS = {
    Direction.NORTH: (0, -1),
    Direction.EAST: (1, 0),
    Direction.SOUTH: (0, 1),
    Direction.WEST: (-1, 0),
}


class RobotModel(StrEnum):
    """The supported robot models, which differ only in when they clean a tile."""

    BASIC = "basic"
    PREMIUM = "premium"

    def cleans(self, *, dirty: bool) -> bool:
        """A basic robot cleans every tile it visits, a premium one only dirty tiles."""
        return self is RobotModel.BASIC or dirty


@dataclass
class Tile:
    walkable: bool
    dirty: bool


class CleaningMap:
    """A rectangular grid of tiles that owns tile cleanliness for the map's lifetime."""

    def __init__(self, tiles: list[list[Tile]]) -> None:
        self._tiles = tiles

    @property
    def rows(self) -> int:
        return len(self._tiles)

    @property
    def cols(self) -> int:
        return len(self._tiles[0])

    @property
    def walkable_tiles(self) -> int:
        return sum(tile.walkable for row in self._tiles for tile in row)

    def contains(self, position: Coordinate) -> bool:
        return 0 <= position.x < self.cols and 0 <= position.y < self.rows

    def is_walkable(self, position: Coordinate) -> bool:
        """Whether the position is inside the map and walkable."""
        tile = self._tile_at(position)
        return tile is not None and tile.walkable

    def is_dirty(self, position: Coordinate) -> bool:
        tile = self._tile_at(position)
        return tile is not None and tile.dirty

    def mark_clean(self, position: Coordinate) -> None:
        self._tiles[position.y][position.x].dirty = False

    def _tile_at(self, position: Coordinate) -> Tile | None:
        return self._tiles[position.y][position.x] if self.contains(position) else None
