"""The connector, which downloads a map while one is wanted and redraws it between."""

import asyncio
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.robot_vacuum_map.connector import (
    XiaomiCloudMapExtractorConnector,
)
from custom_components.robot_vacuum_map.connector.vacuums.base.model import VacuumApi

MODULE = "custom_components.robot_vacuum_map.connector"


@pytest.mark.parametrize(
    ("should_update", "auto_update", "downloads"),
    [(True, True, 1), (False, True, 0), (True, False, 0)],
    ids=["moving", "idle", "paused by the switch"],
)
async def test_downloads_the_map_only_while_one_is_wanted(
    should_update: bool, auto_update: bool, downloads: int
) -> None:
    """The vacuum's answer, which it reads off the event loop, is awaited."""
    connector = XiaomiCloudMapExtractorConnector(MagicMock(), MagicMock(), None)
    connector._vacuum_connector = MagicMock(
        should_update_map=AsyncMock(return_value=should_update)
    )
    connector.set_auto_updating(auto_update)
    connector._get_map = AsyncMock()

    await connector.get_data()

    assert connector._get_map.await_count == downloads


def with_map() -> XiaomiCloudMapExtractorConnector:
    """A connector holding a downloaded map, and a vacuum that redraws it."""
    connector = XiaomiCloudMapExtractorConnector(MagicMock(), MagicMock(), None)
    connector._vacuum_connector = MagicMock(redraw=AsyncMock())
    connector._map_cache.map_data = MagicMock(map_name="3")
    connector._map_cache.map_data_raw = b"map"
    connector._map_cache.map_image = b"image"
    return connector


async def test_redraws_the_map_from_its_last_download() -> None:
    """The redrawn map keeps its name, and its image gets a new time."""
    connector = with_map()

    with patch(f"{MODULE}.to_image", return_value=b"moved"):
        assert await connector.redraw()

    connector._vacuum_connector.redraw.assert_awaited_once_with(b"map")
    assert connector._map_cache.map_data.map_name == "3"
    assert connector._map_cache.map_image == b"moved"
    assert connector._map_cache.last_image_update_timestamp is not None


@pytest.mark.parametrize("reason", ["no map", "paused by the switch", "no change"])
async def test_redraws_nothing_it_has_no_call_to(reason: str) -> None:
    connector = with_map()
    if reason == "no map":
        connector._map_cache.map_data_raw = None
    if reason == "paused by the switch":
        connector.set_auto_updating(False)
    if reason == "no change":
        connector._vacuum_connector.redraw.return_value = None

    assert not await connector.redraw()
    assert connector._map_cache.map_image == b"image"


async def test_dates_the_image_only_when_it_changes() -> None:
    """The image entity's state is this time, and the frontend refetches on it."""
    connector = with_map()
    with patch(f"{MODULE}.to_image", return_value=b"moved"):
        await connector.redraw()
        drawn_at = connector._map_cache.last_image_update_timestamp

        await connector.redraw()

    assert connector._map_cache.last_image_update_timestamp == drawn_at


async def test_encodes_the_image_off_the_event_loop() -> None:
    """Encoding a large map takes long enough to hold up Home Assistant."""
    connector = with_map()
    threads: list[threading.Thread] = []

    def to_image(map_data: Any) -> bytes:
        threads.append(threading.current_thread())
        return b"moved"

    with patch(f"{MODULE}.to_image", side_effect=to_image):
        assert await connector.redraw()

    assert threads
    assert threading.main_thread() not in threads


async def test_redraws_only_once_the_download_in_progress_is_drawn() -> None:
    """Both draw from the vacuum's state in the executor, so neither overlaps."""
    connector = with_map()
    connector._is_authenticated = MagicMock(return_value=True)
    connector._cloud_connector = MagicMock()
    connector._status = MagicMock()
    downloading = asyncio.Event()
    finish_download = asyncio.Event()
    order: list[str] = []

    async def get_map() -> tuple[Any, bytes]:
        downloading.set()
        await finish_download.wait()
        order.append("downloaded")
        return MagicMock(map_name="3"), b"new map"

    async def redraw(raw_map: bytes) -> Any:
        order.append(f"redrew {raw_map.decode()}")
        return MagicMock()

    connector._vacuum_connector.get_map = get_map
    connector._vacuum_connector.redraw = redraw

    with patch(f"{MODULE}.to_image", return_value=b"image"):
        update = asyncio.create_task(connector._update())
        await downloading.wait()
        redrawing = asyncio.create_task(connector.redraw())
        await asyncio.sleep(0)
        finish_download.set()
        await update
        assert await redrawing

    assert order == ["downloaded", "redrew new map"]


def test_names_the_property_a_vacuum_reports_its_position_in() -> None:
    """Only the S20+'s is known, as 7-4."""

    def position_property(api: VacuumApi, model: str) -> tuple[int, int] | None:
        config = MagicMock(used_api=api, model=model)
        connector = XiaomiCloudMapExtractorConnector(MagicMock(), config, None)
        return connector.position_property()

    assert position_property(VacuumApi.XIAOMI, "xiaomi.vacuum.b108gl") == (7, 4)
    assert position_property(VacuumApi.XIAOMI, "xiaomi.vacuum.c102") is None
    assert position_property(VacuumApi.ROBOROCK, "roborock.vacuum.s5") is None
