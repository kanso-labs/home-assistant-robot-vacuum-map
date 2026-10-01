"""Setting the integration up and tearing it down."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.robot_vacuum_map.connector import (
    XiaomiCloudMapExtractorConnector,
)
from custom_components.robot_vacuum_map.const import DOMAIN
from custom_components.robot_vacuum_map.xiaomi_home import (
    XIAOMI_HOME_DOMAIN,
    XiaomiHomeProperties,
)


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, get_data: AsyncMock
) -> None:
    """The integration sets up under robot_vacuum_map and unloads cleanly."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    get_data.assert_awaited()

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "123456789"), config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id is None
    assert (
        config_entry.runtime_data.coordinator.connector._config.live_properties is None
    )
    entities = er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    )
    assert {entity.platform for entity in entities} == {DOMAIN}
    assert {entity.domain for entity in entities} >= {"camera", "image", "sensor"}

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_connects_the_map_via_xiaomi_home_s_vacuum(
    hass: HomeAssistant, config_entry: MockConfigEntry, get_data: AsyncMock
) -> None:
    """With Xiaomi Home holding the vacuum, the map's device names it as its via."""
    xiaomi_home = MockConfigEntry(domain=XIAOMI_HOME_DOMAIN)
    xiaomi_home.add_to_hass(hass)
    vacuum = dr.async_get(hass).async_get_or_create(
        config_entry_id=xiaomi_home.entry_id,
        identifiers={(XIAOMI_HOME_DOMAIN, "de_123456789")},
        name="S20+",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "123456789"), config_entry.entry_id
    )
    assert device.via_device_id == vacuum.id
    assert device.id != vacuum.id
    connector_config = config_entry.runtime_data.coordinator.connector._config
    assert isinstance(connector_config.live_properties, XiaomiHomeProperties)


async def test_redraws_the_map_each_time_xiaomi_home_moves_the_robot(
    hass: HomeAssistant, config_entry: MockConfigEntry, get_data: AsyncMock
) -> None:
    """Xiaomi Home's position sensor redraws the map, and nothing is downloaded."""
    xiaomi_home = MockConfigEntry(domain=XIAOMI_HOME_DOMAIN)
    xiaomi_home.add_to_hass(hass)
    vacuum = dr.async_get(hass).async_get_or_create(
        config_entry_id=xiaomi_home.entry_id,
        identifiers={(XIAOMI_HOME_DOMAIN, "de_123456789")},
    )
    position = er.async_get(hass).async_get_or_create(
        "sensor",
        XIAOMI_HOME_DOMAIN,
        "xiaomi_home.xiaomi_de_123456789_b108gl_vacuum_position_p_7_4",
        config_entry=xiaomi_home,
        device_id=vacuum.id,
    )
    hass.states.async_set(position.entity_id, '{"position":[0,0,0]}')
    config_entry.add_to_hass(hass)

    with patch.object(
        XiaomiCloudMapExtractorConnector, "redraw", return_value=True
    ) as redraw:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        get_data.reset_mock()

        hass.states.async_set(position.entity_id, '{"position":[400,0,0]}')
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        hass.states.async_set(position.entity_id, '{"position":[800,0,0]}')
        await hass.async_block_till_done()

    redraw.assert_called_once()
    get_data.assert_not_awaited()
