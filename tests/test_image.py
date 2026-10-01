"""The map's image entity."""

from datetime import datetime
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.robot_vacuum_map.connector.model import (
    XiaomiCloudMapExtractorData,
)


async def test_dates_the_image_by_when_it_was_last_drawn(
    hass: HomeAssistant, config_entry: MockConfigEntry, get_data: AsyncMock
) -> None:
    """The frontend fetches the image again only when this state moves.

    A redraw moves the robot without a new map, so the state follows the image.
    """
    get_data.return_value = XiaomiCloudMapExtractorData(
        last_real_update_timestamp=datetime.fromisoformat("2026-09-30T11:00:00"),
        last_image_update_timestamp=datetime.fromisoformat("2026-09-30T11:00:02"),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    image = next(
        entry
        for entry in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
        if entry.domain == "image"
    )
    assert hass.states.get(image.entity_id).state == "2026-09-30T11:00:02"
