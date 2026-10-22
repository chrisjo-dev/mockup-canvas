# End-to-end browser tests (optional dev tooling)

This folder is a Playwright test suite for mockup-canvas. It is **not a runtime dependency**: the
skills and `canvas.py` still need only Python 3 and Chrome. Nothing outside `e2e/` imports it, and
`node_modules/` stays inside this folder.

## What it covers

The plan is in [`specs/mockup-canvas-journeys.md`](specs/mockup-canvas-journeys.md); the tests are in
`tests/`, one file per plan section:

| File | Plan section |
| --- | --- |
| `tests/01-registry.spec.ts` | 1. Registry index: list, add, invalid paths, scan, remove |
| `tests/02-canvas.spec.ts` | 2 to 4. Rendering, zoom, fit, pan, arrows, groups, drag, undo and redo, title click and double click |
| `tests/03-comments-live.spec.ts` | 5 and 6. Comments, built badge, live reload, CLI `status` and `link` |
| `tests/04-large-canvas.spec.ts` | 7. Large canvas: thumbnails, virtualization, console errors, pan FPS |
| `tests/05-share.spec.ts` | 8. Share mode: 401 without token, read-only viewer, phone touch pan and pinch |
| `tests/06-export-security.spec.ts` | 9 and 10. Static export, board sandbox, Host and Origin checks |

Projects: `chromium`, `firefox`, `webkit` (desktop, 1280x720) and `mobile-webkit` (iPhone 13, touch),
which runs only tests tagged `@mobile`.

## Isolation

- Each test creates its own temporary HOME with a copy of `examples/trailmate` and sets
  `MOCKUP_CANVAS_HOME` inside it, so your real `~/.mockup-canvas` registry is never read or written.
  HOME is overridden because the server only accepts design folders under HOME.
- Each test starts its own `canvas.py serve` (or `python3 -m http.server` for the export) on a free
  port, never 4400, 8080, 8787, or 5173, in its own process group, and stops it (with any background
  Chrome it started) when the test ends.
- The temporary folder is deleted after a passing test and kept after a failing one.

## Run

```bash
cd e2e
npm ci
npx playwright install chromium webkit firefox
npx playwright test                      # all projects
npx playwright test --project=chromium   # one browser
npx playwright show-report               # HTML report
```

Environment variables (all optional):

| Variable | Meaning |
| --- | --- |
| `MC_E2E_LARGE_IDEA` | An idea folder with many boards (the 71-board case). Copied into the sandbox. Without it the large canvas tests are skipped. |
| `MC_E2E_TMP` | Where sandboxes are created (default: the system temp folder). |
| `MC_E2E_SHOTS` | Folder for screenshots of key states per browser and `metrics.jsonl` (FPS, live reload time). Default: each test's output folder. |
| `MC_E2E_KEEP=1` | Keep every sandbox, also after passing tests. |
| `MC_E2E_PYTHON` | Python executable (default `python3`). |

Notes:

- The FPS test drives a scripted pan with synthetic mouse events and counts `requestAnimationFrame`
  callbacks; it fails only below 30 FPS. Headless numbers are a rough signal, not a benchmark.
- Playwright has no multi-touch gesture API, so the phone pan and pinch are synthesized with
  `TouchEvent`. They exercise the viewer's touch handlers, not the browser's native gestures.
- Tests marked `test.fail()` or `test.fixme()` point at a known product bug in a comment.

## Playwright test agents (planner, generator, healer)

`npx playwright init-agents --loop=claude` generated `.claude/agents/playwright-test-*.md`,
`.mcp.json`, `seed.spec.ts`, and `specs/`. The suite here was written by following those agent
definitions by hand, because the session that wrote it could not use the `playwright-test` MCP server.

To use the real agents:

1. `cd e2e && npm ci` (the MCP server runs `npx playwright run-test-mcp-server` from this folder).
2. Open Claude Code **in the `e2e/` folder** so that `.claude/agents/` and `.mcp.json` load.
3. Approve the `playwright-test` MCP server when Claude Code asks (or enable it with `/mcp`).
4. Ask the agents in order, for example:
   - "Use the playwright-test-planner agent to explore the share mode viewer and add scenarios to specs/."
   - "Use the playwright-test-generator agent to generate tests for section 8 of specs/mockup-canvas-journeys.md."
   - "Use the playwright-test-healer agent to run the suite and fix failing tests."

The agents need a running app to explore. `seed.spec.ts` starts a sandboxed registry server with
the trailmate example, so use it as the seed file. The healer must not weaken an assertion to hide a
product bug; mark the test with `test.fail()` or `test.fixme()` and a comment instead.

## Observations from the first run

- Known product bug, marked `test.fail()`: on an iPhone 13 viewport (390 px) the toolbar is about
  401 px wide and starts at x = -5.7, so both ends are cut off (`05-share.spec.ts`, "Toolbar fits
  inside the phone viewport").
- Unconfirmed: under the full parallel run, WebKit once per run reported the live reload stream
  (`/api/events`) in share mode as blocked "due to access control checks". It did not reproduce in
  isolation (8 repeats with 4 workers), and live reload in share mode works in WebKit, so the test
  records it as an annotation instead of failing.
- `HEAD` requests get 501 from the canvas server (only GET and POST are implemented).
