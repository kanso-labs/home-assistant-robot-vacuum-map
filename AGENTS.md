# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

A Home Assistant custom integration, installed through HACS, that draws a live
map of a robot vacuum from Xiaomi's cloud. Its domain is `xiaomi_cloud_map`.

It is a copy of Piotr Machowski's
[Xiaomi Cloud Map Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor),
made kanso-labs' own so that the Xiaomi Robot Vacuum S20+
(`xiaomi.vacuum.b108gl`) is drawn live. `main` begins at upstream's
v3.0.0-alpha-24, `688fe3e` on its `dev_extracted_libraries` branch, with
upstream's history below it. Everything after that commit is this repository's;
see Upstream.

| Path                                            | What it is                                                                   |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| `custom_components/xiaomi_cloud_map/`           | The integration: config and options flows, coordinator, entities             |
| `custom_components/xiaomi_cloud_map/connector/` | Upstream's cloud connector, and one vacuum class per map API                 |
| `custom_components/xiaomi_cloud_map/brand/`     | The icon and logo, which Home Assistant 2026.3 and later serves from here    |
| `tests/`                                        | pytest, through `pytest-homeassistant-custom-component`                      |
| `blueprints/`                                   | Upstream's automations, written for v2's YAML camera and not re-tested on v3 |
| `images/`                                       | What `README.md` shows                                                       |

The blueprints stay because users import them by URL, but nothing here links
them, and they drive the camera the way v2 did rather than through v3's **Update
map** switch.

## Commands

Everything runs from the repository root, after `mise install` has put the
Python and uv that `.tool-versions` pins on the path.

| Task                           | Command                                                                                | Notes                                                           |
| ------------------------------ | -------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Install the tools              | `mise install`                                                                         |                                                                 |
| Run the tests                  | `uv run pytest`                                                                        | Against Home Assistant 2026.9.4                                 |
| Lint Python                    | `uv run ruff check`                                                                    | `Lint Python` runs this in CI                                   |
| Format Python                  | `uv run ruff format`                                                                   | CI runs it with `--check`                                       |
| Format YAML, JSON and Markdown | `npx prettier --write .`                                                               | CI checks at the version `lint.yaml` pins in `PRETTIER_VERSION` |
| Validate with hassfest         | `docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest:2026.9.4` | The image and tag `lint.yaml` runs                              |

HACS validation runs only in CI, as `Validate with HACS`. It reads the
repository through the GitHub API at the pushed ref, so there is nothing for it
to check before a push.

There is no root `package.json`, so there is no `format` script. Prettier runs
through `npx`, as in `home-assistant-applications`.

## Conventions

### Shared with the other `kanso-labs` repositories

