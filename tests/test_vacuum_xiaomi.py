"""The Xiaomi connector, against the Xiaomi Robot Vacuum S20+ (b108gl)."""

import base64
import json
import math
import pathlib
import struct
import zlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from vacuum_map_parser_base.config.color import ColorsPalette, SupportedColor
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Size, Sizes

from custom_components.robot_vacuum_map.connector.vacuums.base.model import (
    VacuumConfig,
)
from custom_components.robot_vacuum_map.connector.vacuums.vacuum_xiaomi import (
    OFF_UPDATES,
    XiaomiCloudVacuum,
)
from custom_components.robot_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudDeviceInfo,
)

B108GL = "xiaomi.vacuum.b108gl"

# The b108gl's status, service 2 property 1, as its MIoT spec numbers it.
IDLE = 1
CHARGING = 2
BREAK_CHARGING = 3
SWEEPING = 4
PAUSED = 5
GO_CHARGING = 6
REMOTE = 7
CHARGED = 8
MAPPING = 9
UPDATING = 10


def make_vacuum(model: str, **config: Any) -> XiaomiCloudVacuum:
    """A connector for one vacuum, with no cloud or device behind it."""
    device_info = XiaomiCloudDeviceInfo(
        device_id="123456789",
        name="S20+",
        model=model,
        token="0" * 32,
        spec_type="urn:miot-spec-v2:device:vacuum:0000A006",
        local_ip="192.0.2.10",
        mac="aa:bb:cc:dd:ee:ff",
        server="de",
        home_id=1,
        user_id=1,
    )
    return XiaomiCloudVacuum(
        VacuumConfig(
            connector=MagicMock(),
            device_info=device_info,
            server="de",
            device_id="123456789",
            host="192.0.2.10",
            token="0" * 32,
            model=model,
            **{
                "palette": ColorsPalette(),
                "drawables": list(Drawable),
                "image_config": ImageConfig(),
                "sizes": Sizes(),
                "texts": [],
                **config,
            },
        )
    )


async def poll(vacuum: XiaomiCloudVacuum, status: int, times: int) -> list[bool]:
    """Answer should_update_map `times` times with the vacuum at `status`."""
    vacuum._miot_device = MagicMock()
    vacuum._miot_device.get_property_by.return_value = [
        {"siid": 2, "piid": 1, "value": status}
    ]
    return [await vacuum.should_update_map() for _ in range(times)]


@pytest.mark.parametrize("status", [SWEEPING, GO_CHARGING, REMOTE, MAPPING])
async def test_b108gl_keeps_updating_while_it_moves(status: int) -> None:
    """A clean keeps the map refreshing on every poll, however long it runs."""
    vacuum = make_vacuum(B108GL)

    assert all(await poll(vacuum, status, OFF_UPDATES + 10))
    vacuum._miot_device.get_property_by.assert_called_with(2, 1)


@pytest.mark.parametrize(
    "status", [IDLE, CHARGING, BREAK_CHARGING, PAUSED, CHARGED, UPDATING]
)
async def test_b108gl_stops_updating_once_idle(status: int) -> None:
    """Idle, the map refreshes a few more times and then stops."""
    vacuum = make_vacuum(B108GL)

    assert await poll(vacuum, status, OFF_UPDATES + 2) == [True] * OFF_UPDATES + [
        False,
        False,
    ]


async def test_b108gl_starts_updating_again_when_a_clean_starts() -> None:
    """Moving again resets the idle count."""
    vacuum = make_vacuum(B108GL)
    await poll(vacuum, CHARGED, OFF_UPDATES + 2)

    assert await poll(vacuum, SWEEPING, 1) == [True]


async def test_other_models_keep_the_parser_mapping() -> None:
    """Models without an override keep vacuum_map_parser_xiaomi's idle states."""
    vacuum = make_vacuum("xiaomi.vacuum.c102")

    assert (await poll(vacuum, 4, OFF_UPDATES + 1))[-1] is False


