"""The connectors' python-miio devices, and how the connectors read them."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes

from custom_components.robot_vacuum_map.connector.vacuums.base.model import (
    VacuumConfig,
)
from custom_components.robot_vacuum_map.connector.vacuums.vacuum_dreame import (
    DreameCloudVacuum,
)
from custom_components.robot_vacuum_map.connector.vacuums.vacuum_ijai import (
    IjaiCloudVacuum,
)
from custom_components.robot_vacuum_map.connector.vacuums.vacuum_roborock import (
    RoborockCloudVacuum,
)
from custom_components.robot_vacuum_map.connector.vacuums.vacuum_xiaomi import (
    XiaomiCloudVacuum,
)
from custom_components.robot_vacuum_map.connector.xiaomi_cloud.connector import (
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
async def test_still_reads_the_status_by_id(connector: type, model: str) -> None:
    """The empty mapping leaves reading a property by its IDs as it was."""
    vacuum = make_vacuum(connector, model)

    def send(command: str, parameters: Any = None) -> Any:
        # python-miio asks the device for its model before the first command.
        if command == "miIO.info":
            return {"model": model}
        return [{"value": 1}]

    vacuum._miot_device.send = MagicMock(side_effect=send)

    assert await vacuum.should_update_map()
    vacuum._miot_device.send.assert_called_with(
        "get_properties", [{"did": ANY, "siid": ANY, "piid": ANY}]
    )


def on_event_loop() -> bool:
    """Whether the caller runs on the event loop, as the executor's threads do not."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


class Device:
    """A python-miio device that notes, for each call, whether it ran on the loop."""

    def __init__(self, **answers: Callable[..., Any]) -> None:
        self.calls: list[tuple[str, bool]] = []
        for name, answer in answers.items():
            setattr(self, name, self._noting(name, answer))

    def _noting(self, name: str, answer: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any) -> Any:
            self.calls.append((name, on_event_loop()))
            return answer(*args)

        return call


# Uppercase and 18 characters long, as an iJai vacuum's serial number is.
SERIAL_NUMBER = "ABCDEFGHIJKLMNOPQR"


@pytest.mark.parametrize(
    ("connector", "model", "device", "answers", "calls"),
    [
        (
            XiaomiCloudVacuum,
            "xiaomi.vacuum.b108gl",
            "_miot_device",
            {"get_property_by": lambda siid, piid: [{"value": None}]},
            # The status, 7-2's trajectory, 2-11's areas, 2-12's walls, 7-4's
            # position and 7-1's map name.
            ["get_property_by"] * 6,
        ),
        (
            IjaiCloudVacuum,
            "ijai.vacuum.v19",
            "_miot_device",
            {"get_property_by": lambda siid, piid: [{"value": SERIAL_NUMBER}]},
            # The status, and the serial number the map is decrypted with.
            ["get_property_by"] * 2,
        ),
        (
            RoborockCloudVacuum,
            "roborock.vacuum.s5",
            "_vacuum",
            {"status": lambda: MagicMock(state_code=5), "map": lambda: ["map"]},
            ["status", "map"],
        ),
        (
            DreameCloudVacuum,
            "dreame.vacuum.mc1808",
            "_dreame_vacuum",
            {"call_action": lambda name, params: None},
            ["call_action"],
        ),
    ],
    ids=["xiaomi", "ijai", "roborock", "dreame"],
)
async def test_reads_the_vacuum_off_the_event_loop(
    connector: type,
    model: str,
    device: str,
    answers: dict[str, Callable[..., Any]],
    calls: list[str],
) -> None:
    """python-miio blocks until the vacuum answers, so a refresh reads it elsewhere.

    On the event loop, a vacuum slow to answer would hold up all of Home
    Assistant for as long as python-miio waited and retried.
    """
    vacuum = make_vacuum(connector, model)
    setattr(vacuum, device, Device(**answers))
    vacuum.get_raw_map_data = AsyncMock(return_value=b"map")
    vacuum.map_data_parser.unpack_map = MagicMock(return_value="{}")
    vacuum.map_data_parser.parse = MagicMock()

    await vacuum.should_update_map()
    await vacuum.get_map()

    assert getattr(vacuum, device).calls == [(call, False) for call in calls]
