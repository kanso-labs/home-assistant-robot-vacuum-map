"""Live map data a Xiaomi vacuum publishes as MIoT properties, not in its map.

The Xiaomi Robot Vacuum S20+ (xiaomi.vacuum.b108gl) keeps its rooms, its dock
and its calibration in the cloud map, but not the robot, its path, or the
restricted areas and walls set in the Xiaomi app: it publishes its position as
MIoT property 7-4, names a trajectory object in the cloud as property 7-2, and
publishes the areas and walls as properties 2-11 and 2-12. The functions here
merge those into the map's JSON payload, in the shape vacuum_map_parser_xiaomi
reads, before the parser draws it.

Ported from xiaomi_miot_enrichment.py in upstream pull request #750, by almirus.
"""

import base64
import json
import math
import struct
import zlib
from typing import Any

from vacuum_map_parser_base.map_data import Point

# The coordinate the b108gl reports while it does not know where it is.
POSITION_UNKNOWN = 1100

# A trajectory is a run of records, each a marker byte and then x and y as
# little-endian int32. The marker says whether the robot was mopping there.
TRAJECTORY_POINT = 0x02
TRAJECTORY_MOP_POINT = 0x03
_TRAJECTORY_RECORD = struct.Struct("<Bii")

# No map reaches this far, in millimetres, so a coordinate beyond it is a
# record read out of step rather than a place the robot went.
MAX_TRAJECTORY_COORDINATE = 1_000_000

# A mop run breaks where two of its points lie further apart than this, in
# millimetres, and a run shorter than MIN_MOP_RUN_POINTS is not drawn.
MAX_MOP_RUN_GAP = 500
MIN_MOP_RUN_POINTS = 3

# The keys an object may list restricted areas or walls under, and the keys a
# region may list its points under, as upstream pull request #750 reads them,
# with fb_point added, the key vacuum_map_parser_xiaomi 0.1.4 reads an area's
# corners from in the Dreame-based Xiaomi models' maps, and forbidden_regions,
# the key a real S20+ lists its areas under in 2-11.
_REGION_LIST_KEYS = (
    "areas",
    "forbidden_regions",
    "zones",
    "regions",
    "walls",
    "restricted_areas",
    "restricted_walls",
    "value",
)
_POINT_LIST_KEYS = (
    "points",
    "fb_point",
    "area_points",
    "region_points",
    "wall_points",
    "coordinates",
    "vertices",
)

# The fb_attr value marking an area as no-mop rather than no-go, as
# vacuum_map_parser_xiaomi 0.1.4 reads it, verified there on the ov81gl.
_FB_ATTR_NO_MOP = 1


def parse_vacuum_position(value: Any) -> dict[str, Any] | None:
    """Read a vacuum-position property into the map payload's position shape.

    A real S20+ publishes {"position": [x, y, yaw]}, with the yaw in
    milliradians. That yaw is handed on in radians: vacuum_map_parser_xiaomi
    reads a yaw within 2π as radians and converts it whole, where it reads
    larger values as hundredths of a degree and folds them into 0° to 180°.

    The property may also arrive as a JSON object of x and y, or as "x,y,yaw"
    text, the forms upstream pull request #750 reads. Their yaw is passed on in
    whatever unit it came in, for the parser to convert once.

    Returns None when there is no position to draw: an empty value, the
    origin, or POSITION_UNKNOWN.
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = [part.strip() for part in text.split(",")]

    if isinstance(value, dict) and isinstance(value.get("position"), list):
        value = value["position"]
        if len(value) > 2:
            try:
                value = [value[0], value[1], float(value[2]) / 1000]
            except TypeError, ValueError:
                value = value[:2]

    if isinstance(value, dict):
        x = _first(value, "x", "pos_x", "cur_x")
        y = _first(value, "y", "pos_y", "cur_y")
        yaw = _first(value, "yaw", "phi", "angle", "a")
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x, y = value[0], value[1]
        yaw = value[2] if len(value) > 2 else None
    else:
        return None

    try:
        x, y = float(x), float(y)
    except TypeError, ValueError:
        return None
    if (x == 0 and y == 0) or POSITION_UNKNOWN in (x, y):
        return None
    return {"x": x, "y": y, "yaw": 0 if yaw is None else yaw}


def charger_position(payload: dict[str, Any]) -> dict[str, Any] | None:
    """The dock's position in the map payload, in the position shape.

    Its yaw is in milliradians, as 7-4's is, and goes on in radians for the
    parser to convert whole. A real S20+ reported a pile_yaw of 1753, 100.4°,
    while it sat docked facing 99.6°.
    """
    if not payload.get("have_pile"):
        return None
    try:
        x, y = float(payload["pile_x"]), float(payload["pile_y"])
    except KeyError, TypeError, ValueError:
        return None
    try:
        yaw = float(payload.get("pile_yaw", 0)) / 1000
    except TypeError, ValueError:
        yaw = 0
    return {"x": x, "y": y, "yaw": yaw}


def place_vacuum(
    payload: dict[str, Any],
    position: dict[str, Any] | None,
    *,
    docked: bool,
    path: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the map payload with the robot placed where it is.

    Docked, the robot is drawn on its dock. Otherwise it is drawn where the
    position property says, or, with no position reported, at the end of its
    path, and failing that on its dock. With nothing to place it by, the
    payload comes back as it was.
    """
    if docked:
        placed = charger_position(payload) or position
    elif position is not None:
        placed = position
    elif path:
        placed = {"x": path[-1]["x"], "y": path[-1]["y"], "yaw": 0}
    else:
        placed = charger_position(payload)
    if placed is None:
        return payload
    return {**payload, "position": placed}


