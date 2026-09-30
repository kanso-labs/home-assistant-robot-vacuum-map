"""Xiaomi Home, Xiaomi's own integration, when it has the same vacuum.

This integration reaches Xiaomi Home only through Home Assistant's registries
and states. It imports none of Xiaomi Home's code and calls none of its APIs,
which Xiaomi Home's license reserves for Xiaomi Home itself.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

XIAOMI_HOME_DOMAIN = "xiaomi_home"


def xiaomi_home_device_id(
    hass: HomeAssistant, server: str, device_id: str
) -> str | None:
    """The id of Xiaomi Home's device for the vacuum, if Xiaomi Home has one.

    Xiaomi Home identifies a device by its cloud server and device id,
    slugified as "<server>_<device id>", both of which this integration keeps.
    """
    device = dr.async_get(hass).async_get_device(
        identifiers={(XIAOMI_HOME_DOMAIN, slugify(f"{server}_{device_id}"))}
    )
    return device.id if device is not None else None
