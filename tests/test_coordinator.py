"""The coordinator, which refreshes the map on a schedule and redraws it between."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.robot_vacuum_map.coordinator import (
    XiaomiCloudMapExtractorDataUpdateCoordinator,
)


@pytest.mark.parametrize("redrawn", [True, False])
async def test_redraws_without_putting_the_next_refresh_off(
    hass: HomeAssistant, redrawn: bool
) -> None:
    """The robot moves every couple of seconds, and the downloads keep their pace.

    A coordinator reschedules its refresh whenever it is handed new data, so a
    redraw that did would hold the downloads off for as long as the robot moved.
    """
    connector = MagicMock()
    connector.redraw.return_value = redrawn
    coordinator = XiaomiCloudMapExtractorDataUpdateCoordinator(hass, connector)
    listener = MagicMock()
    remove_listener = coordinator.async_add_listener(listener)

    with patch.object(coordinator, "_schedule_refresh") as schedule_refresh:
        coordinator.async_redraw(MagicMock())
    remove_listener()

    assert listener.called is redrawn
    schedule_refresh.assert_not_called()
