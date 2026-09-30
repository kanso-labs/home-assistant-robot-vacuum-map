"""The Xiaomi connector, against the Xiaomi Robot Vacuum S20+ (b108gl)."""

import base64
import json
import zlib
from typing import Any
from unittest.mock import MagicMock

import pytest
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes

from custom_components.xiaomi_vacuum_map.connector.vacuums.base.model import (
    VacuumConfig,
)
from custom_components.xiaomi_vacuum_map.connector.vacuums.vacuum_xiaomi import (
    OFF_UPDATES,
    XiaomiCloudVacuum,
)
from custom_components.xiaomi_vacuum_map.connector.xiaomi_cloud.connector import (
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


def make_vacuum(model: str) -> XiaomiCloudVacuum:
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
            palette=ColorsPalette(),
            drawables=list(Drawable),
            image_config=ImageConfig(),
            sizes=Sizes(),
            texts=[],
        )
    )


def poll(vacuum: XiaomiCloudVacuum, status: int, times: int) -> list[bool]:
    """Answer should_update_map `times` times with the vacuum at `status`."""
    vacuum._miot_device = MagicMock()
    vacuum._miot_device.get_property_by.return_value = [
        {"siid": 2, "piid": 1, "value": status}
    ]
    return [vacuum.should_update_map for _ in range(times)]


@pytest.mark.parametrize("status", [SWEEPING, GO_CHARGING, REMOTE, MAPPING])
def test_b108gl_keeps_updating_while_it_moves(status: int) -> None:
    """A clean keeps the map refreshing on every poll, however long it runs."""
    vacuum = make_vacuum(B108GL)

    assert all(poll(vacuum, status, OFF_UPDATES + 10))
    vacuum._miot_device.get_property_by.assert_called_with(2, 1)


@pytest.mark.parametrize(
    "status", [IDLE, CHARGING, BREAK_CHARGING, PAUSED, CHARGED, UPDATING]
)
def test_b108gl_stops_updating_once_idle(status: int) -> None:
    """Idle, the map refreshes a few more times and then stops."""
    vacuum = make_vacuum(B108GL)

    assert poll(vacuum, status, OFF_UPDATES + 2) == [True] * OFF_UPDATES + [
        False,
        False,
    ]


def test_b108gl_starts_updating_again_when_a_clean_starts() -> None:
    """Moving again resets the idle count."""
    vacuum = make_vacuum(B108GL)
    poll(vacuum, CHARGED, OFF_UPDATES + 2)

    assert poll(vacuum, SWEEPING, 1) == [True]


def test_other_models_keep_the_parser_mapping() -> None:
    """Models without an override keep vacuum_map_parser_xiaomi's idle states."""
    vacuum = make_vacuum("xiaomi.vacuum.c102")

    assert poll(vacuum, 4, OFF_UPDATES + 1)[-1] is False


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


def parse(vacuum: XiaomiCloudVacuum, payload: dict[str, Any]):
    """Run decode_and_parse on a map that decrypts to `payload`."""
    vacuum._xiaomi_map_data_parser.unpack_map = MagicMock(
        return_value=json.dumps(payload)
    )
    return vacuum.decode_and_parse(b"encrypted map")


def test_b108gl_draws_the_robot_at_property_7_4() -> None:
    """Cleaning, the robot is drawn where property 7-4 puts it."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): SWEEPING, (7, 4): '{"x": 600, "y": 400, "yaw": 300}'})
    assert vacuum.should_update_map

    map_data = parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (600, 400)
    # 300 is 3 degrees in hundredths, converted once, by the parser.
    assert map_data.vacuum_position.a == pytest.approx(3.0)


def test_b108gl_draws_the_robot_on_its_dock_while_docked() -> None:
    """Charged on the dock, the robot is drawn there, not at a stale position."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): CHARGED, (7, 4): '{"x": 600, "y": 400, "yaw": 0}'})
    assert vacuum.should_update_map

    map_data = parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


def test_b108gl_draws_the_robot_on_its_dock_when_7_4_is_unknown() -> None:
    """With no position to report, the robot is drawn on the dock."""
    vacuum = make_vacuum(B108GL)
    stub_device(vacuum, {(2, 1): SWEEPING, (7, 4): "1100,1100,0"})
    assert vacuum.should_update_map

    map_data = parse(vacuum, json_map())

    assert (map_data.vacuum_position.x, map_data.vacuum_position.y) == (150, 250)


def test_other_models_parse_the_map_as_it_comes() -> None:
    """Models with no live properties never read 7-4."""
    vacuum = make_vacuum("xiaomi.vacuum.c102")
    stub_device(vacuum, {(7, 4): '{"x": 600, "y": 400}'})

    map_data = parse(vacuum, json_map())

    assert map_data.vacuum_position is None
    vacuum._miot_device.get_property_by.assert_not_called()
