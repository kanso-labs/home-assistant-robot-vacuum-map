# Xiaomi Vacuum Map

A Home Assistant integration that draws a live map of your robot vacuum from
Xiaomi's cloud, with no rooting. It reads Xiaomi, Roborock, Dreame, Viomi,
Roidmi and iJai vacuums.

It is a kanso-labs copy of Piotr Machowski's
[Xiaomi Cloud Map Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor),
with a domain of its own, `xiaomi_vacuum_map`, so the two can be installed side
by side.

<img src="https://raw.githubusercontent.com/kanso-labs/home-assistant-xiaomi-vacuum-map/main/images/map_no_rooms.png" width="48%" alt="A map drawn without rooms">
<img src="https://raw.githubusercontent.com/kanso-labs/home-assistant-xiaomi-vacuum-map/main/images/map_rooms.png" width="48%" alt="The same map with its rooms coloured">

## Installation

It needs Home Assistant 2026.3 or later, and [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kanso-labs&repository=home-assistant-xiaomi-vacuum-map&category=integration)

1. Open the link above. Or, in HACS, choose **Custom repositories** from the
   menu and add `https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map`
   as an **Integration**.
2. Download **Xiaomi Vacuum Map**.
3. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Xiaomi Vacuum Map.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=xiaomi_vacuum_map)

1. Sign in to the Xiaomi account the Xiaomi Home app uses, not a Roborock or
   Dreame app account. Use the username and password, or a QR code or login
   link. Xiaomi may ask for a captcha or a two-factor code, and the setup asks
   for them in turn.
2. Choose the vacuum, if the account has more than one.
3. Confirm the vacuum's local address and token, which come from the cloud, and
   the map API, which is detected from the model.

The map can be adjusted afterwards from the integration's **Configure** button:
the image's scale, rotation and trimming, its colours, the rooms' colours, which
elements are drawn, and their sizes.

### Entities

| Entity                                                        | What it does                                                           |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Live map** (image)                                          | The rendered map                                                       |
| **Live map** (camera)                                         | The same map as a camera, for cards that need one. Disabled by default |
| **Update map** (switch)                                       | Pauses and resumes automatic updates                                   |
| **Force map update** (button)                                 | Downloads the map now                                                  |
| **Is map empty** (binary sensor)                              | Whether the last map came back empty                                   |
| Positions, rooms, paths, zones, walls and obstacles (sensors) | One sensor for each element of the map                                 |

The map is fetched every 10 seconds while the vacuum is working, and a few more
times after it stops.

## Supported vacuums

The map API is chosen from the vacuum's model when it is set up:

| Map API  | Models                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------- |
| Roborock | `roborock.vacuum.*`, `rockrobo.vacuum.*`                                                          |
| Viomi    | `viomi.vacuum.*`                                                                                  |
| Roidmi   | `roidmi.vacuum.*`, `zhimi.vacuum.*`, `chuangmi.vacuum.*`, and `viomi.vacuum.v18`, `v23` and `v38` |
| Dreame   | `dreame.vacuum.*`                                                                                 |
| iJai     | `ijai.vacuum.*`, and `xiaomi.vacuum.b106eu`, `c103` and `d106gl`                                  |
| Xiaomi   | Every other `xiaomi.vacuum.*`, among them the Xiaomi Robot Vacuum S20+ (`xiaomi.vacuum.b108gl`)   |

Upstream's README lists the models it was tested on.

## Troubleshooting

Debug logging shows each poll, and why a map was or was not downloaded:

```yaml
logger:
  logs:
    custom_components.xiaomi_vacuum_map: debug
```

The diagnostics download on the integration's device holds the last map's data,
with the credentials, token, address and MAC removed.

## Development

`mise install` puts the pinned Python and uv on the path. Then `uv run pytest`
runs the tests, `uv run ruff check` and `uv run ruff format` lint and format the
Python, and `npx prettier --write .` formats everything else. `AGENTS.md` has
the rest: the conventions, how releases are cut, and how changes come in from
upstream.

## Credits

- [Piotr Machowski](https://github.com/PiotrMachowski), for the
  [Xiaomi Cloud Map Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor)
  this is a copy of, and the `vacuum-map-parser` packages behind every map API.
- [almirus](https://github.com/almirus), for the Xiaomi Robot Vacuum S20+ work
  in
  [upstream pull request #750](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor/pull/750).
- The projects upstream credits:
  [openHAB miIO add-on](https://github.com/openhab/openhab-addons/tree/main/bundles/org.openhab.binding.miio/src/main/java/org/openhab/binding/miio)
  and
  [Xiaomi Robot Vacuum Protocol](https://github.com/marcelrv/XiaomiRobotVacuumProtocol)
  by [@marcelrv](https://github.com/marcelrv),
  [valeCLOUDo](https://github.com/Xento/valeCLOUDo) by
  [@Xento](https://github.com/Xento), and
  [Valetudo](https://github.com/Hypfer/Valetudo) by
  [@Hypfer](https://github.com/Hypfer).

## License

MIT, in [`LICENSE.md`](LICENSE.md), which keeps upstream's copyright notice
beside this repository's.