def cloud_object_name(value: Any) -> str | None:
    """The name of the cloud object a MIoT property points at.

    The property arrives as the bare name, as a user/device/name path, or as a
    JSON object with the path in "obj_name". The cloud's file URL takes the
    name alone, so only the last part of a path is kept.
    """
    if isinstance(value, str):
        text = value.strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = text
    if isinstance(value, dict):
        value = value.get("obj_name")
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value.split("/")[-1] or None
    return None


def decode_trajectory(raw: bytes) -> list[dict[str, Any]]:
    """Read a downloaded trajectory object into points, in the order visited.

    The object is zlib-compressed, and may arrive base64-encoded, bare or
    inside a JSON object's "data" as the map does. A point the robot mopped
    carries "mop": True. Returns no points for anything that does not decode.
    """
    data = _decompress_trajectory(raw)
    points: list[dict[str, Any]] = []
    index = 0
    while index + _TRAJECTORY_RECORD.size <= len(data):
        marker, x, y = _TRAJECTORY_RECORD.unpack_from(data, index)
        if marker not in (TRAJECTORY_POINT, TRAJECTORY_MOP_POINT):
            # Not a record: step over it a byte at a time, a header included.
            index += 1
            continue
        if abs(x) <= MAX_TRAJECTORY_COORDINATE and abs(y) <= MAX_TRAJECTORY_COORDINATE:
            points.append({"x": x, "y": y, "mop": marker == TRAJECTORY_MOP_POINT})
        index += _TRAJECTORY_RECORD.size
    return points