def json_map(**extra: Any) -> dict[str, Any]:
    """A 20 x 20 JSON map of free floor, 50 mm to the pixel, with a dock on it."""
    grid = zlib.compress(bytes([1] * 400))
    return {
        "width": 20,
        "height": 20,
        "resolution": 50,
        "origin_x": 0,
        "origin_y": 0,
        "map_data": base64.b64encode(grid).decode(),
        "have_pile": 1,
        "pile_x": 150,
        "pile_y": 250,
        "pile_yaw": 0,
        **extra,
    }


def stub_device(
    vacuum: XiaomiCloudVacuum, properties: dict[tuple[int, int], Any]
) -> None:
    """Answer MIoT reads from `properties`, keyed by (siid, piid)."""

    def get_property_by(siid: int, piid: int) -> list[dict[str, Any]]:
        return [{"siid": siid, "piid": piid, "value": properties.get((siid, piid))}]

    vacuum._miot_device = MagicMock()
    vacuum._miot_device.get_property_by.side_effect = get_property_by


async def parse(vacuum: XiaomiCloudVacuum, payload: dict[str, Any]):
    """Parse a map that decrypts to `payload`, after the reads get_map makes."""
    vacuum._xiaomi_map_data_parser.unpack_map = MagicMock(
        return_value=json.dumps(payload)
    )
    await vacuum._read_live_data()
    return vacuum.decode_and_parse(b"encrypted map")


async def test_b108gl_draws_the_robot_at_property_7_4() -> None:
    """Cleaning, the robot is drawn where property 7-4 puts it."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): SWEEPING, (7, 4): '{"x": 600, "y": 400, "yaw": 300}'})
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (600, 400)
    # 300 is 3 degrees in hundredths, converted once, by the parser.
    assert map_data.vacuum_position.a == pytest.approx(3.0)


async def test_b108gl_draws_the_robot_on_its_dock_while_docked() -> None:
    """Charged on the dock, the robot is drawn there, not at a stale position."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): CHARGED, (7, 4): '{"x": 600, "y": 400, "yaw": 0}'})
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


