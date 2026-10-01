"""The connector, which downloads a map while one is wanted and redraws it between."""

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
    connector._vacuum_connector = MagicMock()
    connector._map_cache.map_data = MagicMock(map_name="3")
    connector._map_cache.map_data_raw = b"map"
    connector._map_cache.map_image = b"image"
    return connector


def test_redraws_the_map_from_its_last_download() -> None:
    """The redrawn map keeps its name, and its image gets a new time."""
    connector = with_map()

    with patch(f"{MODULE}.to_image", return_value=b"moved"):
        assert connector.redraw()

    connector._vacuum_connector.redraw.assert_called_once_with(b"map")
    assert connector._map_cache.map_data.map_name == "3"
    assert connector._map_cache.map_image == b"moved"
    assert connector._map_cache.last_image_update_timestamp is not None


@pytest.mark.parametrize("reason", ["no map", "paused by the switch", "no change"])
def test_redraws_nothing_it_has_no_call_to(reason: str) -> None:
    connector = with_map()
    if reason == "no map":
        connector._map_cache.map_data_raw = None
    if reason == "paused by the switch":
        connector.set_auto_updating(False)
    if reason == "no change":
        connector._vacuum_connector.redraw.return_value = None

    assert not connector.redraw()
    assert connector._map_cache.map_image == b"image"


def test_dates_the_image_only_when_it_changes() -> None:
    """The image entity's state is this time, and the frontend refetches on it."""
    connector = with_map()
    with patch(f"{MODULE}.to_image", return_value=b"moved"):
        connector.redraw()
        drawn_at = connector._map_cache.last_image_update_timestamp

        connector.redraw()

    assert connector._map_cache.last_image_update_timestamp == drawn_at


def test_names_the_property_a_vacuum_reports_its_position_in() -> None:
    """Only the S20+'s is known, as 7-4."""

    def position_property(api: VacuumApi, model: str) -> tuple[int, int] | None:
        config = MagicMock(used_api=api, model=model)
        connector = XiaomiCloudMapExtractorConnector(MagicMock(), config, None)
        return connector.position_property()

    assert position_property(VacuumApi.XIAOMI, "xiaomi.vacuum.b108gl") == (7, 4)
    assert position_property(VacuumApi.XIAOMI, "xiaomi.vacuum.c102") is None
    assert position_property(VacuumApi.ROBOROCK, "roborock.vacuum.s5") is None
