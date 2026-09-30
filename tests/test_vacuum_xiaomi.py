"""The Xiaomi connector, against the Xiaomi Robot Vacuum S20+ (b108gl)."""

from unittest.mock import MagicMock

import pytest
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes

from custom_components.xiaomi_cloud_map.connector.vacuums.base.model import (
    VacuumConfig,
)
from custom_components.xiaomi_cloud_map.connector.vacuums.vacuum_xiaomi import (
    OFF_UPDATES,
    XiaomiCloudVacuum,
)
from custom_components.xiaomi_cloud_map.connector.xiaomi_cloud.connector import (
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
