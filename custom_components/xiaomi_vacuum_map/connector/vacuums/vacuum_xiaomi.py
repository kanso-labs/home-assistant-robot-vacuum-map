import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Self

from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice
from PIL.Image import Transpose
from vacuum_map_parser_base.config.color import SupportedColor
from vacuum_map_parser_base.config.drawable import Drawable
from vacuum_map_parser_base.config.size import Size
from vacuum_map_parser_base.image_generator import ImageGenerator
from vacuum_map_parser_base.map_data import MapData, Path, Point
from vacuum_map_parser_xiaomi.aes_decryptor import gen_md5_key
from vacuum_map_parser_xiaomi.map_data_parser import XiaomiMapDataParser
from vacuum_map_parser_xiaomi.status_mapping import (
    XiaomiVacuumStatusMapping,
    get_status_mapping,
)

from ..utils.exceptions import FailedConnectionException
from .base.model import VacuumApi, VacuumConfig
from .base.vacuum_v2 import BaseXiaomiCloudVacuumV2
from .xiaomi_miot_enrichment import (
    cloud_object_name,
    decode_trajectory,
    mop_runs,
    parse_vacuum_position,
    place_vacuum,
    with_path,
    with_restricted_regions,
)

_LOGGER = logging.getLogger(__name__)
OFF_UPDATES = 3

# The transposes the image generator rotates a map by, for the rotations it
# does exactly, and the transposes that undo them.
_ROTATE = {
    90: Transpose.ROTATE_90,
    180: Transpose.ROTATE_180,
    270: Transpose.ROTATE_270,
}
_UNROTATE = {
    90: Transpose.ROTATE_270,
    180: Transpose.ROTATE_180,
    270: Transpose.ROTATE_90,
}


@dataclass
class XiaomiVacuumPropertyMapping:
    """Dataclass containing mapping for map property"""

    # vacuum map service id
    siid: int = 10

    # current map property id in vacuum map service
    piid: int = 1


@dataclass
class XiaomiVacuumLiveMapping:
    """Live map data a vacuum publishes as MIoT properties, not in its map"""

    # vacuum map service id
    siid: int

    # vacuum position property id in vacuum map service
    position_piid: int

    # trajectory object name property id in vacuum map service
    trajectory_piid: int

    # status values meaning the vacuum is on its dock
    docked_at: tuple[int, ...]

    # restricted sweep areas property, as service id and property id
    restricted_areas: tuple[int, int]

    # restricted walls property, as service id and property id
    restricted_walls: tuple[int, int]


_NON_STANDARD_MAP_PROP = [
    (
        [
            "xiaomi.vacuum.b108gl",
        ],
        XiaomiVacuumPropertyMapping(siid=7),
    ),
    (
        [
            "xiaomi.vacuum.b108gp",
            "xiaomi.vacuum.ov32gl",
            "xiaomi.vacuum.ov43gl",
            "xiaomi.vacuum.ov51",
            "xiaomi.vacuum.ov81",
        ],
        XiaomiVacuumPropertyMapping(siid=9),
    ),
    (
        [
            "xiaomi.vacuum.b106bk",
            "xiaomi.vacuum.b106tr",
            "xiaomi.vacuum.b112",
            "xiaomi.vacuum.b112bk",
            "xiaomi.vacuum.b112gl",
            "xiaomi.vacuum.b112tr",
            "xiaomi.vacuum.c101",
            "xiaomi.vacuum.c101eu",
            "xiaomi.vacuum.c102",
            "xiaomi.vacuum.c104",
            "xiaomi.vacuum.e101gl",
        ],
        XiaomiVacuumPropertyMapping(piid=2),
    ),
]

# Status mappings for models vacuum_map_parser_xiaomi gets wrong. Its generic
# idle_at, (0, 1, 2, 4, 8, 10), reads the b108gl's 4 as idle, but in the
# b108gl's MIoT spec 4 is Sweeping, so the map stopped refreshing a few polls
# into every clean. Idle here is Idle, Charging, BreakCharging, Paused, Charged
# and Updating, which leaves Sweeping (4), Go Charging (6), Remote (7) and
# Mapping (9) as moving.
_NON_STANDARD_STATUS_PROP = [
    (
        [
            "xiaomi.vacuum.b108gl",
        ],
        XiaomiVacuumStatusMapping(idle_at=(1, 2, 3, 5, 8, 10)),
    ),
]

# Vacuums whose cloud map leaves the robot, its path, and its restricted areas
# and walls out. The b108gl publishes its position as property 7-4, about every
# two seconds while it cleans, names its trajectory object as property 7-2, a
# new one every couple of seconds, publishes the no-go areas and virtual walls
# set in the Xiaomi app as 2-11 and 2-12, and is on its dock while Charging (2),
# BreakCharging (3) or Charged (8).
_LIVE_MAP_PROP = [
    (
        [
            "xiaomi.vacuum.b108gl",
        ],
        XiaomiVacuumLiveMapping(
            siid=7,
            position_piid=4,
            trajectory_piid=2,
            docked_at=(2, 3, 8),
            restricted_areas=(2, 11),
            restricted_walls=(2, 12),
        ),
    ),
]


