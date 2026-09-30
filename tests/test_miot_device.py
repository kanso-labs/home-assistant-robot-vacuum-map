"""The connectors' MIoT devices, which read properties by service and property ID."""

import logging
from typing import Any
from unittest.mock import ANY, MagicMock

import pytest
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes

from custom_components.xiaomi_vacuum_map.connector.vacuums.base.model import (
    VacuumConfig,
)
from custom_components.xiaomi_vacuum_map.connector.vacuums.vacuum_ijai import (
    IjaiCloudVacuum,
)
from custom_components.xiaomi_vacuum_map.connector.vacuums.vacuum_xiaomi import (
    XiaomiCloudVacuum,
)
from custom_components.xiaomi_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudDeviceInfo,
)

CONNECTORS = pytest.mark.parametrize(
    ("connector", "model"),
    [
        (XiaomiCloudVacuum, "xiaomi.vacuum.b108gl"),
        (IjaiCloudVacuum, "ijai.vacuum.v19"),
    ],
    ids=["xiaomi", "ijai"],
)


def make_vacuum(connector: type, model: str):
    """A connector for one vacuum, with no cloud or device behind it."""
    device_info = XiaomiCloudDeviceInfo(
        device_id="123456789",
        name="Vacuum",
        model=model,
        token="0" * 32,
        spec_type="urn:miot-spec-v2:device:vacuum:0000A006",
        local_ip="192.0.2.10",
        mac="aa:bb:cc:dd:ee:ff",
        server="de",
        home_id=1,
        user_id=1,
    )
    return connector(
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


@CONNECTORS
def test_builds_its_device_without_a_mapping_warning(
    connector: type, model: str, caplog: pytest.LogCaptureFixture
) -> None:
    """python-miio warns about a device built with no mapping, at every start."""
    with caplog.at_level(logging.WARNING, logger="miio.miot_device"):
        make_vacuum(connector, model)

    assert [r.message for r in caplog.records if r.name == "miio.miot_device"] == []


@CONNECTORS
def test_still_reads_the_status_by_id(connector: type, model: str) -> None:
    """The empty mapping leaves reading a property by its IDs as it was."""
    vacuum = make_vacuum(connector, model)

    def send(command: str, parameters: Any = None) -> Any:
        # python-miio asks the device for its model before the first command.
        if command == "miIO.info":
            return {"model": model}
        return [{"value": 1}]

    vacuum._miot_device.send = MagicMock(side_effect=send)

    assert vacuum.should_update_map
    vacuum._miot_device.send.assert_called_with(
        "get_properties", [{"did": ANY, "siid": ANY, "piid": ANY}]
    )
