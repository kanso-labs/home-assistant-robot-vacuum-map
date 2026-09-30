from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import XiaomiCloudMapExtractorDataUpdateCoordinator


@dataclass
class XiaomiCloudMapExtractorRuntimeData:
    coordinator: XiaomiCloudMapExtractorDataUpdateCoordinator
    # Xiaomi Home's device for the same vacuum, which the map's device is
    # connected via, when Xiaomi Home has one.
    via_device_id: str | None = None


type XiaomiCloudMapExtractorConfigEntry = ConfigEntry[
    XiaomiCloudMapExtractorRuntimeData
]