async def test_b108gl_draws_the_robot_on_its_dock_when_7_4_is_unknown() -> None:
    """With no position to report, the robot is drawn on the dock."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): SWEEPING, (7, 4): "1100,1100,0"})
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


async def test_other_models_parse_the_map_as_it_comes() -> None:
    """Models with no live properties never read 7-4."""
    vacuum = make_vacuum("xiaomi.vacuum.c102")
    stub_device(vacuum, {(7, 4): '{"x": 600, "y": 400}'})

    map_data = await parse(vacuum, json_map())

    assert map_data.vacuum_position is None
    vacuum._miot_device.get_property_by.assert_not_called()


MAP_OBJECT = '{"obj_name": "1/123456789/map_7"}'
TRAJECTORY_OBJECT = "1/123456789/trajectory_7"


def trajectory(*points: tuple[int, int, int]) -> bytes:
    """A zlib-compressed trajectory object: marker, then x and y as int32."""
    return zlib.compress(b"".join(struct.pack("<Bii", *point) for point in points))


# Swept across, then two mop runs that a single line would join.
TRAJECTORY = trajectory(
    (0x02, 100, 100),
    (0x02, 200, 100),
    (0x03, 300, 100),
    (0x03, 400, 100),
    (0x03, 500, 100),
    (0x02, 600, 100),
    (0x03, 700, 800),
    (0x03, 800, 800),
    (0x03, 900, 800),
)


def stub_cloud(vacuum: XiaomiCloudVacuum, **objects: bytes) -> AsyncMock:
    """Serve each cloud object by name, and decrypt the map to json_map().

    An object's URL is its name, so the download returned is awaited with it.
    """
    vacuum.get_map_url = AsyncMock(side_effect=lambda name: name)
    download = AsyncMock(side_effect=lambda url: objects.get(url))
    vacuum._connector.get_raw_map_data = download
    vacuum._xiaomi_map_data_parser.unpack_map = MagicMock(
        return_value=json.dumps(json_map())
    )
    return download


async def test_b108gl_draws_the_path_from_property_7_2() -> None:
    """Cleaning, the trajectory 7-2 names becomes the path, mop runs apart."""
    vacuum = make_vacuum(B108GL)
    stub_device(
        vacuum,
        {(2, 1): SWEEPING, (7, 1): MAP_OBJECT, (7, 2): TRAJECTORY_OBJECT, (7, 4): None},
    )
    download = stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    assert await vacuum.should_update_map()

    map_data, _ = await vacuum.get_map()

    assert [(p.x, p.y) for p in map_data.path.path[0]] == [
        (100, 100),
        (200, 100),
        (300, 100),
        (400, 100),
        (500, 100),
        (600, 100),
        (700, 800),
        (800, 800),
        (900, 800),
    ]
    assert [[p.x for p in run] for run in map_data.mop_path.path] == [
        [300, 400, 500],
        [700, 800, 900],
    ]
    # With 7-4 silent, the robot is drawn where its path ends.
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (900, 800)
    download.assert_any_await("trajectory_7")


async def test_b108gl_draws_no_stale_path_on_its_dock() -> None:
    """Docked, the last clean's trajectory is neither downloaded nor drawn."""
    vacuum = make_vacuum(B108GL)
    stub_device(
        vacuum,
        {(2, 1): CHARGED, (7, 1): MAP_OBJECT, (7, 2): TRAJECTORY_OBJECT, (7, 4): None},
    )
    download = stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    assert await vacuum.should_update_map()

    map_data, _ = await vacuum.get_map()

    assert map_data.path is None
    assert map_data.mop_path is None
    assert [call.args for call in download.await_args_list] == [("map_7",)]
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


async def test_b108gl_draws_the_mop_runs_on_the_map() -> None:
    """The mop runs change the image, which a path without mopping does not."""

    async def image_for(raw_trajectory: bytes) -> bytes:
        vacuum = make_vacuum(B108GL)
        stub_device(
            vacuum,
            {(2, 1): SWEEPING, (7, 1): MAP_OBJECT, (7, 2): TRAJECTORY_OBJECT},
        )
        stub_cloud(vacuum, map_7=b"map", trajectory_7=raw_trajectory)
        assert await vacuum.should_update_map()
        map_data, _ = await vacuum.get_map()
        return map_data.image.data.tobytes()

    swept_only = trajectory(
        *[
            (0x02, x, y)
            for _, x, y in struct.iter_unpack("<Bii", zlib.decompress(TRAJECTORY))
        ]
    )

    assert await image_for(TRAJECTORY) != await image_for(swept_only)


async def test_b108gl_survives_a_trajectory_that_does_not_download() -> None:
    """With no trajectory to be had, the map is drawn without a path."""
    vacuum = make_vacuum(B108GL)
    stub_device(
        vacuum,
        {(2, 1): SWEEPING, (7, 1): MAP_OBJECT, (7, 2): TRAJECTORY_OBJECT, (7, 4): None},
    )
    stub_cloud(vacuum, map_7=b"map")
    assert await vacuum.should_update_map()

    map_data, _ = await vacuum.get_map()

    assert map_data.path is None
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


def indexed(index: int, name: str) -> str:
    """A 7-1 or 7-2 value as python-miio reads it: the object's path and index."""
    return json.dumps({"index": index, "obj_name": f"1/123456789/{name}"})


async def refresh_at(
    vacuum: XiaomiCloudVacuum, map_index: int, trajectory_index: int, x: int
):
    """Refresh with 7-1 and 7-2 at these indexes, and the robot at x."""
    stub_device(
        vacuum,
        {
            (2, 1): SWEEPING,
            (7, 1): indexed(map_index, "map_7"),
            (7, 2): indexed(trajectory_index, "trajectory_7"),
            (7, 4): json.dumps({"position": [x, 400, 0]}),
        },
    )
    assert await vacuum.should_update_map()
    map_data, _ = await vacuum.get_map()
    return map_data


