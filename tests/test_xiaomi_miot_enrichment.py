"""Merging the live data the b108gl publishes outside its map."""

import base64
import json
import struct
import zlib

import pytest

from custom_components.xiaomi_vacuum_map.connector.vacuums.xiaomi_miot_enrichment import (
    MAX_TRAJECTORY_COORDINATE,
    POSITION_UNKNOWN,
    cloud_object_name,
    decode_trajectory,
    mop_runs,
    parse_vacuum_position,
    place_vacuum,
    with_path,
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


def test_places_a_cleaning_robot_with_no_position_at_the_end_of_its_path() -> None:
    """Mid-clean with 7-4 silent, the robot is where its path ends."""
    path = [{"x": 100, "y": 200}, {"x": 300, "y": 400}]

    assert place_vacuum(DOCK, None, docked=False, path=path)["position"] == {
        "x": 300,
        "y": 400,
        "yaw": 0,
    }


def test_places_a_docked_robot_on_its_dock_whatever_its_path() -> None:
    """A path does not pull a docked robot off its dock."""
    path = [{"x": 300, "y": 400}]

    assert place_vacuum(DOCK, None, docked=True, path=path)["position"]["x"] == 150.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1/123456789/trajectory_7", "trajectory_7"),
        ('{"obj_name": "1/123456789/trajectory_7"}', "trajectory_7"),
        ({"obj_name": "1/123456789/trajectory_7"}, "trajectory_7"),
        ("trajectory_7", "trajectory_7"),
        (1727700000, "1727700000"),
        ("1727700000", "1727700000"),
        (None, None),
        ("", None),
        ({"obj_name": None}, None),
    ],
)
def test_reads_the_cloud_object_name(value, expected) -> None:
    """Paths, JSON and bare names all come down to the object's name."""
    assert cloud_object_name(value) == expected


def records(*points: tuple[int, int, int]) -> bytes:
    """Trajectory records: a marker byte, then x and y as little-endian int32."""
    return b"".join(struct.pack("<Bii", *point) for point in points)


POINTS = records((0x02, 100, 200), (0x03, 150, -250), (0x02, -300, 400))
DECODED = [
    {"x": 100, "y": 200, "mop": False},
    {"x": 150, "y": -250, "mop": True},
    {"x": -300, "y": 400, "mop": False},
]


@pytest.mark.parametrize(
    "raw",
    [
        zlib.compress(POINTS),
        base64.b64encode(zlib.compress(POINTS)),
        json.dumps({"data": base64.b64encode(zlib.compress(POINTS)).decode()}).encode(),
        POINTS,
        zlib.compress(b"\x00\x09header" + POINTS),
    ],
    ids=["zlib", "base64", "json", "uncompressed", "header"],
)
def test_decodes_the_trajectory_in_each_form(raw: bytes) -> None:
    """Each form the object arrives in decodes to the same points."""
    assert decode_trajectory(raw) == DECODED


def test_drops_points_no_map_could_hold() -> None:
    """A coordinate beyond any map is a record read out of step."""
    raw = zlib.compress(records((0x02, MAX_TRAJECTORY_COORDINATE + 1, 0), (0x02, 1, 2)))

    assert decode_trajectory(raw) == [{"x": 1, "y": 2, "mop": False}]


@pytest.mark.parametrize(
    "raw", [b"", b"not a trajectory", b"{not json", b'{"data": 7}']
)
def test_decodes_nothing_from_what_is_not_a_trajectory(raw: bytes) -> None:
    """Anything that does not decode gives no points rather than an error."""
    assert decode_trajectory(raw) == []


def test_puts_the_path_in_without_its_mop_marks() -> None:
    """The parser draws the whole path, and no mop path of its own."""
    payload = with_path({"have_pile": 1}, DECODED)

    assert payload["paths"] == [
        {"x": 100, "y": 200},
        {"x": 150, "y": -250},
        {"x": -300, "y": 400},
    ]


def test_keeps_a_path_the_map_already_has() -> None:
    """A map carrying its own path keeps it."""
    payload = {"paths": [{"x": 1, "y": 1}]}

    assert with_path(payload, DECODED) is payload


def mopped(*xs: int) -> list[dict]:
    return [{"x": x, "y": 0, "mop": True} for x in xs]


def swept(*xs: int) -> list[dict]:
    return [{"x": x, "y": 0, "mop": False} for x in xs]


def test_splits_mop_runs_where_the_robot_stopped_mopping() -> None:
    """Mopping, sweeping, then mopping again makes two runs, not one line."""
    runs = mop_runs(mopped(0, 100, 200) + swept(300) + mopped(400, 500, 600))

    assert [[point.x for point in run] for run in runs] == [
        [0, 100, 200],
        [400, 500, 600],
    ]


def test_splits_mop_runs_across_a_gap() -> None:
    """Two mopped points more than 500 mm apart start a new run."""
    runs = mop_runs(mopped(0, 100, 200, 800, 900, 1000))

    assert [[point.x for point in run] for run in runs] == [
        [0, 100, 200],
        [800, 900, 1000],
    ]


def test_drops_mop_runs_too_short_to_draw() -> None:
    """A run of fewer than three points is not drawn."""
    assert mop_runs(mopped(0, 100) + swept(200) + mopped(300)) == []
