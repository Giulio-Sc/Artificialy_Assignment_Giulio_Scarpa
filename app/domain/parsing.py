"""Parsing of the two supported map file formats."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError

from app.domain.models import CleaningMap, Tile


class InvalidMapError(ValueError):
    """The uploaded file contents do not describe a valid map."""


def parse_txt_map(content: bytes) -> CleaningMap:
    """Parse a TXT map, where 'o' is a walkable dirty tile and 'x' a non-walkable one."""
    text = _decode(content).replace("\r\n", "\n")
    if text.endswith("\n"):  # a single line ending after the last row is accepted
        text = text[:-1]

    rows = text.split("\n")
    if not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise InvalidMapError("Every row must be non-empty and have the same number of columns.")
    return CleaningMap([[_txt_tile(character) for character in row] for row in rows])


def parse_json_map(content: bytes) -> CleaningMap:
    """Parse a JSON map, which lists exactly one tile per coordinate of the rectangle."""
    try:
        document = _JsonMap.model_validate_json(content)
    except ValidationError as error:
        raise InvalidMapError(f"The file is not a valid JSON map: {error}.") from error

    tiles: dict[tuple[int, int], Tile] = {}
    for tile in document.tiles:
        position = (tile.x, tile.y)
        if not (0 <= tile.x < document.cols and 0 <= tile.y < document.rows):
            raise InvalidMapError(f"Tile {position} lies outside the declared bounds.")
        if position in tiles:
            raise InvalidMapError(f"Tile {position} appears more than once.")
        if not tile.walkable and tile.dirty:
            raise InvalidMapError(f"Non-walkable tile {position} cannot be dirty.")
        # A walkable tile whose dirty field is omitted starts dirty.
        dirty = tile.walkable if tile.dirty is None else tile.dirty
        tiles[position] = Tile(walkable=tile.walkable, dirty=dirty)

    if len(tiles) != document.rows * document.cols:
        raise InvalidMapError("Every coordinate of the rectangle must appear exactly once.")
    return CleaningMap(
        [[tiles[(x, y)] for x in range(document.cols)] for y in range(document.rows)]
    )


# The map format is fully specified, so an unknown key is an authoring mistake rather than a
# newer version of the format: rejecting it turns a silently misread map into a clear error.
_STRICT = ConfigDict(extra="forbid")


class _JsonTile(BaseModel):
    model_config = _STRICT

    x: StrictInt
    y: StrictInt
    walkable: StrictBool
    dirty: StrictBool | None = None


class _JsonMap(BaseModel):
    model_config = _STRICT

    rows: Annotated[StrictInt, Field(gt=0)]
    cols: Annotated[StrictInt, Field(gt=0)]
    tiles: list[_JsonTile]


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidMapError("The file is not valid UTF-8 text.") from error


def _txt_tile(character: str) -> Tile:
    match character:
        case "o":
            return Tile(walkable=True, dirty=True)
        case "x":
            return Tile(walkable=False, dirty=False)
        case _:
            raise InvalidMapError(f"{character!r} is not a valid tile character.")
