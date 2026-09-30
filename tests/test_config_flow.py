"""The options a new entry starts with."""

from vacuum_map_parser_base.config.size import Size, Sizes

from custom_components.xiaomi_vacuum_map.config_flow import (
    XiaomiCloudMapExtractorFlowHandler,
)
from custom_components.xiaomi_vacuum_map.const import CONF_IMAGE_CONFIG_SCALE


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