@pytest.mark.parametrize(
    ("map_index", "trajectory_index", "downloads"),
    [
        (1790794042, 1790794040, []),
        (1790794054, 1790794040, ["map_7"]),
        (1790794042, 1790794052, ["trajectory_7"]),
        (1790794054, 1790794052, ["trajectory_7", "map_7"]),
    ],
    ids=["neither changed", "the map changed", "the path changed", "both changed"],
)
async def test_b108gl_downloads_only_what_changed(
    map_index: int, trajectory_index: int, downloads: list[str]
) -> None:
    """An object whose index has not moved is neither asked for nor downloaded.

    The map is still drawn afresh, with the robot where it is now.
    """
    vacuum = make_vacuum(B108GL)
    download = stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    await refresh_at(vacuum, 1790794042, 1790794040, x=600)
    download.reset_mock()
    vacuum.get_map_url.reset_mock()

    map_data = await refresh_at(vacuum, map_index, trajectory_index, x=900)

    assert [call.args for call in vacuum.get_map_url.await_args_list] == [
        (name,) for name in downloads
    ]
    assert [call.args for call in download.await_args_list] == [
        (name,) for name in downloads
    ]
    assert len(map_data.path.path[0]) == 9
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (900, 400)


async def test_b108gl_downloads_an_object_with_no_index_every_time() -> None:
    """Xiaomi Home gives 7-2 as a bare path, with no index to go by."""
    vacuum = make_vacuum(B108GL)
    download = stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    stub_device(
        vacuum,
        {
            (2, 1): SWEEPING,
            (7, 1): indexed(1790794042, "map_7"),
            (7, 2): TRAJECTORY_OBJECT,
        },
    )

    for _ in range(2):
        assert await vacuum.should_update_map()
        await vacuum.get_map()

    assert [call.args for call in download.await_args_list] == [
        ("trajectory_7",),
        ("map_7",),
        ("trajectory_7",),
    ]


async def test_b108gl_downloads_everything_again_after_a_failed_refresh() -> None:
    """What was downloaded may be what failed, whatever its index says."""
    vacuum = make_vacuum(B108GL)
    download = stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    vacuum._xiaomi_map_data_parser.unpack_map.side_effect = [
        ValueError("the map does not decrypt"),
        json.dumps(json_map()),
    ]
    with pytest.raises(ValueError):
        await refresh_at(vacuum, 1790794042, 1790794040, x=600)
    download.reset_mock()

    await refresh_at(vacuum, 1790794042, 1790794040, x=600)

    assert [call.args for call in download.await_args_list] == [
        ("trajectory_7",),
        ("map_7",),
    ]


RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
async def test_b108gl_draws_mop_runs_over_the_path_at_every_rotation(
    rotate: int,
) -> None:
    """Each mop run covers its stretch of path, however the map is rotated.

    The parser rotates the image before the runs are drawn. With the path in
    red, the runs in blue and both the same width, a blue pixel off the red
    path would be a run drawn out of step with the rotation.
    """

    async def colours(raw_trajectory: bytes) -> tuple[set, set]:
        vacuum = make_vacuum(
            B108GL,
            palette=ColorsPalette(
                {SupportedColor.PATH: RED, SupportedColor.MOP_PATH: BLUE}
            ),
            drawables=[Drawable.PATH, Drawable.MOP_PATH],
            image_config=ImageConfig(scale=4, rotate=rotate),
            sizes=Sizes({Size.PATH_WIDTH: 3, Size.MOP_PATH_WIDTH: 3}),
        )
        stub_device(
            vacuum, {(2, 1): SWEEPING, (7, 1): MAP_OBJECT, (7, 2): TRAJECTORY_OBJECT}
        )
        stub_cloud(vacuum, map_7=b"map", trajectory_7=raw_trajectory)
        assert await vacuum.should_update_map()
        map_data, _ = await vacuum.get_map()
        image = map_data.image.data.convert("RGBA")
        pixels = [
            ((x, y), image.getpixel((x, y)))
            for x in range(image.width)
            for y in range(image.height)
        ]
        return {xy for xy, c in pixels if c == BLUE}, {
            xy for xy, c in pixels if c == RED
        }

    swept_only = trajectory(
        *[
            (0x02, x, y)
            for _, x, y in struct.iter_unpack("<Bii", zlib.decompress(TRAJECTORY))
        ]
    )
    mop_pixels, _ = await colours(TRAJECTORY)
    _, path_pixels = await colours(swept_only)

    assert mop_pixels
    assert mop_pixels <= path_pixels


