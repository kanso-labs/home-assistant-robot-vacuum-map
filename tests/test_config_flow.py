"""The options a new entry starts with, and how the flow updates an entry."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vacuum_map_parser_base.config.size import Size, Sizes

from custom_components.robot_vacuum_map.config_flow import (
    XiaomiCloudMapExtractorFlowHandler,
)
from custom_components.robot_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudDeviceInfo,
)
from custom_components.robot_vacuum_map.const import (
    CONF_IMAGE_CONFIG_SCALE,
    CONF_USED_MAP_API,
    DOMAIN,
)


def test_draws_a_new_entry_four_times_the_size_of_the_grid() -> None:
    """At scale 1 the S20+'s map came out 144 x 245, too small for a card."""
    image_config = XiaomiCloudMapExtractorFlowHandler._default_image_config()

    assert image_config[CONF_IMAGE_CONFIG_SCALE] == 4


def test_multiplies_a_new_entry_s_sizes_to_match() -> None:
    """Sizes are in pixels, so they grow with the scale to keep their size."""
    sizes = XiaomiCloudMapExtractorFlowHandler._default_sizes()

    assert sizes == {size.value: value * 4 for size, value in Sizes.SIZES.items()}
    assert sizes[Size.PATH_WIDTH.value] == 4
    assert sizes[Size.VACUUM_RADIUS.value] == 24


async def test_reauthentication_updates_its_entry_after_the_host_changed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The vacuum moved to a new address, so no entry has the host typed in."""
    config_entry.add_to_hass(hass)
    flow = XiaomiCloudMapExtractorFlowHandler()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "reauth"
    flow.context = {"source": SOURCE_REAUTH, "entry_id": config_entry.entry_id}
    flow._connector = MagicMock()
    flow._username = "user@example.com"
    flow._password = "password"
    flow._cloud_vacuum = XiaomiCloudDeviceInfo(
        device_id="123456789",
        name="S20+",
        model="xiaomi.vacuum.b108gl",
        token="1" * 32,
        spec_type="urn:miot-spec-v2:device:vacuum:0000A006",
        local_ip="192.0.2.20",
        mac="aa:bb:cc:dd:ee:ff",
        server="de",
        home_id=1,
        user_id=1,
    )

    with patch(
        "custom_components.robot_vacuum_map.config_flow.save_connector_config",
        new=AsyncMock(),
    ):
        result = await flow.async_step_confirm_data(
            {
                CONF_HOST: "192.0.2.20",
                CONF_TOKEN: "1" * 32,
                CONF_USED_MAP_API: "XIAOMI",
            }
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == "192.0.2.20"
    assert config_entry.data[CONF_TOKEN] == "1" * 32
    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
