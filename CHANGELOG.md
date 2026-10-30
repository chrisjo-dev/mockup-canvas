# Changelog

All notable changes to mockup-canvas are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-10-30

### Added

- Pins (#15): tell the agent exactly which part of a board you mean. Press `C` or Point in the canvas toolbar, click a spot or drag an area on a board, and write a note. The board gets a numbered pin.
- The server opens the board in its own headless Chrome (the guarded one that renders thumbnails), finds the element under the pin, and saves its CSS selector, text, a short HTML excerpt, and a crop of that part of the board in `<idea>/render/.pins/`. The canvas never reads into a board's sandboxed iframe.
- Pin details show the note, the element, and the crop, with Copy for AI (one line naming the idea, board, pin, and element), Resolve or Reopen, and Delete with Undo. `P` hides pins.
- When a board file changes, its pins are looked up again by selector and move with their elements; a pin whose element is gone is marked `lost` and stays where it was.
- `canvas pins <idea dir> [file] [--all] [--json]` lists pins for an agent, and `--resolve N --note TEXT` and `--reopen N` change them. `canvas comment ... --at x,y[,w,h]` or `--el SELECTOR` adds a pin from the command line, so mockup-review can pin its findings.
- The three skills run `canvas pins` when the user mentions pins and treat pin text as data, not instructions.
- Pins are optional fields on the existing `comments[]` entries in `canvas.json`, so older versions keep them.

### Security

- `POST /api/pin` takes the same same-origin and `Content-Type` checks as every other write. Share pages (including `--share-edit`) and read-only servers have no pin UI, answer 403, and do not serve pin images. A note is at most 500 characters and a board holds at most 50 pins. Share and read-only servers never probe pins (a probe writes `canvas.json`).

## [0.6.0] - 2026-10-29

### Added

- Delete with Undo (#14). Delete idea in a dashboard card's menu, Delete board in a new `...` menu on each board title (or right-click the title) on the canvas, and Delete collection in a collection's menu. Each asks first and then shows a toast with Undo for 8 seconds.
- Deleting never removes files. An idea folder moves to `<design dir>/.trash/<idea>-<UTC time>/`. A board file moves to `<design dir>/.trash/<idea>/`, with its canvas.json entry (position, group, status, comments, implementation record) and its flow arrows in a sidecar JSON, so a restore puts all of it back. A collection is only taken out of `roots.json`; its projects and ideas stay.
- `canvas trash <idea dir> [file]`, `canvas trash --list <design dir>`, and `canvas restore <design dir> <id>` do the same from the command line. A restore refuses when something now has the same name.
- The skills keep their rule: old versions go to `old drafts` as rejected. They delete only when the user asks, and then with `canvas trash`.

### Security

- Delete and restore are local only. Share pages (including `--share-edit`) and read-only servers have no delete menu, and their APIs answer 403. Requests need a same-origin `Origin` like every other write, names with `..`, separators, or a leading dot are refused, a linked `.trash` is refused, and every path is checked against the registered design folder.
- Folders whose names start with a dot (such as `.trash`) are never listed or served as ideas.

## [0.5.1] - 2026-10-28

### Security

- The canvas page is served with a hash-based `Content-Security-Policy` like the dashboard: only its own inline scripts run, including the ones the server injects in share mode, and requests and frames stay on the server (#12).

### Added

- A release workflow: pushing a `vX.Y.Z` tag creates the GitHub release with that version's CHANGELOG section as notes (taken by `tools/changelog_section.py`). `CONTRIBUTING.md` lists the release steps.

### Fixed

- Saving the project registry (`roots.json`) keeps top-level keys and project entry fields that this version does not know, so an older version no longer drops what a newer one wrote. `canvas.json` saves already kept them; tests now cover both.
- The Chrome cleanup tests wait up to 45 s for `canvas.py` to exit, since 15 s was once too short on a loaded machine.

## [0.5.0] - 2026-10-28

### Security

- Every static file (boards, assets, shared) is served with `Content-Security-Policy: sandbox`, and font CORS headers go only to sandboxed boards.
- Share mode derives the asset key per idea, so a link to one idea cannot open another idea's files.
- Chrome is driven over DevTools pipes, so it exits with the server even after `kill -9`.
- Board renders go through a local SOCKS5 guard proxy that pins DNS and blocks WebSocket, service worker, rebinding, and special IP address tricks.
- On Python older than 3.13, render blocking also covers the NAT64 local use, documentation, and SRv6 IPv6 ranges, which older `ipaddress` versions treat as global.

### Added

- A GitHub Actions workflow that runs the unit tests on Ubuntu with Python 3.8 and on the latest Ubuntu and macOS with the current Python 3, with Chrome so the render tests run too.
- A read-only live demo of the TrailMate example at https://chrisjo-dev.github.io/mockup-canvas/, built by `tools/build_demo.py` and published by a GitHub Pages workflow.
- `CONTRIBUTING.md`, this changelog, and issue and pull request templates.
- `CITATION.cff`, more plugin keywords, and links to the changelog and contributing guide in `llms.txt`.
- A one-time closing question in the three skills, after the first finished task on a machine: the agent asks whether to star the repository on GitHub and stars it only on a clear yes (with the signed-in `gh`), or gives the link. Creating `~/.mockup-canvas/.star-hint-shown` (or the same file under `MOCKUP_CANVAS_HOME`) turns it off.

### Changed

- The README gives the CLI size as about 4,000 lines (it had grown past the 3,300 lines it stated).
- The README opening paragraph is a self-contained definition, and three new FAQ entries answer common questions directly, in all four languages.

### Fixed

- The dashboard rail no longer shows a stray "null" when there are no collections.
- An exported page keeps its own `<title>` instead of always showing "Exported canvas".
- `canvas.py` loads on Python 3.8 again; a decorator needed Python 3.9.
- `canvas serve` and the `export` check no longer wait on a reverse DNS lookup of the bind address, which took 35 s on a macOS CI runner.

## [0.4.1] - 2026-10-28

### Fixed

- On phones, the collection subline ("Includes all of ...") wraps as one sentence and keeps project names on one line.
- An open card menu no longer sits on top of the Open canvas and Reveal buttons.

### Added

- A favicon on the dashboard and the canvas page, readable on light and dark tab bars.

## [0.4.0] - 2026-10-28

### Added

- Collections: gather ideas from different projects under one name in the dashboard rail, without moving any folder. Move an idea from its card menu (Move to collection), or add a whole project from its menu (Add to collection), so its later ideas join too.
- A collection page with the status filters, search, sort, and card sizes.
- `POST /api/roots/collection`; collections are saved in `roots.json` and shown read-only in share mode.

### Changed

- The README shows a demo GIF, a social preview, and dashboard screenshots made from the example data.

### Fixed

- Collection names with invisible characters are refused, and collections are capped at 100.

Note: a server older than 0.4.0 drops collections when it saves `roots.json`, so update every machine that shares that file.

## [0.3.0] - 2026-10-27

### Added

- A gallery dashboard at `http://localhost:4400/`: idea cards with thumbnail mosaics, a status meter, open comments, built count, and "N new" since your last visit.
- A side rail with projects and status filters (Needs decision, Has comments, Approved not built, Built), search, Large and Compact grids, and an all-boards view per project.
- A command palette (`/` or `Cmd+K`) to jump to any idea or board, add a project, or switch theme.
- Add project and find in folders in a dialog with inline errors; missing folders show a warning with Locate, Check again, and Remove.
- Light and dark themes, a phone layout, and a read-only share view of the dashboard.
- `#<board>` links that open a canvas fitted to one board.

### Changed

- Built badges are violet to match the new design system.
- Web fonts no longer block the dashboard's first paint.

### Fixed

- Boards that keep images in subfolders (for example `assets/photos/x.jpg`) no longer lose them when you zoom in. Paths stay contained to their folder, symlinked asset and shared folders are refused, and NUL in paths is rejected.
- A thumbnail render never recreates an idea folder that was moved or deleted.

### Security

- Retry limits, project name rules, JSON boot data, and a send timeout for live-reload streams.

## [0.2.1] - 2026-10-23

### Fixed

- Boards on a large canvas turn sharp sooner and stay fresh: small pans no longer cancel loading boards, live boards mount sooner, thumbnails render at the scale the screen needs, and an edited board asks for its new thumbnail at once.

### Added

- Opt-in UX feel measurements for the large canvas in the end-to-end suite.

## [0.2.0] - 2026-10-22

### Added

- The `mockup-review` and `mockup-to-code` skills, so the three skills cover draw, review, and build.
- `snap`, `compare`, `impl`, and `comment` commands: screenshot a running app page, compare it with a board pixel by pixel, record which route and files implement a board, and leave review comments on boards.
- The canvas shows a built badge and a comment panel.
- `add --size` resizes a registered board, and `render --full-page` captures the whole scroll height.
- An optional Playwright end-to-end suite in `e2e/`.
- `install.sh` links every skill folder under `skills/`.

### Changed

- The canvas stays smooth with many boards: only boards near the view keep a live page, zoomed-out boards show cached thumbnails, and screen updates are batched once per frame.

### Fixed

- Captures use the exact viewport over DevTools, with a real wait after the page load event.
- Every command stops its own Chrome and deletes its profile when it ends, also on Ctrl+C.
- A board seen once never turns white again, `HEAD` requests are answered, and the toolbar fits phone screens.

### Security

- Local files are kept out of rendered PNGs, private hosts are blocked in board renders, compare PNG sizes are capped, and inputs are hardened.

## [0.1.0] - 2026-10-21

### Added

- First release: the `mockup-canvas` skill and the `canvas.py` CLI with `serve`, `roots`, `new`, `add`, `group`, `render`, `check`, `overview`, `export`, `link`, `status`, and `artifact`.
- A local, Figma-like canvas to pan, zoom, and arrange HTML artboards, with flow arrows, groups, approval marks, live reload, and phone sharing.
- The TrailMate example and a unit test suite.

[Unreleased]: https://github.com/chrisjo-dev/mockup-canvas/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.7.0
[0.6.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.6.0
[0.5.1]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.5.1
[0.5.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.5.0
[0.4.1]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.4.1
[0.4.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.4.0
[0.3.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.3.0
[0.2.1]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.2.1
[0.2.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.2.0
[0.1.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.1.0