AREA = "[[100, 100, 400, 100, 400, 300, 100, 300]]"
WALL = "[[500, 100, 500, 800]]"


async def test_b108gl_draws_the_areas_and_walls_from_2_11_and_2_12() -> None:
    """The no-go areas and virtual walls set in the Xiaomi app are drawn."""

    async def parsed(areas: Any, walls: Any):
        vacuum = make_vacuum(B108GL)
        stub_device(vacuum, {(2, 1): CHARGED, (2, 11): areas, (2, 12): walls})
        assert await vacuum.should_update_map()
        return await parse(vacuum, json_map())

    map_data = await parsed(AREA, WALL)

    assert [area.as_list() for area in map_data.no_go_areas] == [
        [100, 100, 400, 100, 400, 300, 100, 300]
    ]
    assert [wall.as_list() for wall in map_data.walls] == [[500, 100, 500, 800]]
    assert (
        map_data.image.data.tobytes() != (await parsed(None, None)).image.data.tobytes()
    )


async def test_b108gl_drops_areas_and_walls_once_removed() -> None:
    """An area or wall removed in the Xiaomi app is gone at the next refresh."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): SWEEPING, (2, 11): AREA, (2, 12): WALL})
    assert await vacuum.should_update_map()
    await parse(vacuum, json_map())
    stub_device(vacuum, {(2, 1): SWEEPING, (2, 11): "[]", (2, 12): ""})

    map_data = await parse(vacuum, json_map())

    assert map_data.no_go_areas == []
    assert map_data.walls == []


@pytest.mark.parametrize("value", [None, "not an object name"])
async def test_falls_back_to_the_default_map_name(value: Any) -> None:
    """With no map name in its property, the connector asks for the default."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(7, 1): value})

    assert await vacuum.get_map_name() == "0"


async def test_b108gl_draws_a_no_mop_area_from_2_11() -> None:
    """An area 2-11 marks as no-mop is drawn as one, not as no-go."""
    vacuum = make_vacuum(B108GL)
    stub_device(
        vacuum,
        {
            (2, 1): CHARGED,
            (
                2,
                11,
            ): '[{"id": 2, "fb_attr": 1, "fb_point": [100, 100, 400, 100, 400, 300, 100, 300]}]',
        },
    )
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert map_data.no_go_areas == []
    assert [area.as_list() for area in map_data.no_mopping_areas] == [
        [100, 100, 400, 100, 400, 300, 100, 300]
    ]