The canonical text is
[`CONVENTIONS.md`](https://github.com/kanso-labs/.github/blob/main/CONVENTIONS.md)
in `kanso-labs/.github`; this is a copy, kept in step by hand. Change that file
first, then every copy.

- **Keys in JSON and YAML are ordered by name.** Files whose order carries
  meaning are exempt: workflows, where step order is execution order;
  changelogs, which are chronological; and `package.json`, where the npm
  ecosystem expects `name` and `version` first.
- **A workflow's filename is the kebab-case of its `name:` field.** Reusable
  workflows, meaning those triggered only by `workflow_call`, take a leading
  underscore.
- **Job names and step names are imperative verb phrases.** Job ids, step ids,
  and matrix keys are exempt.
- **Actions are pinned to exact release tags**, `actions/checkout@v7.0.1`, never
  `@main` and never a tag the publisher moves — `@v7` and `@v7.0` both move.
  Renovate opens the bump pull requests, and it has nothing to open when the pin
  never changes: `frenck/action-app-linter@v2.21` sat still through a repository
  rename and a release that fixed something a consumer was working around,
  because the tag it named was moved onto both.
- **Dependency versions are pinned exactly.** Every `dependencies`,
  `devDependencies`, and `optionalDependencies` entry is a bare version,
  `1.2.3`, never `^1.2.3`, `~1.2.3`, `>=1.2.3`, `*`, `1.x`, or an `||` union.
  Renovate opens those bumps too. `peerDependencies` are the deliberate
  exception: they state what the consumer's own installed copy must satisfy, so
  ranges are correct there and stay.
- **`.tool-versions` pins a fully-specified version on every line**,
  `nodejs <major>.<minor>.<patch>`, never `nodejs 24` or `nodejs lts`.

### Where this repository departs from them

- **`manifest.json` keeps `domain` and `name` first**, because hassfest requires
  it, as `package.json` keeps `name` and `version` first. The other keys are
  ordered by name.
- **A requirement Home Assistant already pins stays unpinned in
  `manifest.json`**, Pillow first among them. Home Assistant installs an
  integration's requirements under its own package constraints, so a second pin
  would conflict with Home Assistant's the first time either moved. Every other
  requirement is pinned exactly.

**ruff formats and lints the Python, and Prettier the YAML, JSON and Markdown.**
ruff runs at its defaults, apart from three rules waived for `connector/`; see
Traps. `pyproject.toml` pins every development dependency exactly, and its
`version` of `0.0.0` is only there because uv needs one: the integration's
version is `manifest.json`'s.

## Releases

HACS installs an integration from its GitHub releases. It offers the five latest
and installs the newest, so nothing reaches an installed instance until a
release is cut.

release-please cuts them, through the shared workflow in
[`kanso-labs/actions`](https://github.com/kanso-labs/actions), which
`.github/workflows/release-please.yaml` calls at a pinned tag, as the siblings
do. A push to `main` keeps the release pull request current, the daily 09:00 UTC
run is the only one that merges it, and `workflow_dispatch` re-proposes a stuck
one.

- **One package, at the root**, tagged `v<version>`. `manifest.json`'s `version`
  is written through `extra-files`. Never edit it by hand.
- **`feat` and `fix` release, and nothing else does.** Below 1.0.0, `feat` takes
  a minor and `fix` a patch. Every other type, `deps` included, sits in a hidden
  changelog section, and a run whose commits are all hidden opens no release
  pull request.
- **`deps` is hidden here, unlike in the siblings.** Every commit belongs to the
  one root package, so a visible `deps` would make each Renovate bump to an
  action or a formatter cut a release that HACS then offers as an update
  changing nothing. The bumps that do change an installed integration, to
  `manifest.json`'s requirements, are typed `fix` by `.github/renovate.json`.
- **`bootstrap-sha` is `688fe3e`**, the last upstream commit, so no changelog
  lists upstream's history.
- **`initial-version` is `0.1.0`.** `bump-minor-pre-major` only governs bumps
  from an earlier release. With no release yet, release-please would have
  started at 1.0.0.

### Renovate

The organization's runner in
[`kanso-labs/renovate`](https://github.com/kanso-labs/renovate) manages this
repository, and `.github/renovate.json` shapes what it opens:

- **`manifest.json`'s requirements** are read by Renovate's own
  `homeassistant-manifest` manager, which skips Pillow for carrying no version.
  They are typed `fix`, and each lands in one pull request with its
  `pyproject.toml` twin, because Renovate names the branch after the package.
- **The hassfest image, `homeassistant` and
  `pytest-homeassistant-custom-component`** move together, in one "Home
  Assistant" pull request. The hassfest image is held to release tags.
- **PyTurboJPEG and protobuf are never bumped.** They are pinned to what Home
  Assistant itself pins, and move by hand with the Home Assistant bump that
  changes those pins.
- **`.tool-versions`** is read by Renovate's `asdf` manager. Its `mise` manager
  reads only `mise.toml` files.

`@renovate rebase` on one of its pull requests works through
`.github/workflows/renovate-command.yaml`, which calls the shared
`_renovate-command.yaml`.

## Upstream

Upstream is
[PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor).
Its v3 integration lives on `dev_extracted_libraries`, not `master`. None of
upstream's tags came across: this repository's first tag is its own `v0.1.0`.

**A change from upstream is ported, not merged.** The integration's directory
and domain were renamed, and ruff reformatted every file, so a cherry-pick of an
upstream commit rarely applies. Bring one in like this:

1. Fetch upstream into a ref of its own, and list what it has that `main` does
   not. An open upstream pull request comes the same way, from
   `refs/pull/<number>/head`.

   ```shell
   git fetch https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor.git \
     dev_extracted_libraries:refs/upstream/dev_extracted_libraries
   git log --oneline 688fe3e..refs/upstream/dev_extracted_libraries
   ```

2. Make the change by hand under `custom_components/xiaomi_cloud_map/`, run
   `uv run ruff format`, and add a test that fails without it.
3. Credit its author with a `Co-authored-by:` trailer. The squash merge keeps
   only the pull request title, so make sure the trailer is still in the merge
   box when the pull request merges.

What this repository proves on hardware goes back upstream as a comment on the
upstream pull request it came from, and only on the account owner's go-ahead,
since the comment is public.

## Commits and pull requests

Pull requests are squash-merged, with the pull request title as the commit
subject and an empty body. That title becomes the only commit on `main` and the
only thing release-please reads, so it is a Conventional Commit:

| Type of the pull request title | Effect               |
| ------------------------------ | -------------------- |
| `feat`                         | releases, minor bump |
| `fix`                          | releases, patch bump |
| anything else                  | no release           |

A `!` marks a breaking change, which also takes a minor below 1.0.0.

Work lands as stacked pull requests, each based on the one below it. `Lint` and
`Test` run on every pull request for that reason, not only on those into `main`,
and the `Default` ruleset requires `Confirm lint succeeded` and
`Confirm tests succeeded` before anything merges into `main`.

Write branch commits conventionally anyway. They are what a reviewer reads while
the pull request is open, even though only the title survives the merge.

## Traps

**HACS's `brands` check is ignored, and `brand/icon.png` is checked in its
place.** HACS 2.0.5, its newest release, looks for brand images only in
home-assistant/brands, where `xiaomi_cloud_map` will never be listed. The check
that also reads an integration's own `brand/` directory,
[hacs/integration#5128](https://github.com/hacs/integration/pull/5128), is on
HACS's main branch but in no release. So `lint.yaml` passes
`INPUT_IGNORE: brands` and tests for the icon itself, and `tests/test_brand.py`
checks every image. Remove the ignore at the first HACS release that carries the
local check.

**`LICENSE.md` is not the organization's byte-identical copy.** MIT requires
keeping upstream's copyright notice, so this one carries Piotr Machowski's line
above Kanso Labs'. Neither formatter touches it, as with every other copy.

**Prettier formats `manifest.json` with its `json-stringify` parser.**
release-please rewrites the file with `JSON.stringify`, which puts every array
on its own lines, while Prettier's `json` parser collapses short ones. Without
the override in `.prettierrc`, every release pull request would fail
`Check formatting`.

**Home Assistant's test harness installs no requirements**, the integration's or
its own components'. `pyproject.toml`'s test group therefore repeats
`manifest.json`'s pins, and adds PyTurboJPEG, which Home Assistant's camera
requires, and protobuf. A requirement bumped in one file and not the other
leaves the tests running something no install does.

**`vacuum-map-parser-ijai` imports protobuf without declaring it.** The
connector imports every map API at start-up, so an install without protobuf
cannot load the integration at all. Home Assistant's container image carries it,
because its `requirements_all.txt` pulls it in, but a bare Home Assistant Core
install may not.

**`pytest-homeassistant-custom-component` publishes a release for every Home
Assistant beta**, and its version cannot say so. `pyproject.toml` pins
`homeassistant` exactly beside it, so a beta-built release fails to lock instead
of slipping into the tests.

**Once a release exists, HACS validates the latest release as well as the ref.**
The first release pull request was merged seconds before its tag was readable,
and failed `Validate with HACS` with
`Repository structure for v0.1.0 is not compliant`. The same check passed on
`main` a minute later. Re-run it before looking for a structural problem.

**`Closes #N` in a pull request body has not linked the issue here.** None of
the first pull requests picked up its closing keyword, so merging them closed
nothing, and the issues were closed by hand. The siblings' pull requests link
normally, and the cause is not known. Check the issue after a merge.

**The connector waives three ruff rules.** `BLE001`, `DTZ005` and `S110` are off
for `connector/` in `pyproject.toml`. Upstream's connector catches whatever a
cloud or device call raises and logs it, and compares naive local timestamps
only with each other. Making them timezone-aware would touch the session data
the connector persists.

**`except A | B` does not catch anything.** Python raises `TypeError` when it
matches an exception against a union; only a tuple works. ruff's `B030` reports
it, and the connector carried one until ruff arrived.
