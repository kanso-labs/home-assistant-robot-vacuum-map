"""Merging the live data the b108gl publishes outside its map."""

import pytest

from custom_components.xiaomi_vacuum_map.connector.vacuums.xiaomi_miot_enrichment import (
    POSITION_UNKNOWN,
    parse_vacuum_position,
    place_vacuum,
)

DOCK = {"have_pile": 1, "pile_x": 150, "pile_y": 250, "pile_yaw": 9000}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            '{"x": 1200, "y": -340, "yaw": 2470}',
            {"x": 1200.0, "y": -340.0, "yaw": 2470},
        ),
        (
            {"pos_x": 1200, "pos_y": -340, "phi": 2470},
            {"x": 1200.0, "y": -340.0, "yaw": 2470},
        ),
        ("1200,-340,2470", {"x": 1200.0, "y": -340.0, "yaw": "2470"}),
        ("1200, -340", {"x": 1200.0, "y": -340.0, "yaw": 0}),
        ([1200, -340, 2470], {"x": 1200.0, "y": -340.0, "yaw": 2470}),
    ],
)
def test_parses_each_form_of_the_position(value, expected) -> None:
    """The property's JSON and comma-separated forms read the same."""
    assert parse_vacuum_position(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "  ",
        "0",
        "0,0",
        "0,0,0",
        f"{POSITION_UNKNOWN},{POSITION_UNKNOWN}",
        {"x": POSITION_UNKNOWN, "y": 200},
        "not a position",
        {"x": "far", "y": "away"},
    ],
)
def test_reads_no_position_when_there_is_none(value) -> None:
    """Empty values, the origin and the unknown sentinel mean no position."""
    assert parse_vacuum_position(value) is None


def test_places_a_moving_robot_where_it_reports() -> None:
    """Away from the dock, the robot is drawn at its reported position."""
    position = {"x": 1200.0, "y": -340.0, "yaw": 2470}

    assert place_vacuum(DOCK, position, docked=False)["position"] == position


def test_places_a_docked_robot_on_its_dock() -> None:
    """Docked, the robot is drawn on the dock, whatever position it reports."""
    position = {"x": 1200.0, "y": -340.0, "yaw": 2470}

    assert place_vacuum(DOCK, position, docked=True)["position"] == {
        "x": 150.0,
        "y": 250.0,
        "yaw": 9000,
    }


def test_places_a_robot_with_no_position_on_its_dock() -> None:
    """With no position reported, the robot is drawn on the dock."""
    assert place_vacuum(DOCK, None, docked=False)["position"]["x"] == 150.0


def test_leaves_the_map_alone_with_nothing_to_place() -> None:
    """No position and no dock leave the payload as it was."""
    payload = {"have_pile": 0}

    assert place_vacuum(payload, None, docked=True) is payload
