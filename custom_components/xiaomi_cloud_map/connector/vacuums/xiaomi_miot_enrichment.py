"""Live map data a Xiaomi vacuum publishes as MIoT properties, not in its map.

The Xiaomi Robot Vacuum S20+ (xiaomi.vacuum.b108gl) keeps its rooms, its dock
and its calibration in the cloud map, but not the robot: it publishes its
position on its own, as MIoT property 7-4. The functions here merge such
properties into the map's JSON payload, in the shape vacuum_map_parser_xiaomi
reads, before the parser draws it.

Ported from xiaomi_miot_enrichment.py in upstream pull request #750, by almirus.
"""

import json
from typing import Any

# The coordinate the b108gl reports while it does not know where it is.
POSITION_UNKNOWN = 1100


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
    payload: dict[str, Any], position: dict[str, Any] | None, *, docked: bool
) -> dict[str, Any]:
    """Return the map payload with the robot placed where it is.

    Docked, or with no position reported, the robot is drawn on its dock.
    Otherwise it is drawn where the position property says. With neither a
    position nor a dock, the payload comes back as it was.
    """
    placed = position
    if docked or position is None:
        placed = charger_position(payload) or position
    if placed is None:
        return payload
    return {**payload, "position": placed}


def _first(data: dict[str, Any], *keys: str) -> Any:
    return next((data[key] for key in keys if key in data), None)
