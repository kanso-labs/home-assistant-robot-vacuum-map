"""Fixtures shared by every test."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.size import Sizes

from custom_components.xiaomi_cloud_map.config_flow import (
    XiaomiCloudMapExtractorFlowHandler,
)
from custom_components.xiaomi_cloud_map.connector.model import (
    XiaomiCloudMapExtractorData,
)
from custom_components.xiaomi_cloud_map.const import (
    CONF_COLORS,
    CONF_DRAWABLES,
    CONF_IMAGE_CONFIG,
    CONF_ROOM_COLORS,
    CONF_SERVER,
    CONF_SIZES,
    CONF_TEXTS,
    CONF_USED_MAP_API,
    DOMAIN,
)

MAC = "aa:bb:cc:dd:ee:ff"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components/."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry shaped the way the config flow creates one."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="S20+",
        unique_id=MAC,
        data={
            CONF_DEVICE_ID: "123456789",
            CONF_HOST: "192.0.2.10",
            CONF_MAC: MAC,
            CONF_MODEL: "xiaomi.vacuum.b108gl",
            CONF_NAME: "S20+",
            CONF_PASSWORD: "password",
            CONF_SERVER: "de",
            CONF_TOKEN: "0" * 32,
            CONF_USED_MAP_API: "XIAOMI",
            CONF_USERNAME: "user@example.com",
        },
        options={
            CONF_COLORS: XiaomiCloudMapExtractorFlowHandler._default_colors(),
            CONF_DRAWABLES: [drawable.value for drawable in Drawable],
            CONF_IMAGE_CONFIG: XiaomiCloudMapExtractorFlowHandler._default_image_config(),
            CONF_ROOM_COLORS: {},
            CONF_SIZES: {size.value: value for size, value in Sizes.SIZES.items()},
            CONF_TEXTS: [],
        },
    )


@pytest.fixture
def get_data() -> Generator[AsyncMock]:
    """Answer every poll with an empty map instead of calling Xiaomi's cloud."""
    with patch(
        "custom_components.xiaomi_cloud_map.connector.XiaomiCloudMapExtractorConnector.get_data",
        return_value=XiaomiCloudMapExtractorData(),
    ) as get_data:
        yield get_data
