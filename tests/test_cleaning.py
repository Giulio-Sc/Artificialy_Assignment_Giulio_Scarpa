import pytest

from app.domain.cleaning import InvalidStartError, run_session
from app.domain.models import CleaningMap, Coordinate, RobotModel
from app.domain.parsing import parse_json_map, parse_txt_map
from app.domain.session import Action, SessionState


def at(x: int, y: int) -> Coordinate:
    return Coordinate(x=x, y=y)


def clean(
    cleaning_map: CleaningMap,
    robot_model: RobotModel = RobotModel.BASIC,
    start: Coordinate = Coordinate(x=0, y=0),
    actions: list[Action] | None = None,
):
    return run_session(cleaning_map, robot_model, start, actions or [])


def test_basic_robot_cleans_every_visited_tile():
    report = clean(
        parse_txt_map(b"oooo\noooo\noooo\n"),
        actions=[Action(direction="east", steps=2), Action(direction="south", steps=1)],
    )

    assert report.state is SessionState.COMPLETED
    assert report.submitted_actions == 2
    assert report.successful_steps == 3
    assert report.cleaned_tiles == [at(0, 0), at(1, 0), at(2, 0), at(2, 1)]
    assert report.final_position == at(2, 1)
    assert report.error is None


def test_basic_robot_cleans_an_already_clean_tile_again():
    cleaning_map = parse_txt_map(b"oo")
    actions = [Action(direction="east", steps=1), Action(direction="west", steps=1)]

    report = clean(cleaning_map, actions=actions)

    assert report.cleaned_tiles == [at(0, 0), at(1, 0), at(0, 0)]


def test_premium_robot_only_cleans_dirty_tiles():
    cleaning_map = parse_json_map(
        b"""
        {
          "rows": 1,
          "cols": 2,
          "tiles": [
            {"x": 0, "y": 0, "walkable": true, "dirty": true},
            {"x": 1, "y": 0, "walkable": true, "dirty": false}
          ]
        }
        """
    )
    actions = [Action(direction="east", steps=1)]

    first = clean(cleaning_map, RobotModel.PREMIUM, actions=actions)
    second = clean(cleaning_map, RobotModel.PREMIUM, actions=actions)

    assert first.cleaned_tiles == [at(0, 0)]
    assert second.cleaned_tiles == [], "cleanliness is kept between sessions"
    assert second.successful_steps == 1


def test_starting_tile_is_processed_without_any_action():
    report = clean(parse_txt_map(b"oo"))

    assert report.cleaned_tiles == [at(0, 0)]
    assert report.successful_steps == 0
    assert report.final_position == at(0, 0)


def test_collision_with_an_obstacle_stops_the_session():
    report = clean(
        parse_txt_map(b"ooxo\noooo\n"),
        actions=[Action(direction="east", steps=3), Action(direction="south", steps=1)],
    )

    assert report.state is SessionState.ERROR
    assert report.error is not None
    assert report.error.code == "collision"
    assert report.error.message
    assert report.error.position == at(2, 0)
    assert report.final_position == at(1, 0), "the robot stops before the invalid tile"
    assert report.submitted_actions == 2
    assert report.successful_steps == 1, "later steps and actions are not executed"
    assert report.cleaned_tiles == [at(0, 0), at(1, 0)], "earlier cleaning is preserved"


def test_collision_with_the_map_boundary_reports_the_outside_coordinate():
    report = clean(
        parse_txt_map(b"ooxo\noooo\n"),
        actions=[Action(direction="north", steps=1)],
    )

    assert report.state is SessionState.ERROR
    assert report.error is not None
    assert report.error.position == at(0, -1)
    assert report.final_position == at(0, 0)
    assert report.successful_steps == 0


def test_start_must_be_a_walkable_tile_of_the_map():
    cleaning_map = parse_txt_map(b"ox")

    with pytest.raises(InvalidStartError):
        clean(cleaning_map, start=at(1, 0))
    with pytest.raises(InvalidStartError):
        clean(cleaning_map, start=at(0, 5))


def test_duration_is_consistent_with_the_timestamps():
    report = clean(parse_txt_map(b"oo"))

    assert report.finished_at >= report.started_at
    assert report.duration_ms == int((report.finished_at - report.started_at).total_seconds() * 1000)
