"""Live map data a Xiaomi vacuum publishes as MIoT properties, not in its map.

The Xiaomi Robot Vacuum S20+ (xiaomi.vacuum.b108gl) keeps its rooms, its dock
and its calibration in the cloud map, but not the robot or its path: it
publishes its position as MIoT property 7-4, and names a trajectory object in
the cloud as property 7-2. The functions here merge those into the map's JSON
payload, in the shape vacuum_map_parser_xiaomi reads, before the parser draws
it.

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


def parse_vacuum_position(value: Any) -> dict[str, Any] | None:
    """Read a vacuum-position property into the map payload's position shape.

    The property arrives as a JSON object or as "x,y,yaw" text. The yaw is
    passed on in whatever unit it came in, because vacuum_map_parser_xiaomi
    converts it to degrees itself, and converting it here as well would read a
    small angle, already in degrees, as radians.

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
    """The dock's position in the map payload, in the position shape."""
    if not payload.get("have_pile"):
        return None
    try:
        x, y = float(payload["pile_x"]), float(payload["pile_y"])
    except KeyError, TypeError, ValueError:
        return None
    return {"x": x, "y": y, "yaw": payload.get("pile_yaw", 0)}


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


def _first(data: dict[str, Any], *keys: str) -> Any:
    return next((data[key] for key in keys if key in data), None)
