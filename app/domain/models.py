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
    """The four directions a robot can step in."""

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
        # The behavioural difference between the two models.
        return self is RobotModel.BASIC or dirty


@dataclass
class Tile:
    """One grid square: whether it can be walked on, and whether it still needs cleaning."""

    walkable: bool
    dirty: bool


class CleaningMap:
    """A rectangular grid of tiles that owns tile cleanliness for the map's lifetime."""

    def __init__(self, tiles: list[list[Tile]]) -> None:
        # The parsers already reject a grid that is empty or ragged, but the invariant
        # belongs to the type that every other method relies on it: `cols` reads row zero.
        if not tiles or not tiles[0] or any(len(row) != len(tiles[0]) for row in tiles):
            raise ValueError("A map must be a rectangle of at least one row and one column.")
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
        # Cleaning is one-way: only loading a map makes tiles dirty again, so this state
        # survives every later cleaning session on the same map.
        # Reached through _tile_at rather than by indexing: a negative coordinate would
        # otherwise wrap around and silently clean a tile at the far end of the row.
        tile = self._tile_at(position)
        if tile is None:
            raise ValueError(f"Cannot clean {position}, which is outside the map.")
        tile.dirty = False

    def _tile_at(self, position: Coordinate) -> Tile | None:
        return self._tiles[position.y][position.x] if self.contains(position) else None
