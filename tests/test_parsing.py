import pytest

from app.domain.models import Coordinate
from app.domain.parsing import InvalidMapError, parse_json_map, parse_txt_map


def test_txt_map_reports_its_shape_and_walkable_tiles():
    cleaning_map = parse_txt_map(b"oxoo\nooxo\noooo\n")

    assert (cleaning_map.rows, cleaning_map.cols, cleaning_map.walkable_tiles) == (3, 4, 10)
    assert cleaning_map.is_walkable(Coordinate(x=0, y=0))
    assert not cleaning_map.is_walkable(Coordinate(x=1, y=0))


def test_txt_tiles_start_dirty():
    cleaning_map = parse_txt_map(b"ox")

    assert cleaning_map.is_dirty(Coordinate(x=0, y=0))
    assert not cleaning_map.is_dirty(Coordinate(x=1, y=0))


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"oxoo\nooxo\noooo", id="no trailing line ending"),
        pytest.param(b"oxoo\r\nooxo\r\noooo\r\n", id="windows line endings"),
    ],
)
def test_accepted_txt_line_endings(content: bytes):
    assert parse_txt_map(content).walkable_tiles == 10


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"", id="empty file"),
        pytest.param(b"\n", id="only a line ending"),
        pytest.param(b"oo\n\noo\n", id="blank line inside the grid"),
        pytest.param(b"oo\nooo\n", id="rows of different lengths"),
        pytest.param(b"oo\nOo\n", id="uppercase tile character"),
        pytest.param(b"oo\no.\n", id="unknown tile character"),
        pytest.param(b"oo\noo\n\n", id="two trailing line endings"),
        pytest.param("oò".encode("latin-1"), id="not utf-8"),
    ],
)
def test_invalid_txt_maps(content: bytes):
    with pytest.raises(InvalidMapError):
        parse_txt_map(content)


def json_map(*tiles: str, rows: int = 1, cols: int = 2) -> bytes:
    return f'{{"rows": {rows}, "cols": {cols}, "tiles": [{",".join(tiles)}]}}'.encode()


def test_json_map_reports_its_shape_and_walkable_tiles():
    content = b"""
    {
      "rows": 2,
      "cols": 3,
      "tiles": [
        {"x": 0, "y": 0, "walkable": true, "dirty": true},
        {"x": 1, "y": 0, "walkable": true, "dirty": false},
        {"x": 2, "y": 0, "walkable": false, "dirty": false},
        {"x": 0, "y": 1, "walkable": true},
        {"x": 1, "y": 1, "walkable": true},
        {"x": 2, "y": 1, "walkable": true}
      ]
    }
    """
    cleaning_map = parse_json_map(content)

    assert (cleaning_map.rows, cleaning_map.cols, cleaning_map.walkable_tiles) == (2, 3, 5)
    assert not cleaning_map.is_dirty(Coordinate(x=1, y=0))
    assert cleaning_map.is_dirty(Coordinate(x=0, y=1)), "an omitted dirty field means dirty"


def test_non_walkable_json_tile_may_omit_or_disable_dirty():
    cleaning_map = parse_json_map(
        json_map('{"x": 0, "y": 0, "walkable": false}', '{"x": 1, "y": 0, "walkable": false}')
    )

    assert cleaning_map.walkable_tiles == 0
    assert not cleaning_map.is_dirty(Coordinate(x=0, y=0))


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"not json", id="malformed json"),
        pytest.param(json_map('{"x": 0, "y": 0, "walkable": true}'), id="missing coordinate"),
        pytest.param(
            json_map(
                '{"x": 0, "y": 0, "walkable": true}',
                '{"x": 0, "y": 0, "walkable": true}',
            ),
            id="duplicate coordinate",
        ),
        pytest.param(
            json_map(
                '{"x": 0, "y": 0, "walkable": true}',
                '{"x": 2, "y": 0, "walkable": true}',
            ),
            id="coordinate outside the bounds",
        ),
        pytest.param(
            json_map(
                '{"x": 0, "y": 0, "walkable": false, "dirty": true}',
                '{"x": 1, "y": 0, "walkable": true}',
            ),
            id="dirty non-walkable tile",
        ),
        pytest.param(
            json_map('{"x": 0, "y": 0, "walkable": true}', rows=0, cols=1),
            id="non-positive rows",
        ),
        pytest.param(
            json_map('{"x": 0, "y": 0}', cols=1),
            id="missing walkable field",
        ),
        pytest.param(
            json_map('{"x": 0, "y": 0, "walkable": "true"}', cols=1),
            id="walkable is not a boolean",
        ),
        pytest.param(
            json_map('{"x": 0, "y": 0, "walkable": true, "dirt": false}', cols=1),
            id="misspelled tile field",
        ),
        pytest.param(
            b'{"rows": 1, "cols": 1, "tiles": [{"x": 0, "y": 0, "walkable": true}], "note": "hi"}',
            id="unknown document field",
        ),
    ],
)
def test_invalid_json_maps(content: bytes):
    with pytest.raises(InvalidMapError):
        parse_json_map(content)
