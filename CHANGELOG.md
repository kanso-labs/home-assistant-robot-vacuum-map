# Changelog

## [0.6.0](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/compare/v0.5.0...v0.6.0) (2026-09-30)


### Features

* **xiaomi:** draw no-mop areas from 2-11 in the fb_point form ([#60](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/60)) ([c9b8472](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/c9b84727f85a6240e377984d0cdd45f533cb548a))


### Bug Fixes

* **xiaomi:** fall back to the default map name when the property has none ([#58](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/58)) ([6a01d2d](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/6a01d2d059c97436a1d59b4468ea9559d834bcd8))

## [0.5.0](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/compare/v0.4.0...v0.5.0) (2026-09-30)


### Features

* **xiaomi:** draw the b108gl no-go areas and virtual walls ([#48](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/48)) ([1f74392](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/1f74392b13fdbc93977eba57c30b1ea0b655d107))


### Bug Fixes

* stop python-miio warning about a missing mapping at start-up ([#49](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/49)) ([9bd20a2](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/9bd20a2a0d16636e35c789c0dd9076ba0871f6af))
* update dependency vacuum-map-parser-ijai to v0.1.1 ([#54](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/54)) ([62549d7](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/62549d7424dfbc36c20898fb9c0e32e13bd8e1af))
* update dependency vacuum-map-parser-roborock to v0.1.5 ([#55](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/55)) ([bf04848](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/bf048488fed7d3598656a00209c280fe822cd486))
* update dependency vacuum-map-parser-xiaomi to v0.1.4 ([#56](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/56)) ([f4827e3](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/f4827e30020d5b09ef75a3a0425e1c2720373a15))

## [0.4.0](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/compare/v0.3.0...v0.4.0) (2026-09-30)


### Features

* **xiaomi:** draw the b108gl cleaning path from the trajectory object ([d82d8c5](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/d82d8c552636ae58d8c54c8860ab404fdca36461))

## [0.3.0](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/compare/v0.2.0...v0.3.0) (2026-09-30)


### ⚠ BREAKING CHANGES

* rename the integration to Xiaomi Vacuum Map ([#43](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/43))

### Code Refactoring

* rename the integration to Xiaomi Vacuum Map ([#43](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/43)) ([5ce27e6](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/5ce27e69e425238e2cdafe4e9b03761f4db2ecf1))

## [0.2.0](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/compare/v0.1.1...v0.2.0) (2026-09-30)


### Features

* **xiaomi:** draw the b108gl robot live from MIoT property 7-4 ([#40](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/issues/40)) ([8231766](https://github.com/kanso-labs/home-assistant-xiaomi-vacuum-map/commit/82317660d0f1e23b8b93133c5313f73702f9ab4b))

## [0.1.1](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/compare/v0.1.0...v0.1.1) (2026-09-30)


### Bug Fixes

* **xiaomi:** keep refreshing the b108gl map while it cleans ([#38](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/issues/38)) ([40414c3](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/commit/40414c33e4f03c6f6fc8fa910a07084d04546cd7))

## 0.1.0 (2026-09-30)


### ⚠ BREAKING CHANGES

* move the integration to the xiaomi_cloud_map domain ([#24](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/issues/24))

### Features

* **brand:** ship the icon and logo in brand/ ([#29](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/issues/29)) ([fe344c7](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/commit/fe344c734405ea5b04192bd3b3f6ebac848c9f0b))


### Code Refactoring

* move the integration to the xiaomi_cloud_map domain ([#24](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/issues/24)) ([271faaa](https://github.com/kanso-labs/home-assistant-xiaomi-cloud-map/commit/271faaa1b10c5db22ab344a33b13801730d54174))
