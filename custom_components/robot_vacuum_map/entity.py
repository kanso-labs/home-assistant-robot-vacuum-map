from typing import Any, Self

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
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from vacuum_map_parser_base.map_data import MapData

from .connector.model import XiaomiCloudMapExtractorData
from .connector.vacuums.base.model import VacuumApi
from .const import CONF_SERVER, CONF_USED_MAP_API, DOMAIN
from .coordinator import XiaomiCloudMapExtractorDataUpdateCoordinator
from .types import XiaomiCloudMapExtractorConfigEntry


class XiaomiCloudMapExtractorEntity(
    CoordinatorEntity[XiaomiCloudMapExtractorDataUpdateCoordinator]
):
    _attr_has_entity_name = True
    _entity_component_unrecorded_attributes = frozenset(
        {"path", "zones", "walls", "obstacles", "areas", "calibration_points", "rooms"}
    )
    _host: str
    _token: str
    _mac: str
    _username: str
    _password: str
    _model: str
    _device_id: str
    _server: str
    _used_map_api: VacuumApi
    _attr_device_info: DeviceInfo

    def __init__(
        self: Self,
        coordinator: XiaomiCloudMapExtractorDataUpdateCoordinator,
        config_entry: XiaomiCloudMapExtractorConfigEntry,
        domain: str,
        key: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._host = config_entry.data[CONF_HOST]
        self._token = config_entry.data[CONF_TOKEN]
        self._mac = config_entry.data[CONF_MAC]
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._model = config_entry.data[CONF_MODEL]
        self._name = config_entry.data[CONF_NAME]
        self._device_id = config_entry.data[CONF_DEVICE_ID]
        self._server = config_entry.data[CONF_SERVER]
        self._used_map_api = VacuumApi(config_entry.data[CONF_USED_MAP_API])
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=self._used_map_api.title(),
            name=self._name,
            model=self._model,
        )
        # Since Home Assistant 2026.8 a device belongs to one integration, so the
        # map cannot share Xiaomi Home's device; it is connected via it instead.
        if (via_device_id := config_entry.runtime_data.via_device_id) is not None:
            self._attr_device_info["via_device_id"] = via_device_id
        self._attr_unique_id = f"{self._device_id}_{domain}_{key}"

    def _data(self: Self) -> XiaomiCloudMapExtractorData | None:
        return self.coordinator.data

    def _map_data(self: Self) -> MapData | None:
        if (data := self._data()) is None:
            return None
        return data.map_data

    @property
    def extra_state_attributes(self: Self) -> dict[str, Any]:
        if (data := self._data()) is None:
            return {}
        attributes = {}
        if data.last_update_timestamp:
            attributes["last_update_timestamp"] = data.last_update_timestamp
        if data.last_successful_update_timestamp:
            attributes["last_successful_update_timestamp"] = (
                data.last_successful_update_timestamp
            )
        return attributes
