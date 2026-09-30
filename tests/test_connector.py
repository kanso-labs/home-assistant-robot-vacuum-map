"""The connector's refresh, which downloads a map only while one is wanted."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.robot_vacuum_map.connector import (
    XiaomiCloudMapExtractorConnector,
)


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
