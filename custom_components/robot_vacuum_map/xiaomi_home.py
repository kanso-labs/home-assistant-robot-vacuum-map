"""Xiaomi Home, Xiaomi's own integration, when it has the same vacuum.

This integration reaches Xiaomi Home only through Home Assistant's registries
and states. It imports none of Xiaomi Home's code and calls none of its APIs,
which Xiaomi Home's license reserves for Xiaomi Home itself.
"""

from collections.abc import Callable
from typing import Any

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import MAX_LENGTH_STATE_STATE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import slugify

XIAOMI_HOME_DOMAIN = "xiaomi_home"


def xiaomi_home_device_id(
    hass: HomeAssistant, server: str, device_id: str
) -> str | None:
    """The id of Xiaomi Home's device for the vacuum, if Xiaomi Home has one.

    Xiaomi Home identifies a device by its cloud server and device id,
    slugified as "<server>_<device id>", both of which this integration keeps.
    It makes a config entry per Xiaomi account and server, and each entry that
    has the vacuum holds a device of its own for it, so the entries are
    searched in turn and the first device found is the one returned.
    """
    identifier = (XIAOMI_HOME_DOMAIN, slugify(f"{server}_{device_id}"))
    devices = dr.async_get(hass)
    for entry in hass.config_entries.async_entries(XIAOMI_HOME_DOMAIN):
        device = devices.async_get_device_by_identifier(identifier, entry.entry_id)
        if device is not None:
            return device.id
    return None


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
        return self._state(self._entry(siid, piid))

    def activity(self) -> str | None:
        """The state of Xiaomi Home's vacuum entity, or None."""
        return self._state(
            next((e for e in self._entries() if e.domain == VACUUM_DOMAIN), None)
        )

    @callback
    def async_watch(
        self,
        siid: int,
        piid: int,
        action: Callable[[Event[EventStateChangedData]], Any],
    ) -> CALLBACK_TYPE:
        """Call action each time the property's entity changes state.

        Returns what stops it. With no entity for the property, nothing is
        watched.
        """
        if (entry := self._entry(siid, piid)) is None:
            return lambda: None
        return async_track_state_change_event(self._hass, entry.entity_id, action)

    def _entry(self, siid: int, piid: int) -> er.RegistryEntry | None:
        suffix = f"_p_{siid}_{piid}"
        return next((e for e in self._entries() if e.unique_id.endswith(suffix)), None)

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