async def test_b108gl_keeps_its_raw_live_data_for_diagnostics() -> None:
    """Diagnostics carry each property as read and the trajectory as downloaded.

    The account and device IDs in the object names are taken out.
    """
    vacuum = make_vacuum(B108GL)
    stub_device(
        vacuum,
        {
            (2, 1): SWEEPING,
            (7, 1): MAP_OBJECT,
            (7, 2): TRAJECTORY_OBJECT,
            (7, 4): "600,400,300",
            (2, 11): AREA,
            (2, 12): WALL,
        },
    )
    stub_cloud(vacuum, map_7=b"map", trajectory_7=TRAJECTORY)
    assert await vacuum.should_update_map()

    await vacuum.get_map()
    data = vacuum.additional_data()

    assert data["miot_properties"] == {
        "2-1": SWEEPING,
        "2-11": AREA,
        "2-12": WALL,
        "7-1": '{"obj_name": "**REDACTED**/**REDACTED**/map_7"}',
        "7-2": "**REDACTED**/**REDACTED**/trajectory_7",
        "7-4": "600,400,300",
    }
    assert base64.b64decode(data["trajectory_raw"]) == TRAJECTORY


async def test_b108gl_draws_the_robot_where_a_real_s20_plus_reports_it() -> None:
    """The captured 7-4, taken as the robot drove home, places and turns it."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): GO_CHARGING, (7, 4): '{"position":[-1290,-1810,870]}'})
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (-1290, -1810)
    # 870 milliradians is 49.8 degrees, the way the robot was driving.
    assert map_data.vacuum_position.a == pytest.approx(math.degrees(0.87))


# Captured from a real S20+ on 0.7.1: its map, decrypted, and two diagnostics
# downloads taken during one clean, while it swept and while it drove home. The
# room names are replaced, and the object names keep the redaction diagnostics
# gave them.
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "b108gl"
CAPTURED_MAP = json.loads((FIXTURES / "map.json").read_text())
CAPTURE_SWEEPING, CAPTURE_GOING_HOME = json.loads(
    (FIXTURES / "captures.json").read_text()
)
CAPTURES = pytest.mark.parametrize(
    "capture", [CAPTURE_SWEEPING, CAPTURE_GOING_HOME], ids=["sweeping", "going home"]
)


def stub_capture(
    vacuum: XiaomiCloudVacuum,
    capture: dict[str, Any],
    overrides: dict[tuple[int, int], Any] | None = None,
) -> AsyncMock:
    """Answer as the S20+ did when the capture was taken, with its real map."""
    properties = {
        tuple(int(part) for part in key.split("-")): value
        for key, value in capture["properties"].items()
    }
    stub_device(vacuum, properties | (overrides or {}))
    download = stub_cloud(vacuum, **{"3": b"map", "1": capture["trajectory"].encode()})
    vacuum._xiaomi_map_data_parser.unpack_map = MagicMock(
        return_value=json.dumps(CAPTURED_MAP)
    )
    return download


@CAPTURES
async def test_b108gl_keeps_refreshing_through_a_captured_clean(
    capture: dict[str, Any],
) -> None:
    """Sweeping (4) and driving home (6) both keep the map refreshing."""
    vacuum = make_vacuum(B108GL)

    assert all(await poll(vacuum, capture["properties"]["2-1"], OFF_UPDATES + 2))


@pytest.mark.parametrize(
    ("capture", "points", "mop_run_lengths"),
    [(CAPTURE_SWEEPING, 139, [125]), (CAPTURE_GOING_HOME, 218, [189])],
    ids=["sweeping", "going home"],
)
async def test_b108gl_draws_a_captured_clean(
    capture: dict[str, Any], points: int, mop_run_lengths: list[int]
) -> None:
    """The real map, path, mop run and position come out as the robot had them."""
    vacuum = make_vacuum(B108GL)
    download = stub_capture(vacuum, capture)
    assert await vacuum.should_update_map()

    map_data, _ = await vacuum.get_map()

    # 7-2 names the trajectory "1" and 7-1 the map "3".
    assert [call.args for call in download.await_args_list] == [("1",), ("3",)]
    assert len(map_data.rooms) == 11
    assert (map_data.charger.x, map_data.charger.y) == (200, 134)
    assert len(map_data.path.path[0]) == points
    assert [len(run) for run in map_data.mop_path.path] == mop_run_lengths
    x, y, yaw = json.loads(capture["properties"]["7-4"])["position"]
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (x, y)
    assert map_data.vacuum_position.a == pytest.approx(math.degrees(yaw / 1000))


async def test_b108gl_puts_the_robot_on_the_captured_dock_once_charged() -> None:
    """Docked, the robot sits on the real dock, with no path left over."""
    vacuum = make_vacuum(B108GL)
    download = stub_capture(vacuum, CAPTURE_GOING_HOME, {(2, 1): CHARGED})
    assert await vacuum.should_update_map()

    map_data, _ = await vacuum.get_map()

    assert [call.args for call in download.await_args_list] == [("3",)]
    assert map_data.path is None
    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (200, 134)
    # The dock's pile_yaw, 1753, is 100.4 degrees in milliradians.
    assert map_data.vacuum_position.a == pytest.approx(math.degrees(1.753))


class FakeXiaomiHome:
    """A live source answering as Xiaomi Home's entities would."""

    def __init__(self, activity: str | None, **values: Any) -> None:
        self.activity_value = activity
        self.values = {
            tuple(int(p) for p in key.removeprefix("p").split("_")): value
            for key, value in values.items()
        }

    def value(self, siid: int, piid: int) -> Any:
        return self.values.get((siid, piid))

    def activity(self) -> str | None:
        return self.activity_value


