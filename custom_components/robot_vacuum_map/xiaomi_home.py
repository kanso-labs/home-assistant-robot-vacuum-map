"""Xiaomi Home, Xiaomi's own integration, when it has the same vacuum.

This integration reaches Xiaomi Home only through Home Assistant's registries
and states. It imports none of Xiaomi Home's code and calls none of its APIs,
which Xiaomi Home's license reserves for Xiaomi Home itself.
"""

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import MAX_LENGTH_STATE_STATE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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


class XiaomiHomeProperties:
    """A vacuum's live MIoT properties, read from Xiaomi Home's entities for it.

    Xiaomi Home makes an entity for each property, whose unique id ends
    "_p_<siid>_<piid>", and folds the vacuum's status into its vacuum entity,
    whose state is the activity.
    """

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        self._hass = hass
        self._device_id = device_id

    def value(self, siid: int, piid: int) -> str | None:
        """The state of Xiaomi Home's entity for the property, or None."""
        suffix = f"_p_{siid}_{piid}"
        return self._state(
            next((e for e in self._entries() if e.unique_id.endswith(suffix)), None)
        )

    def activity(self) -> str | None:
        """The state of Xiaomi Home's vacuum entity, or None."""
        return self._state(
            next((e for e in self._entries() if e.domain == VACUUM_DOMAIN), None)
        )

    def _entries(self) -> list[er.RegistryEntry]:
        return [
            entry
            for entry in er.async_entries_for_device(
                er.async_get(self._hass), self._device_id
            )
            if entry.platform == XIAOMI_HOME_DOMAIN
        ]

    def _state(self, entry: er.RegistryEntry | None) -> str | None:
        """An entity's state, or None when it cannot stand for the property.

        That is when there is no entity, its state is unknown or unavailable,
        or the state fills all 255 characters Home Assistant keeps of one, so
        Xiaomi Home may have cut it short.
        """
        if entry is None or (state := self._hass.states.get(entry.entity_id)) is None:
            return None
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        if len(state.state) >= MAX_LENGTH_STATE_STATE:
            return None
        return state.state
