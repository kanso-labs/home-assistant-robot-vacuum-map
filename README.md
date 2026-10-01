# Robot Vacuum Map

[![Lint][lint-shield]][lint-workflow] [![Test][test-shield]][test-workflow]
[![Release][release-shield]][release] [![HACS][hacs-shield]][hacs]
[![License][license-shield]](./LICENSE.md)

A Home Assistant integration that draws a live map of your robot vacuum from
Xiaomi's cloud, with no rooting. It reads Xiaomi, Roborock, Dreame, Viomi,
Roidmi and iJai vacuums.

It is a kanso-labs copy of Piotr Machowski's
[Xiaomi Cloud Map Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor),
with a domain of its own, `robot_vacuum_map`, so the two can be installed side
by side.

<img src="https://raw.githubusercontent.com/kanso-labs/home-assistant-robot-vacuum-map/main/images/map_no_rooms.png" width="48%" alt="A map drawn without rooms">
<img src="https://raw.githubusercontent.com/kanso-labs/home-assistant-robot-vacuum-map/main/images/map_rooms.png" width="48%" alt="The same map with its rooms coloured">

## Installation

It needs Home Assistant 2026.3 or later, and [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kanso-labs&repository=home-assistant-robot-vacuum-map&category=integration)

Or add it by hand, from **HACS → ⋮ → Custom repositories**, as an
**Integration**:

```text
https://github.com/kanso-labs/home-assistant-robot-vacuum-map
```

Then download **Robot Vacuum Map** and restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Robot Vacuum Map.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=robot_vacuum_map)

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

A new entry draws the map four times the size of the cloud map's grid, with the
elements' sizes multiplied to match. An entry set up before 0.8.0 keeps drawing
at its old scale of 1 until you raise **Image dimensions → Scale**, and raise
**Map elements' sizes** by the same factor so the path and the robot keep their
size against the map. Walls and rooms cannot get finer than the grid itself,
which on the Xiaomi Robot Vacuum S20+ is 5 cm to a cell.

### Entities

| Entity                                                        | What it does                                                           |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Live map** (image)                                          | The rendered map                                                       |
| **Live map** (camera)                                         | The same map as a camera, for cards that need one. Disabled by default |
| **Update map** (switch)                                       | Pauses and resumes automatic updates                                   |
| **Force map update** (button)                                 | Updates the map now                                                    |
| **Is map empty** (binary sensor)                              | Whether the last map came back empty                                   |
| Positions, rooms, paths, zones, walls and obstacles (sensors) | One sensor for each element of the map                                 |

The map is fetched every 10 seconds while the vacuum is working, and a few more
times after it stops. On the Xiaomi Robot Vacuum S20+, a map or path that has
not changed since the last update is drawn again rather than downloaded again.

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
    custom_components.robot_vacuum_map: debug
```

The diagnostics download on the integration's device holds the last map, both as
downloaded and as parsed, with the credentials, token, address and MAC removed.
For a vacuum on the Xiaomi map API it also holds the last value read from each
MIoT property, and for the Xiaomi Robot Vacuum S20+ the last trajectory
downloaded, with the account and device IDs taken out of object names.

## Development

Fork, then clone the repository:

```shell
git clone https://github.com/your-username/home-assistant-robot-vacuum-map.git
```

`mise install` puts the Python and uv that [`.tool-versions`](.tool-versions)
pins on the path.

### The commands CI runs

CI runs these four on every pull request, and each runs the same locally:

```shell
uv run ruff format --check  # Python formatting
uv run ruff check           # Python lint
uv run pytest               # the tests, against Home Assistant 2026.9.4
npx prettier --check .      # YAML, JSON and Markdown
```

CI also validates the integration with hassfest and HACS, and lints the
workflows. [AGENTS.md](./AGENTS.md) has the command that runs hassfest locally;
HACS reads the repository through the GitHub API, so it runs only in CI.

## Contributing

Issues and pull requests are welcome. The organization's contributing guide
lives in
[kanso-labs/.github](https://github.com/kanso-labs/.github/blob/main/CONTRIBUTING.md)
and covers how to report, propose and submit.

[AGENTS.md](./AGENTS.md) is the working reference for anything specific to this
repository: its layout, how releases reach an installed instance, how changes
come in from upstream, and the traps that have already caught someone. It is
written for people and coding agents alike.

Participation is governed by the
[code of conduct](https://github.com/kanso-labs/.github/blob/main/CODE_OF_CONDUCT.md).

## License

This integration is MIT licensed. See [LICENSE.md](./LICENSE.md), which keeps
Piotr Machowski's copyright notice beside Kanso Labs', as the licence requires
of a copy.

It is built on others' work:

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

[hacs]: https://hacs.xyz/docs/faq/custom_repositories/
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[license-shield]: https://img.shields.io/badge/license-MIT-blue.svg
[lint-shield]:
  https://github.com/kanso-labs/home-assistant-robot-vacuum-map/actions/workflows/lint.yaml/badge.svg
[lint-workflow]:
  https://github.com/kanso-labs/home-assistant-robot-vacuum-map/actions/workflows/lint.yaml
[release]:
  https://github.com/kanso-labs/home-assistant-robot-vacuum-map/releases/latest
[release-shield]:
  https://img.shields.io/github/v/release/kanso-labs/home-assistant-robot-vacuum-map
[test-shield]:
  https://github.com/kanso-labs/home-assistant-robot-vacuum-map/actions/workflows/test.yaml/badge.svg
[test-workflow]:
  https://github.com/kanso-labs/home-assistant-robot-vacuum-map/actions/workflows/test.yaml