def with_xiaomi_home(vacuum: XiaomiCloudVacuum, source: FakeXiaomiHome) -> None:
    vacuum._live_properties = source
    stub_device(vacuum, {})


@pytest.mark.parametrize(
    ("activity", "status", "refreshes"),
    [
        ("cleaning", SWEEPING, True),
        ("returning", GO_CHARGING, True),
        ("docked", CHARGING, True),
        ("paused", PAUSED, True),
    ],
)
async def test_b108gl_reads_its_status_from_xiaomi_home(
    activity: str, status: int, refreshes: bool
) -> None:
    """The activity stands in for the status, and the vacuum is not asked."""
    vacuum = make_vacuum(B108GL)
    with_xiaomi_home(vacuum, FakeXiaomiHome(activity))

    assert await vacuum.should_update_map() is refreshes
    assert vacuum._status_value == status
    vacuum._miot_device.get_property_by.assert_not_called()


async def test_b108gl_counts_an_idle_robot_that_moved_as_remote_controlled() -> None:
    """Xiaomi Home reads remote control as idle; a moving position gives it away."""
    vacuum = make_vacuum(B108GL)
    source = FakeXiaomiHome("idle", p7_4='{"position":[0,0,0]}')
    with_xiaomi_home(vacuum, source)
    polls = [await vacuum.should_update_map() for _ in range(OFF_UPDATES + 1)]
    assert polls[-1] is False

    source.values[(7, 4)] = '{"position":[400,0,0]}'

    assert await vacuum.should_update_map()
    assert vacuum._status_value == REMOTE


async def test_b108gl_asks_the_vacuum_when_xiaomi_home_cannot_tell() -> None:
    vacuum = make_vacuum(B108GL)
    with_xiaomi_home(vacuum, FakeXiaomiHome(None))
    vacuum._miot_device.get_property_by.side_effect = lambda siid, piid: [
        {"siid": siid, "piid": piid, "value": SWEEPING}
    ]

    assert await vacuum.should_update_map()
    vacuum._miot_device.get_property_by.assert_called_with(2, 1)


async def test_b108gl_draws_the_robot_where_xiaomi_home_reports_it() -> None:
    """7-4 comes from Xiaomi Home's sensor, and the vacuum is not asked for it."""
    vacuum = make_vacuum(B108GL)
    with_xiaomi_home(
        vacuum, FakeXiaomiHome("cleaning", p7_4='{"position":[-1290,-1810,870]}')
    )
    assert await vacuum.should_update_map()

    map_data = await parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (-1290, -1810)
    asked = {call.args for call in vacuum._miot_device.get_property_by.call_args_list}
    assert (7, 4) not in asked
