import logging
from typing import Self

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connector import XiaomiCloudMapExtractorConnector
from .connector.model import XiaomiCloudMapExtractorData
from .connector.utils.exceptions import (
    CaptchaRequiredException,
    DeviceNotFoundException,
    FailedLoginException,
    InvalidCredentialsException,
    InvalidDeviceTokenException,
    TwoFactorAuthRequiredException,
    XiaomiCloudMapExtractorException,
)
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class XiaomiCloudMapExtractorDataUpdateCoordinator(
    DataUpdateCoordinator[XiaomiCloudMapExtractorData]
):
    def __init__(
        self: Self,
        hass: HomeAssistant,
        connector: XiaomiCloudMapExtractorConnector,
    ) -> None:
        self.connector = connector
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=self.update_data,
        )

    async def update_data(self: Self) -> XiaomiCloudMapExtractorData:
        try:
            return await self.connector.get_data()
        except (
            FailedLoginException,
            InvalidCredentialsException,
            InvalidDeviceTokenException,
            TwoFactorAuthRequiredException,
            CaptchaRequiredException,
            DeviceNotFoundException,
        ) as err:
            _LOGGER.error(err)
            _LOGGER.debug("Triggering reauth flow...")
            raise ConfigEntryAuthFailed(err) from err
        except XiaomiCloudMapExtractorException as err:
            _LOGGER.error(err)
            raise UpdateFailed(err) from err

    @callback
    def async_redraw(self: Self, _: Event[EventStateChangedData]) -> None:
        """Draw the map again from its last download, for a robot that moved.

        The entities are told directly. async_set_updated_data would put the
        next refresh off each time, and the downloads would stop while the
        robot kept moving.
        """
        if self.connector.redraw():
            self.async_update_listeners()

    async def force_update_data(self) -> None:
        self.connector.force_refresh()
        await self.async_request_refresh()

    async def set_auto_updating(self, updating: bool) -> None:
        self.connector.set_auto_updating(updating)

    def is_auto_updating(self) -> bool:
        return self.connector.is_auto_updating()