class XiaomiCloudVacuum(BaseXiaomiCloudVacuumV2):
    def __init__(self, vacuum_config: VacuumConfig):
        super().__init__(vacuum_config)
        self._token = vacuum_config.token
        self._host = vacuum_config.host

        # Properties are read by service and property ID, which needs no mapping,
        # but python-miio warns at start-up unless the device is given one.
        self._miot_device = MiotDevice(self._host, self._token, timeout=2, mapping={})

        self._xiaomi_map_data_parser = XiaomiMapDataParser(
            vacuum_config.palette,
            vacuum_config.sizes,
            vacuum_config.drawables,
            vacuum_config.image_config,
            vacuum_config.texts,
        )

        self._status_mapping = next(
            (
                mapping
                for models, mapping in _NON_STANDARD_STATUS_PROP
                if self.model in models
            ),
            get_status_mapping(self.model),
        )
        self._off_counter = 0
        self._status_value = None
        self._trajectory: list[dict[str, Any]] = []
        # The last value read from each MIoT property, keyed siid-piid, and the
        # last trajectory object downloaded, both kept for diagnostics.
        self._property_values: dict[str, Any] = {}
        self._raw_trajectory: bytes | None = None

        self._vacuum_map = next(
            (
                mapping
                for models, mapping in _NON_STANDARD_MAP_PROP
                if self.model in models
            ),
            XiaomiVacuumPropertyMapping(),
        )
        self._live_map = next(
            (mapping for models, mapping in _LIVE_MAP_PROP if self.model in models),
            None,
        )

    @property
    def should_update_map(self: Self) -> bool:
        try:
            status_value = self._miot_device.get_property_by(
                self._status_mapping.siid, self._status_mapping.piid
            )[0]["value"]
            self._status_value = status_value
            self._remember(
                self._status_mapping.siid, self._status_mapping.piid, status_value
            )

            if status_value in self._status_mapping.idle_at:
                self._off_counter += 1
                _LOGGER.debug(
                    "Vacuum is not moving. Off counter: %d", self._off_counter
                )
                return self._off_counter <= OFF_UPDATES
            else:
                self._off_counter = 0
                return True
        except DeviceException as de:
            if "token" not in repr(de):
                return False
            raise FailedConnectionException(de)

    @staticmethod
    def vacuum_platform() -> VacuumApi:
        return VacuumApi.XIAOMI

    @property
    def map_archive_extension(self) -> str:
        return "zlib.enc"

    @property
    def map_data_parser(self) -> XiaomiMapDataParser:
        return self._xiaomi_map_data_parser

    async def get_map_name(self: Self) -> str:
        response = self._miot_device.get_property_by(
            self._vacuum_map.siid, self._vacuum_map.piid
        )[0].get("value")
        self._remember(self._vacuum_map.siid, self._vacuum_map.piid, response)

        if response is None:
            return await super().get_map_name()

        if isinstance(response, int):
            return str(response)
        else:
            map_name = None
            try:
                map_name = json.loads(response).get("obj_name", None)
            except json.JSONDecodeError:
                if isinstance(response, str) and "/" in response:
                    map_name = response
            if map_name is None:
                return await super().get_map_name()
            return map_name.split("/")[-1]

    async def get_map_url(self, map_name: str) -> str | None:
        return await self.get_fallback_map_url(map_name)

    async def get_map(self: Self) -> tuple[MapData, bytes]:
        if self._live_map is not None:
            self._trajectory = await self._get_trajectory()
        return await super().get_map()

    async def _get_trajectory(self: Self) -> list[dict[str, Any]]:
        """The path so far, from the trajectory object property 7-2 names."""
        self._raw_trajectory = None
        if self._status_value in self._live_map.docked_at:
            # Back on the dock, the trajectory is the last clean's.
            return []
        name = cloud_object_name(
            self._get_live_property(self._live_map.siid, self._live_map.trajectory_piid)
        )
        if name is None:
            return []
        raw_trajectory = await self.get_raw_map_data(name)
        if raw_trajectory is None:
            _LOGGER.debug("Failed to download trajectory %s", name)
            return []
        self._raw_trajectory = raw_trajectory
        return decode_trajectory(raw_trajectory)

    def decode_and_parse(self, raw_map: bytes) -> MapData:
        # Try parsing as JSON first (old format), otherwise use raw data directly (new format)
        try:
            raw_map = base64.decodebytes(json.loads(raw_map)["data"].encode("latin1"))
        except json.JSONDecodeError, KeyError, UnicodeDecodeError:
            # Data may not be JSON-wrapped
            pass

        raw_map = raw_map.hex()
        decoded_map = self.map_data_parser.unpack_map(
            raw_map,
            model=self.model.replace("xiaomi", "mi"),
            device_id=str(self._device_id),
        )
        if self._live_map is None:
            return self.map_data_parser.parse(decoded_map)
        map_data = self.map_data_parser.parse(self._with_live_data(decoded_map))
        self._draw_mop_runs(map_data)
        return map_data

    def _with_live_data(self: Self, decoded_map: str) -> Any:
        """Merge what the vacuum publishes outside its map into the map's payload."""
        try:
            payload = json.loads(decoded_map)
        except TypeError, json.JSONDecodeError:
            return decoded_map
        if not isinstance(payload, dict):
            return decoded_map

        payload = with_restricted_regions(
            with_path(payload, self._trajectory),
            self._get_live_property(*self._live_map.restricted_areas),
            self._get_live_property(*self._live_map.restricted_walls),
        )
        position = parse_vacuum_position(
            self._get_live_property(self._live_map.siid, self._live_map.position_piid)
        )
        return place_vacuum(
            payload,
            position,
            docked=self._status_value in self._live_map.docked_at,
            path=self._trajectory,
        )

    def _draw_mop_runs(self: Self, map_data: MapData) -> None:
        """Draw each mop run as a line of its own.

        The parser joins every mopped point into one line, so the payload
        reaches it without them and they are drawn here instead, after the
        parser has drawn and rotated the image. For a quarter turn the rotation
        is undone first, which a transpose does exactly, so the runs land on
        the same pixels as the path, and then redone. Point.rotated() would put
        them a pixel off, because it maps x to w - x where a transpose maps it
        to w - 1 - x. Any other angle the parser rotates by resampling, which
        no transpose undoes, so there the points are rotated instead.
        """
        runs = mop_runs(self._trajectory)
        if not runs:
            return
        map_data.mop_path = Path(sum(len(run) for run in runs), 1, 0, runs)
        image = map_data.image
        if Drawable.MOP_PATH not in self._drawables or image is None or image.is_empty:
            return

        width = int(self._sizes.get_size(Size.MOP_PATH_WIDTH))
        color = self._palette.get_color(SupportedColor.MOP_PATH)
        rotation = image.dimensions.rotation

        def to_image(point: Point) -> Point:
            point = point.to_img(image.dimensions)
            if rotation and rotation not in _UNROTATE:
                point = point.rotated(image.dimensions)
            return point

        def draw_runs(draw) -> None:
            for run in runs:
                start = to_image(run[0])
                for point in run[1:]:
                    end = to_image(point)
                    draw.line([start.x, start.y, end.x, end.y], width=width, fill=color)
                    if width > 4:
                        radius = width / 2
                        corners = (
                            (end.x - radius, end.y - radius),
                            (
                                end.x + radius,
                                end.y + radius,
                            ),
                        )
                        draw.pieslice(corners, 0, 360, outline=color, fill=color)
                    start = end

        if rotation in _UNROTATE:
            image.data = image.data.transpose(_UNROTATE[rotation])
        ImageGenerator._draw_on_new_layer(
            image, draw_runs, ImageGenerator._use_transparency(color)
        )
        if rotation in _ROTATE:
            image.data = image.data.transpose(_ROTATE[rotation])

    def _get_live_property(self: Self, siid: int, piid: int) -> Any:
        try:
            value = self._miot_device.get_property_by(siid, piid)[0].get("value")
        except DeviceException as de:
            _LOGGER.debug("Failed to read MIoT property %d-%d: %s", siid, piid, de)
            return None
        self._remember(siid, piid, value)
        return value

    def _remember(self: Self, siid: int, piid: int, value: Any) -> None:
        self._property_values[f"{siid}-{piid}"] = value

    def _redacted(self: Self, value: Any) -> Any:
        """A property value with the account and device IDs taken out.

        Object names carry both, as user ID/device ID/name, and diagnostics
        are made to be attached to public issues.
        """
        if not isinstance(value, str):
            return value
        for identifier in (self._user_id, self._device_id):
            if identifier:
                value = re.sub(
                    rf"\b{re.escape(str(identifier))}\b", "**REDACTED**", value
                )
        return value

    def additional_data(self: Self) -> dict[str, Any]:
        super_data = super().additional_data()
        enc_key = gen_md5_key(
            self.model.replace("xiaomi", "mi"),
            str(self._device_id),
        )

        return {
            **super_data,
            "enc_key": enc_key,
            "miot_properties": {
                key: self._redacted(value)
                for key, value in sorted(self._property_values.items())
            },
            "trajectory_raw": self._raw_trajectory
            and base64.b64encode(self._raw_trajectory).decode(),
        }
