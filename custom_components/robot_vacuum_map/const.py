from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

NAME: Final = "Robot Vacuum Map"

DOMAIN: Final = "robot_vacuum_map"

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]

CONTENT_TYPE: Final = "image/png"
DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=10)

# How much larger than the cloud map's grid a new entry draws the map, with the
# elements' sizes multiplied to match, so each keeps its size against the map.
# At 4 the S20+'s 144 x 245 grid comes out 576 x 980.
DEFAULT_IMAGE_SCALE: Final = 4

CONF_USED_MAP_API: Final = "used_map_api"
CONF_SERVER: Final = "server"

CONF_CAPTCHA_CODE: Final = "captcha_code"
CONF_TWO_FACTOR_CODE: Final = "two_factor_code"

CONF_IMAGE_CONFIG: Final = "image_config"
CONF_IMAGE_CONFIG_SCALE: Final = "scale"
CONF_IMAGE_CONFIG_ROTATE: Final = "rotate"
CONF_IMAGE_CONFIG_TRIM_LEFT: Final = "trim_left"
CONF_IMAGE_CONFIG_TRIM_RIGHT: Final = "trim_right"
CONF_IMAGE_CONFIG_TRIM_TOP: Final = "trim_top"
CONF_IMAGE_CONFIG_TRIM_BOTTOM: Final = "trim_bottom"

CONF_COLORS: Final = "colors"

CONF_ROOM_COLORS = "room_colors"

CONF_DRAWABLES: Final = "drawables"

CONF_SIZES: Final = "sizes"

CONF_TEXTS: Final = "texts"
CONF_TEXT_VALUE: Final = "text"
CONF_TEXT_X: Final = "x"
CONF_TEXT_Y: Final = "y"
CONF_TEXT_COLOR: Final = "color"
CONF_TEXT_FONT: Final = "font"
CONF_TEXT_FONT_SIZE: Final = "font_size"

STORAGE_VERSION: Final = 1
