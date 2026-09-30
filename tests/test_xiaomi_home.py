"""Reading a vacuum's live properties from Xiaomi Home's entities."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.robot_vacuum_map.xiaomi_home import (
    XIAOMI_HOME_DOMAIN,
    XiaomiHomeProperties,
)

# Unique ids as Xiaomi Home made them on a real S20+, with its device id.
PREFIX = "xiaomi_home.xiaomi_us_123456789_b108gl"


@pytest.fixture
def xiaomi_home(hass: HomeAssistant) -> XiaomiHomeProperties:
    """Xiaomi Home's S20+, with its vacuum, position sensor and walls text."""
    entry = MockConfigEntry(domain=XIAOMI_HOME_DOMAIN)
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(XIAOMI_HOME_DOMAIN, "us_123456789")},
    )
    entities = er.async_get(hass)
    for domain, unique_id, state in (
        ("vacuum", PREFIX, "cleaning"),
        ("sensor", f"{PREFIX}_vacuum_position_p_7_4", '{"position":[225,-42,1739]}'),
        ("text", f"{PREFIX}_restricted_walls_p_2_12", '{"restricted_walls":[]}'),
        ("sensor", f"{PREFIX}_map_obj_name_p_7_1", "unavailable"),
    ):
        entity = entities.async_get_or_create(
            domain,
            XIAOMI_HOME_DOMAIN,
            unique_id,
            config_entry=entry,
            device_id=device.id,
        )
        hass.states.async_set(entity.entity_id, state)
    return XiaomiHomeProperties(hass, device.id)


async def test_reads_a_property_from_its_entity(
    xiaomi_home: XiaomiHomeProperties,
) -> None:
    assert xiaomi_home.value(7, 4) == '{"position":[225,-42,1739]}'
    assert xiaomi_home.value(2, 12) == '{"restricted_walls":[]}'


async def test_reads_the_activity_from_the_vacuum_entity(
    xiaomi_home: XiaomiHomeProperties,
) -> None:
    assert xiaomi_home.activity() == "cleaning"


async def test_leaves_the_vacuum_to_answer_what_xiaomi_home_cannot(
    hass: HomeAssistant, xiaomi_home: XiaomiHomeProperties
) -> None:
    """No entity, an unavailable state, or a state cut at 255 characters."""
    assert xiaomi_home.value(2, 11) is None
    assert xiaomi_home.value(7, 1) is None
    walls = er.async_get(hass).async_get_entity_id(
        "text", XIAOMI_HOME_DOMAIN, f"{PREFIX}_restricted_walls_p_2_12"
    )
    hass.states.async_set(walls, "x" * 255)
    assert xiaomi_home.value(2, 12) is None