def with_path(payload: dict[str, Any], points: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the map payload with the trajectory as its path.

    The points go in without their mop marks, so the parser draws the path but
    no mop path: it would join every mopped point into one line, across the
    gaps between runs. mop_runs draws those instead. A payload that carries a
    path of its own keeps it.
    """
    if not points or payload.get("paths"):
        return payload
    return {**payload, "paths": [{"x": p["x"], "y": p["y"]} for p in points]}


def with_restricted_regions(
    payload: dict[str, Any], areas: Any, walls: Any
) -> dict[str, Any]:
    """Return the map payload with the restricted areas and walls in it.

    They go into "fb_regions", the forbidden regions vacuum_map_parser_xiaomi
    draws, after any the map carries itself. Each area becomes a region of
    four corners, no-mop where its fb_attr says so and no-go otherwise, and
    each wall a region of type "wall", whose ends the parser reads from its
    first and third points. With nothing to add, the payload comes back as it
    was.
    """
    regions = [
        {"type": _area_type(item), "points": corners}
        for item, corners in _regions(areas, 4)
    ] + [
        {"type": "wall", "points": [ends[0], ends[0], ends[1], ends[1]]}
        for _, ends in _regions(walls, 2)
    ]
    if not regions:
        return payload
    existing = payload.get("fb_regions")
    if not isinstance(existing, list):
        existing = []
    return {**payload, "fb_regions": [*existing, *regions]}


def mop_runs(points: list[dict[str, Any]]) -> list[list[Point]]:
    """Split the mopped points into the runs the robot mopped them in.

    A run ends at a point the robot did not mop, or where two mopped points
    lie more than MAX_MOP_RUN_GAP apart. Runs of fewer than MIN_MOP_RUN_POINTS
    points are dropped.
    """
    runs: list[list[Point]] = []
    run: list[Point] = []

    def end_run() -> None:
        if len(run) >= MIN_MOP_RUN_POINTS:
            runs.append(run.copy())
        run.clear()

    for point in points:
        if not point.get("mop"):
            end_run()
            continue
        current = Point(point["x"], point["y"])
        if (
            run
            and math.hypot(current.x - run[-1].x, current.y - run[-1].y)
            > MAX_MOP_RUN_GAP
        ):
            end_run()
        run.append(current)
    end_run()
    return runs


def _decompress_trajectory(raw: bytes) -> bytes:
    payload = raw
    try:
        text = raw.decode("ascii").strip()
    except UnicodeDecodeError:
        text = ""
    if text.startswith("{"):
        try:
            payload = base64.b64decode(json.loads(text)["data"])
        except json.JSONDecodeError, KeyError, TypeError, ValueError:
            return b""
    elif text:
        try:
            payload = base64.b64decode(text, validate=True)
        except ValueError:
            payload = raw
    try:
        return zlib.decompress(payload)
    except zlib.error:
        # Some firmware sends the records uncompressed.
        if payload[:1] in (bytes([TRAJECTORY_POINT]), bytes([TRAJECTORY_MOP_POINT])):
            return payload
        return b""


def _regions(value: Any, corners: int) -> list[tuple[Any, list[dict[str, float]]]]:
    """Each region a restricted area or wall property lists, with its points."""
    return [
        (item, points)
        for item in _region_items(value, corners)
        if (points := _region_points(item, corners)) is not None
    ]


def _area_type(item: Any) -> str:
    if isinstance(item, dict) and item.get("fb_attr") == _FB_ATTR_NO_MOP:
        return "no_mop"
    return "no_go"


def _region_items(value: Any, corners: int) -> list[Any]:
    """Split a property's value into one item per region.

    The value may be JSON text, a list of regions, one flat list of numbers
    holding them all, or an object listing them under one of
    _REGION_LIST_KEYS. An object that lists none stands for one region itself.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        for key in _REGION_LIST_KEYS:
            if key in value and (items := _region_items(value[key], corners)):
                return items
        return [value]
    if isinstance(value, list):
        size = corners * 2
        if value and len(value) % size == 0 and _pairs(value) is not None:
            return [value[index : index + size] for index in range(0, len(value), size)]
        return value
    return []


def _region_points(item: Any, corners: int) -> list[dict[str, float]] | None:
    """Read one region into its points, or None without `corners` of them.

    A region is an object with its points as x0, y0, x1, y1 and so on, an
    area's two opposite corners as x1, y1, x2, y2, or its points under one of
    _POINT_LIST_KEYS. Or it is a list, of the points or of their coordinates
    one after another.
    """
    if isinstance(item, dict):
        keys = [f"{axis}{index}" for index in range(corners) for axis in "xy"]
        if all(key in item for key in keys):
            return _pairs([item[key] for key in keys])
        if corners == 4 and all(key in item for key in ("x1", "y1", "x2", "y2")):
            x1, y1, x2, y2 = (_number(item[key]) for key in ("x1", "y1", "x2", "y2"))
            if None in (x1, y1, x2, y2):
                return None
            return [
                {"x": x1, "y": y1},
                {"x": x2, "y": y1},
                {"x": x2, "y": y2},
                {"x": x1, "y": y2},
            ]
        for key in _POINT_LIST_KEYS:
            if key in item and (points := _region_points(item[key], corners)):
                return points
        return None
    if not isinstance(item, (list, tuple)):
        return None
    if len(item) == corners * 2 and (points := _pairs(item)) is not None:
        return points
    points = [_point(value) for value in item[:corners]]
    if len(points) < corners or None in points:
        return None
    return points


def _point(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        x = _number(_first(value, "x", "pos_x", "x0"))
        y = _number(_first(value, "y", "pos_y", "y0"))
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x, y = _number(value[0]), _number(value[1])
    else:
        return None
    if x is None or y is None:
        return None
    return {"x": x, "y": y}


def _pairs(values: list[Any]) -> list[dict[str, float]] | None:
    """Read coordinates listed one after another into points."""
    numbers = [_number(value) for value in values]
    if len(numbers) % 2 or None in numbers:
        return None
    return [{"x": x, "y": y} for x, y in zip(numbers[::2], numbers[1::2])]


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _first(data: dict[str, Any], *keys: str) -> Any:
    return next((data[key] for key in keys if key in data), None)
