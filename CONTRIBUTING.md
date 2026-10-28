# Contributing to mockup-canvas

Thanks for helping. Issues and pull requests are welcome. Please write issues, pull requests, and commit messages in English so every contributor can follow them; the READMEs and skill guides also have Korean, Simplified Chinese, and Japanese versions.

## Setup

You need Python 3.8 or later and, for rendering and the render tests, Google Chrome, Chromium, or Microsoft Edge. There are no pip dependencies.

```bash
git clone https://github.com/chrisjo-dev/mockup-canvas.git
cd mockup-canvas
python3 skills/mockup-canvas/scripts/canvas.py serve examples   # open http://127.0.0.1:4400/trailmate/
```

If Chrome is not found automatically, set `MOCKUP_CANVAS_CHROME=/path/to/chrome`.

To try your working copy as a skill, run `./install.sh --dry-run` first to see what it would link, then `./install.sh`.

Keep your own data out of experiments: set `MOCKUP_CANVAS_HOME` to a temporary folder so `~/.mockup-canvas` (your registered projects) is not read or changed.

```bash
export MOCKUP_CANVAS_HOME="$(mktemp -d)"
```

## Tests

Run the unit tests before you open a pull request:

```bash
cd tests && python3 -m unittest discover .
```

Every test uses its own temporary `HOME` and `MOCKUP_CANVAS_HOME`. Render tests are skipped when Chrome is not found; CI runs them on Linux and macOS. The same suite runs on every push and pull request (see `.github/workflows/test.yml`).

The optional end-to-end suite uses Playwright and lives in `e2e/`. It is dev tooling only, not a runtime dependency. See [e2e/README.md](e2e/README.md) for details.

```bash
cd e2e
npm ci
npx playwright install chromium webkit firefox
npx playwright test
```

For changes to the canvas viewer, check performance as well. `tests/perf_check.py` serves an idea in a temporary folder and measures frame times, long tasks, and time to the fit view in headless Chrome. It is not part of the unit suite.

```bash
python3 tests/perf_check.py examples/trailmate
python3 tests/perf_check.py <idea dir> --cold --json perf.json
```

Its targets are 55 FPS or more, p95 frame time of 25 ms or less, no frame over 50 ms, no long task over 100 ms, and the fit view within 1.5 s. Include the numbers before and after your change in the pull request (`--canvas <other canvas.py>` compares against another copy).

## Design rules

- **One file, standard library only.** The CLI and server are the single file `skills/mockup-canvas/scripts/canvas.py`, next to `viewer.html`, `dashboard.html`, and `dashboard-manage.js`. Do not add pip packages, a build step, or new runtime files that installs would have to copy. Python 3.8 must keep working.
- **Chrome only for pixels.** Chrome (or Chromium or Edge) is used only to render boards and capture app pages as PNGs.
- **Local by default.** The server binds to `127.0.0.1`, the tool makes no outbound requests, and share mode stays opt-in. Read [SECURITY.md](SECURITY.md) before changing the server, and report vulnerabilities privately through GitHub Security Advisories, not public issues.
- **Never delete user work.** Old boards move to an `old drafts` group; nothing in an idea folder is removed.
- **Keep the translations in step.** A change to `README.md` or `docs/skill.md` should say the same thing in the Korean, Simplified Chinese, and Japanese versions. If you cannot translate, say so in the pull request and a maintainer will help.

## Proposing UI changes

Changes to the canvas, the dashboard, or the share view start on the canvas, not in code:

1. Draw the proposed screen or state as an HTML artboard in an idea folder, for example with `canvas new design my-proposal` and `canvas add`, next to a board that shows the current UI.
2. Export it with `canvas export design/my-proposal ./my-proposal-export`, or attach `canvas overview` and `canvas render` PNGs, and open an issue with the feature request template.
3. Once the board is agreed, implement it and compare the result with the board. Include before and after screenshots, plus performance numbers for viewer changes.

## Commit style

Follow the style of the existing history: a conventional prefix, an optional scope, and a short lowercase summary that says what changed for the user.

```text
feat(dashboard): collections in the rail, a collection page, and menus to move ideas and projects
fix(server): refuse symlinked assets and shared folders, reject NUL in paths
perf: cancel live boards still loading when a gesture starts
test(e2e): measure scrolling on a 40-idea collection page too
docs: collections in the dashboard section of the four READMEs
release: v0.4.1
```

Common prefixes are `feat`, `fix`, `perf`, `test`, `docs`, `ci`, and `release`. Use the body for the why and for details, and reference the issue (`Refs #123` or `Fixes #123`). One focused change per commit.

## Pull requests

- Keep each pull request to one topic and describe what changed for users.
- Run the unit tests, and the end-to-end suite or `perf_check.py` when you change the viewer or dashboard.
- Update `CHANGELOG.md` under `Unreleased`, and the READMEs and skill guides when behavior or commands change.
- Fill in the pull request template; it lists the checks.
