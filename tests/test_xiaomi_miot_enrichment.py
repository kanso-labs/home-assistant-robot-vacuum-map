"""Merging the live data the b108gl publishes outside its map."""

import base64
import json
import struct
import zlib

import pytest

from custom_components.robot_vacuum_map.connector.vacuums.xiaomi_miot_enrichment import (
    MAX_TRAJECTORY_COORDINATE,
    POSITION_UNKNOWN,
    cloud_object_index,
    cloud_object_name,
    decode_trajectory,
    mop_runs,
    parse_vacuum_position,
    place_vacuum,
    with_path,
    with_restricted_regions,
)

# The pile_yaw a real S20+ reported for its dock, in milliradians.
DOCK = {"have_pile": 1, "pile_x": 150, "pile_y": 250, "pile_yaw": 1753}


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
        "yaw": 1.753,
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('{"index":1790794042,"obj_name":"1/123456789/3"}', 1790794042),
        ({"index": 1790794042, "obj_name": "1/123456789/3"}, 1790794042),
        ("1/123456789/1", None),
        ('{"obj_name": "1/123456789/1"}', None),
        ('{"index": "1790794042", "obj_name": "1/123456789/1"}', None),
        ('{"index": true, "obj_name": "1/123456789/1"}', None),
        ("1790794042", None),
        (1790794042, None),
        (None, None),
    ],
)
def test_reads_the_cloud_object_index(value, expected) -> None:
    """Only the JSON form carries an index, and only a whole number counts."""
    assert cloud_object_index(value) == expected


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


CORNERS = [
    {"x": 100, "y": 100},
    {"x": 400, "y": 100},
    {"x": 400, "y": 300},
    {"x": 100, "y": 300},
]
# A wall from (500, 100) to (500, 800), each end twice, as the parser reads a
# wall's ends from its first and third points.
WALL_POINTS = [
    {"x": 500, "y": 100},
    {"x": 500, "y": 100},
    {"x": 500, "y": 800},
    {"x": 500, "y": 800},
]


@pytest.mark.parametrize(
    "areas",
    [
        "[[100, 100, 400, 100, 400, 300, 100, 300]]",
        [100, 100, 400, 100, 400, 300, 100, 300],
        [[[100, 100], [400, 100], [400, 300], [100, 300]]],
        [{"points": [[100, 100], [400, 100], [400, 300], [100, 300]]}],
        [
            {
                "vertices": [
                    {"x": 100, "y": 100},
                    {"x": 400, "y": 100},
                    {"x": 400, "y": 300},
                    {"x": 100, "y": 300},
                ]
            }
        ],
        [
            {
                "x0": 100,
                "y0": 100,
                "x1": 400,
                "y1": 100,
                "x2": 400,
                "y2": 300,
                "x3": 100,
                "y3": 300,
            }
        ],
        [{"x1": 100, "y1": 100, "x2": 400, "y2": 300}],
        {"areas": [[100, 100, 400, 100, 400, 300, 100, 300]]},
        [{"id": 1, "fb_attr": 0, "fb_point": [100, 100, 400, 100, 400, 300, 100, 300]}],
        '{"value": "[[100, 100, 400, 100, 400, 300, 100, 300]]"}',
    ],
)
def test_reads_each_form_of_a_restricted_area(areas) -> None:
    """The property's JSON, list and object forms of an area read the same."""
    payload = with_restricted_regions({}, areas, None)

    assert payload["fb_regions"] == [{"type": "no_go", "points": CORNERS}]


@pytest.mark.parametrize(
    "walls",
    [
        "[[500, 100, 500, 800]]",
        [500, 100, 500, 800],
        [[[500, 100], [500, 800]]],
        [{"points": [{"x": 500, "y": 100}, {"x": 500, "y": 800}]}],
        [{"x0": 500, "y0": 100, "x1": 500, "y1": 800}],
        {"walls": [[500, 100, 500, 800]]},
    ],
)
def test_reads_each_form_of_a_wall(walls) -> None:
    """The property's JSON, list and object forms of a wall read the same."""
    payload = with_restricted_regions({}, None, walls)

    assert payload["fb_regions"] == [{"type": "wall", "points": WALL_POINTS}]


def test_reads_every_region_a_property_lists() -> None:
    """Several areas and walls come through in the order listed."""
    payload = with_restricted_regions(
        {},
        [100, 100, 400, 100, 400, 300, 100, 300, 0, 0, 50, 0, 50, 50, 0, 50],
        "[[500, 100, 500, 800], [0, 0, 0, 900]]",
    )

    assert [region["type"] for region in payload["fb_regions"]] == [
        "no_go",
        "no_go",
        "wall",
        "wall",
    ]


def test_skips_a_region_it_cannot_read() -> None:
    """A region with too few points or no numbers is left out, not the rest."""
    payload = with_restricted_regions(
        {}, [[100, 100, 400, 100, 400, 300, 100, 300], "a", [1, 2], {"x1": "a"}], None
    )

    assert payload["fb_regions"] == [{"type": "no_go", "points": CORNERS}]


@pytest.mark.parametrize(
    "value", [None, "", "  ", "[]", "{}", "not json", 42, "[1, 2, 3]", [[1, 2]]]
)
def test_reads_no_regions_from_what_lists_none(value) -> None:
    """Nothing that lists a region leaves the payload as it was."""
    payload = {"width": 20}

    assert with_restricted_regions(payload, value, value) is payload


def test_keeps_the_regions_the_map_carries() -> None:
    """Regions from 2-11 and 2-12 go in after any the map has of its own."""
    carried = {"type": "no_mop", "points": CORNERS}

    payload = with_restricted_regions(
        {"fb_regions": [carried]}, None, "[[500, 100, 500, 800]]"
    )

    assert payload["fb_regions"] == [carried, {"type": "wall", "points": WALL_POINTS}]


def test_reads_a_no_mop_area_by_its_fb_attr() -> None:
    """An area whose fb_attr is 1 is a no-mop area, as the parser reads it in maps."""
    payload = with_restricted_regions(
        {},
        '[{"id": 2, "fb_attr": 1, "fb_point": [100, 100, 400, 100, 400, 300, 100, 300]}]',
        None,
    )

    assert payload["fb_regions"] == [{"type": "no_mop", "points": CORNERS}]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Captured from a real S20+ while it swept, and while it drove home.
        ('{"position":[-2630,-3280,6054]}', {"x": -2630.0, "y": -3280.0, "yaw": 6.054}),
        ('{"position":[-1290,-1810,870]}', {"x": -1290.0, "y": -1810.0, "yaw": 0.87}),
        ('{"position":[-2630,-3280]}', {"x": -2630.0, "y": -3280.0, "yaw": 0}),
    ],
)
def test_parses_the_position_a_real_s20_plus_publishes(value, expected) -> None:
    """Its yaw is in milliradians, and goes on in radians for the parser."""
    assert parse_vacuum_position(value) == expected


def test_reads_the_areas_a_real_s20_plus_lists_under_forbidden_regions() -> None:
    """A real S20+ lists its 2-11 areas under forbidden_regions."""
    payload = with_restricted_regions(
        {},
        '{"forbidden_regions":[[100, 100, 400, 100, 400, 300, 100, 300]]}',
        None,
    )

    assert payload["fb_regions"] == [{"type": "no_go", "points": CORNERS}]


def test_reads_no_areas_from_the_empty_list_a_real_s20_plus_publishes() -> None:
    payload = {"width": 20}

    assert (
        with_restricted_regions(
            payload, '{"forbidden_regions":[]}', '{"restricted_walls":[]}'
        )
        is payload
    )
