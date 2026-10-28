# Changelog

All notable changes to mockup-canvas are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/chrisjo-dev/mockup-canvas/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.5.0
[0.4.1]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.4.1
[0.4.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.4.0
[0.3.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.3.0
[0.2.1]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.2.1
[0.2.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.2.0
[0.1.0]: https://github.com/chrisjo-dev/mockup-canvas/releases/tag/v0.1.0
