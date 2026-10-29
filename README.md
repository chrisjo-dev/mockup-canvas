# mockup-canvas

Three Claude Code and Codex skills for planning screens with an AI agent. The agent draws HTML mockups on a local, Figma-like canvas and reviews them. Then it builds the screens you approved in your app and compares them with the mockups.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![Tests](https://github.com/chrisjo-dev/mockup-canvas/actions/workflows/test.yml/badge.svg)](https://github.com/chrisjo-dev/mockup-canvas/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Works with Claude Code and Codex](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#quick-start-install-the-claude-code-plugin-or-codex-skill)
[![No pip dependencies: Python stdlib, Chrome for PNG rendering](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#faq)

mockup-canvas is three free, open-source (MIT) skills for Claude Code and OpenAI Codex. With them an AI agent draws your screens as HTML mockups on a local canvas, reviews them, and builds the ones you approve, then compares the built screens with the mockups. You see and approve each screen before the agent writes any app code.

`mockup-canvas` draws each screen as a plain HTML file and lays the screens out on a Figma-like canvas. You pan and zoom, link screens with flow arrows, and approve or reject them. `mockup-review` reviews those screens and leaves its findings as comments on the artboards they are about. `mockup-to-code` builds the approved screens in your app and compares each running route with its mockup, pixel by pixel, until the only differences left are intended ones.

The mockups are files in your own repository, not in a hosted tool. The canvas runs on `127.0.0.1` with no account, and approvals, comments, and build records are saved in `canvas.json`. You need Python 3.8 or later (standard library only, no pip packages). Google Chrome, Chromium, or Edge is used only to render and capture PNGs.

There is a plain-text summary for AI assistants in [llms.txt](llms.txt).

**Live demo:** [chrisjo-dev.github.io/mockup-canvas](https://chrisjo-dev.github.io/mockup-canvas/) shows the six-screen TrailMate example on the canvas. It is read-only. You can pan and zoom, but you can't move boards or change their status.

![The mockup-canvas dashboard in dark mode: seven idea cards from three projects with board thumbnails, status meters, comment, built, and new badges, and a rail of projects and status filters](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard.png)

![An idea canvas: three phone artboards linked by labeled flow arrows, with approved marks, a violet built badge, and a comment count](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/canvas.png)

![Demo: the dashboard filtered to ideas with comments, the command palette opened with / to search for trail, the trailmate idea opened on its canvas, then panning and zooming in to approved and rejected boards and opening a board's review comments](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/demo.gif)

## The three skills

**draw → review → approve → build → compare**

| Skill | When to use | What it does | Example prompt |
| --- | --- | --- | --- |
| `mockup-canvas` | Planning, before any app code | Draws each screen as an HTML artboard, links the flow, and records your approvals on the canvas. | `Draw a mockup of a habit tracker app: home, add habit, and weekly stats.` |
| `mockup-review` | Screens are drawn and you want a second opinion | Checks every board and the flow against the spec and a checklist, leaves `[must]`, `[should]`, and `[could]` comments on the boards, writes `review.md`, and recommends approve, revise, or reject. It never edits boards or sets status. | `Review the mockups in design/habits and tell me what is missing.` |
| `mockup-to-code` | You have approved boards | Builds the approved boards in your app's own framework, compares each running route with its board using `canvas compare`, and records the route and files with `canvas impl`. | `Build the approved habit tracker screens in our app.` |

You do the approving. Only boards you approve (recorded with `canvas status ... approved`) get built. All three skills run the same `canvas.py` CLI.

## Why draw mockups with an AI agent first

A UI described in words is ambiguous. "A home feed with a hero strip and a card list" means one thing to you and another to the agent until you both see it. When you plan a product with an agent, you need to see the screens before you agree on them. mockup-canvas came out of planning and building services with AI this way: get what is needed on screen first, then work from there.

The agent draws each screen as a small HTML file, and the canvas shows them side by side. You approve one, reject another, or ask for a variant, and the board updates while the agent works. App code starts only after the screens are approved. From then on the approved mockups are the visual spec, and the built screens are compared with them. The mockups stay in your repository as standalone HTML files that open in any browser, no account needed.

## What you get

**The canvas** (`viewer.html`, served locally)

- Pan and zoom like in a design tool. Boards are re-rendered at each zoom level, so they stay sharp instead of looking like a stretched bitmap.
- Drag artboards around. Positions are saved to `canvas.json`, and moves can be undone and redone.
- Flow arrows between screens, labeled with the button or action that leads there.
- Approval badges (approved, rejected). Notes show as a tooltip on the artboard title.
- A violet `built` badge on boards with a recorded implementation (the route is in its tooltip), and a comment count on boards with review comments. Click the count to read them in a panel.
- Collapsible groups of artboards, for example `current` and `old drafts`.
- It stays responsive on large boards. Only boards near the view keep a live page. When zoomed out below about 30 to 40%, boards show cached PNG thumbnails (when served). A board you have seen once shows its thumbnail, not a blank card, while it loads again. Screen updates are batched once per animation frame, and thumbnails render in the background at low priority. On a 71-artboard canvas (1440x900, Apple M4, Chrome headless), pan and zoom stay at about 59 to 60 FPS, with a p95 frame time of about 20 ms and no frame over 50 ms. That holds on first open and with cached thumbnails. To reproduce, run `python3 tests/perf_check.py <idea folder>`.
- Live reload. The server checks for file changes every second, so an edit to an artboard or `canvas.json` shows up within about a second.
- The server opens on a dashboard of every registered project. It has idea cards with the newest board thumbnails, status counts, comments, and built boards, filters for what needs a decision, search and a command palette (`/` or `Cmd K`), adding projects or finding design folders, warnings for missing folders, light and dark themes, and a phone layout. See [The dashboard](#the-dashboard).
- It works on a phone too, live on the same network (share mode) or as a static export you can host anywhere.

**The agent skills** (`skills/<skill>/SKILL.md`)

- `mockup-canvas` tells Claude Code or Codex how to draw, register, link, check, and show mockups, step by step. It keeps old versions instead of deleting them, and it treats your approval as the record.
- `mockup-review` checks state coverage, flow, token consistency, accessibility basics, thumb reach, and the spec, and reports findings with a severity tag on the board they concern.
- `mockup-to-code` maps the mockup tokens into your app, builds a shared shell first, then implements one approved board at a time and compares it with its board.
- Each skill ends its first run with a short retrospective that proposes improvements to the skill itself.

**The CLI** (`skills/mockup-canvas/scripts/canvas.py`)

- One Python 3 file of about 4,600 lines, standard library only (Python 3.8+), no pip dependencies. It has 18 commands: `serve`, `roots`, `new`, `add`, `group`, `render`, `check`, `overview`, `export`, `link`, `status`, `artifact`, `snap`, `compare`, `impl`, `comment`, `trash`, `restore`.
- Chrome (or Chromium or Edge) is used only to render boards and capture app pages as PNGs.

## The dashboard

`canvas serve` opens on a dashboard of every registered project at `http://localhost:4400/`. It shows what needs your attention before you open a canvas.

- **Idea cards** show thumbnails of the newest boards, a status meter (approved in green, undecided in gray, rejected in red), the open comment count, how many boards are built, and an `N new` badge for boards changed since you last opened that idea.
- **The rail** lists your projects and four status filters: Needs decision, Has comments, Approved, not built, and Built.
- **Search and the command palette.** The search box, `/`, or `Cmd+K` (`Ctrl+K`) finds any idea or board across projects and runs actions such as adding a project. A board result opens its canvas fitted to that board.
- **Views.** Large or Compact cards, sorting by recent edit, name, or board count, and an all-boards page for each project with a status filter.
- **Projects.** Add project registers a design folder, Find in folders scans folders for design folders, and each project can be renamed or removed from the list (no files are deleted).
- **Collections** gather ideas from several projects under one name in the rail, without moving any folder. Use Move to collection on an idea card, or Add to collection in a project's menu to include the whole project (its later ideas too). Each idea belongs to one collection, a collection disappears when its last idea is taken out, and they are kept in `roots.json`.
- **Delete with Undo.** Delete idea in a card's menu, and Delete collection in a collection's menu. An idea folder moves to `design/.trash/`, and a toast offers Undo for 8 seconds. Deleting a collection leaves its ideas where they are. Share pages and read-only servers have no delete.
- **Missing folder warnings** flag a registered project whose folder was moved or deleted, with a button to locate it again.
- **Light and dark themes** (the sun or moon button, or `Shift+T`), and a phone layout with project tabs and a status menu.

![The dashboard in light mode with the same projects and ideas](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard-light.png)

![The command palette open over the dashboard: matching ideas and boards with their status, and a filter action](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/palette.png)

![The dashboard on a 390 px wide phone: project tabs, a status menu, and stacked idea cards](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard-phone.png)

## Quick start: install the Claude Code plugin or Codex skill

In Claude Code, run the two `/plugin` commands below. The first adds the `chrisjo-dev/mockup-canvas` marketplace, and the second installs the plugin with all three skills. There are no pip packages to install, and Chrome is only used to render PNGs.

### Claude Code plugin

```text
/plugin marketplace add chrisjo-dev/mockup-canvas
/plugin install mockup-canvas@mockup-canvas
```

Then ask in plain words:

```text
Draw a mockup of a habit tracker app: home, add habit, and weekly stats.
```

The agent creates the idea folder, draws the screens, starts the canvas server, and gives you a URL such as `http://localhost:4400/<project>/<idea>/`.

### Manual install (Claude Code and Codex)

```bash
git clone https://github.com/chrisjo-dev/mockup-canvas.git
cd mockup-canvas
./install.sh            # links every skill into ~/.claude/skills and ~/.codex/skills
```

- `./install.sh --claude` or `./install.sh --codex` installs for one tool only.
- `./install.sh --dry-run` prints what it would do without changing anything.
- It links every skill folder under `skills/` (mockup-canvas, mockup-review, mockup-to-code), not just mockup-canvas. If you already have a skill with one of these names, or anything else at a target, it is moved to `~/.mockup-canvas/backup/<timestamp>/` first and replaced by the link. Running it again is safe.

In Codex, call a skill by name, for example: `Use $mockup-canvas to draw the sign-up flow.`, `Use $mockup-review to review the sign-up mockups.`, or `Use $mockup-to-code to build the approved sign-up screens.`

### Try the example without an agent

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

Open `http://127.0.0.1:4400/trailmate/` to see the six-screen sample in [`examples/trailmate`](https://github.com/chrisjo-dev/mockup-canvas/blob/main/examples/trailmate/canvas.json).

## Run the server

The agent starts the server for you when it draws mockups and gives you the address. To start it yourself, run `canvas.py` from the skill folder, `<skill-dir>`:

| Install | `<skill-dir>` |
| --- | --- |
| Claude Code plugin | `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas` in the agent's commands; in your own terminal, the plugin cache, usually `~/.claude/plugins/cache/mockup-canvas/mockup-canvas/<version>/skills/mockup-canvas` |
| Manual install (`install.sh`) | `~/.claude/skills/mockup-canvas` (or `~/.codex/skills/mockup-canvas`) |
| A clone of this repository | `skills/mockup-canvas` |

Tip: define a `canvas` shell function in `~/.zshrc` or `~/.bashrc` so the commands below get shorter:

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

### All registered projects

```bash
python3 <skill-dir>/scripts/canvas.py serve
```

| URL | What it shows |
| --- | --- |
| `http://localhost:4400/` | The dashboard of every registered project |
| `http://localhost:4400/<project>/<idea>/` | One idea's canvas |
| `http://localhost:4400/<project>/<idea>/#<board>` | The same canvas fitted to one board, for example `#T01-Home` |

The server listens on `127.0.0.1` only. If a server for the same projects is already running on the port, `serve` prints its address and exits; if the port holds another canvas server, it moves to the next free port and prints it.

### One design folder

```bash
python3 <skill-dir>/scripts/canvas.py serve path/to/design
```

`http://localhost:4400/` then lists that folder's ideas, and each canvas is at `http://localhost:4400/<idea>/`.

### Another port

```bash
python3 <skill-dir>/scripts/canvas.py serve --port 4500
```

`--port` works in both modes.

### View on a phone on the same Wi-Fi

```bash
python3 <skill-dir>/scripts/canvas.py serve --share --minutes 30
python3 <skill-dir>/scripts/canvas.py serve --share --project NAME
python3 <skill-dir>/scripts/canvas.py serve path/to/design --share
```

`--share` prints a URL with the computer's LAN address and a random token (`http://<lan ip>:4400/?t=...`). Open it on the phone. The page is read-only, requests without the token are refused, and the server stops by itself after `--minutes` (1 to 240, default 30). `--project NAME` shares one registered project instead of all of them. Traffic is plain HTTP, so share only on networks you trust. See [Security model](#security-model).

### Run it in the background and stop it

```bash
nohup python3 <skill-dir>/scripts/canvas.py serve > /tmp/mockup-canvas.log 2>&1 &
```

The log file holds the address and any errors. To stop a server running in the foreground, press `Ctrl+C`. To stop a background server, stop the process listening on its port:

```bash
lsof -ti tcp:4400 -sTCP:LISTEN | xargs kill
```

This stops only the server on that port. Avoid `pkill -f canvas.py`, which also stops servers that other sessions or agents started.

## How mockup-canvas works

Each skill follows the workflow in its `SKILL.md`. See [docs/skill.md](docs/skill.md) for every step with its commands, the rules, and how to customize the skills.

### Draw (mockup-canvas)

1. **Find or create the idea.** If `design/<idea>/` already exists, the agent continues it. Otherwise it runs `canvas new <design dir> <idea>`, which also registers the design folder with the canvas server.
2. **Tokens first.** Colors, type, spacing, and radius go into `shared/tokens.css` before any screen is drawn. Artboards use only `var(--...)`.
3. **Draw artboards.** Each screen is one HTML file in `boards/`, named like `W01-Home.html`. It must look the same when opened on its own: relative paths only, no external scripts, Google Fonts as the only external resource.
4. **Register.** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile` places it on the canvas. If content is cut off, running `add` again with a new `--size` resizes the board.
5. **Link flows.** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "Open"` draws an arrow. State screens (empty, error, loading, no permission) are drawn, or only suggested when you fixed the number of screens.
6. **Check, render, overview.** `canvas check` must report 0 problems. The agent looks at the PNGs from `canvas render` (with `--full-page` for content below the fold) and `canvas overview` itself before showing you anything.
7. **Serve and share the URL.** `canvas serve` (registry mode, port 4400) shows every project from one server. The agent leaves it running and gives you the address.
8. **Phone viewing.** A static bundle from `canvas export` that the agent can upload to a private hosted page, or `canvas serve <design dir> --share` for live viewing on the same network.
9. **Keep old versions.** The agent never deletes on its own. Old screens move to an `old drafts` group and are marked `rejected`. When you ask for a delete, `canvas trash` moves the idea or board to `design/.trash/`, and `canvas restore` puts it back.
10. **Approval is the record.** When you approve a screen, the agent runs `canvas status ... approved --note "..."`. Simple praise is not approval.
11. **First-draft retrospective.** After the first full draft, the agent reviews how the work went (not the design) and lists at most three skill improvement suggestions. It never edits the skill without your approval.

### Review (mockup-review)

1. **Load the context:** the spec the screens were drawn from, `tokens.css`, `canvas.json`, and any earlier `review.md`.
2. **Machine checks:** `canvas check` and `canvas overview`. Every `check` problem becomes a finding.
3. **Per board and flow:** render each current board (also with `--full-page`), read its HTML, go through the checklist, and walk the links from the entry screen for dead ends and unreachable boards.
4. **Comment on the board:** one finding per `canvas comment`, starting with `[must]`, `[should]`, or `[could]`.
5. **Report:** write `design/<idea>/review.md` and recommend approve, revise, or reject per board. Setting status stays your decision.

The reviewer never edits artboards, tokens, or `canvas.json`. It works best in a different agent or session than the one that drew the screens.

### Build (mockup-to-code)

1. **Scope:** `canvas impl <idea dir>` lists the approved boards. Only those are built; if none is approved, the agent asks.
2. **Inspect the project:** framework, routing, styling, existing components and tokens, data contracts, and the test, lint, and dev server commands.
3. **Map tokens once, shell first:** board tokens are mapped into the app's token system in one place, then the shared layout, header, and navigation are built.
4. **Screen by screen:** one approved board per route, with its empty, loading, and error states as real states, wired to real data (stubs are marked and reported).
5. **Compare:** `canvas compare <idea dir> W01-Home.html --url http://localhost:5173/` writes `side.png`, `diff.png`, and `report.json` with the mismatch percent. The agent looks at the images, fixes, and compares again until every remaining difference is intentional and named.
6. **Record and check:** `canvas impl <idea dir> W01-Home.html --route / --file src/pages/Home.tsx`, then the project's tests, lint, and typecheck, and one polish pass over all screens.

### Example conversation

A shortened example. A request turns into screens on the canvas, one screen is approved and another revised, and the first draft ends with suggestions for improving the skill.

> **You:** Draw a mockup of a trail app for weekend hikers. Four screens.
>
> **Agent:** Created `design/trailmate/` and set the tokens first. Drew T01-Home, T02-TrailDetail, T03-Invite, and T04-Plan, and linked them in order. `check` reports 0 problems. Open `http://localhost:4400/myapp/trailmate/`. Since you asked for four screens, I did not draw these, but you may want them: an empty state for Home and an error state for Invite.
>
> **You:** Home is good. Make the map on the detail page larger.
>
> **Agent:** Marked T01-Home approved with the note "home feed composition". Moved the old T02 to "old drafts" as rejected and added T02-TrailDetail-v2 with a full-width map. The canvas has already reloaded.
>
> Skill improvement suggestions: 1. The map size was not in the request and had to be redrawn, one extra round, ask for the key element's size when a screen centers on a map or chart.

## CLI reference

Define a shell function first, pointing at wherever the skill lives:

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

Run `canvas <command> -h` for the usage of any command.

| Command | What it does | Example |
| --- | --- | --- |
| `serve` | Start the canvas server. No folder: registry mode, with the dashboard of every registered project. With a folder: that design folder only. `--port N` picks the port (default 4400). `--share` opens it to the local network with a token, `--minutes N` sets when it stops; in registry mode `--share --project NAME` shares one project. See [Run the server](#run-the-server). | `canvas serve`<br>`canvas serve design --share --minutes 30` |
| `roots list` | List registered design folders. | `canvas roots list` |
| `roots add` | Register a design folder, optionally with a name. | `canvas roots add ~/work/app/design --name app` |
| `roots remove` | Unregister a project by name. Files are not touched. | `canvas roots remove app` |
| `roots scan` | Find design folders under the given directories and register them. | `canvas roots scan ~/work ~/projects` |
| `new` | Create an idea folder (`boards/`, `shared/tokens.css`, `canvas.json`, ...) and register its design folder. | `canvas new design wallet` |
| `add` | Register an artboard on the canvas, copying it into `boards/` if needed. Sizes: `mobile` 390x844, `tablet` 768x1024, `desktop` 1440x900, or `WxH`. Run it again with a new `--size` to resize a registered board. | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | Move an artboard to a group. | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | Add a flow arrow between two artboards. | `canvas link design/wallet W01-Home.html W02-Send.html --label "Send"` |
| `status` | Set `draft`, `approved`, or `rejected`, with an optional note. | `canvas status design/wallet W01-Home.html approved --note "layout ok"` |
| `artifact` | Save the hosted page URL for an idea, or print it when no URL is given. | `canvas artifact design/wallet https://example.com/page` |
| `render` | Render artboards to PNG in `render/` with headless Chrome, at their registered size. All artboards when no file is given. `--full-page` captures the whole scroll height; `--wait MS` (default 1000) waits after the page load event. | `canvas render design/wallet W01-Home.html --full-page` |
| `overview` | Render the whole canvas, arrows and groups included, to `render/_overview.png`. | `canvas overview design/wallet` |
| `check` | Report missing files, broken references, unregistered boards, overlaps, dangling links, forbidden characters, and implementation files that do not exist. Also prints approval and comment counts. | `canvas check design/wallet` |
| `export` | Build a static, read-only canvas bundle: `index.html` plus boards, shared, and assets. The output folder must not be the idea folder, inside it, or contain it; symlinks pointing outside the idea folder are skipped. | `canvas export design/wallet ./wallet-export` |
| `snap` | Screenshot a running app page (http or https) with headless Chrome at exactly the given size (default `mobile`). `--wait MS` (default 3000) is real time after the page load event; `--full-page` captures the whole scroll height. | `canvas snap http://localhost:5173/ --size mobile --out home.png` |
| `compare` | Render a board at its registered size, capture the app at the same size (`--url`) or use a PNG (`--png`), and write `board.png`, `app.png`, `diff.png` (mismatches in magenta), `side.png` (board, app, and diff side by side), and `report.json` (with `mismatch_percent`) to `<idea>/compare/<board id>/`, or `--out DIR`. `--threshold N` (0 to 255, default 24) is how far a color channel may differ before a pixel counts; `--ignore-top N` and `--ignore-bottom N` leave bands out; `--align-top N` places the app N px down, below a fake status bar the board draws; `--wait MS` (default 3000). | `canvas compare design/wallet W01-Home.html --url http://localhost:5173/ --align-top 47` |
| `impl` | With a board: record the route and source files (relative to the project root) that implement it, or `--clear` the record. Without a board: list approved boards and whether each is implemented; `--strict` exits 1 when one is missing. | `canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx`<br>`canvas impl design/wallet --strict` |
| `comment` | Add a review comment to a board (`--by NAME` for the author), list its comments when no text is given, or remove them with `--clear`. | `canvas comment design/wallet W02-Send.html "[must] No error state" --by reviewer` |
| `trash` | Move an idea, or one board of it, to `<design dir>/.trash/`. A board keeps its canvas.json entry (position, group, status, comments) and its flow arrows in a sidecar file for restore. `--list` shows what is there. Nothing is ever removed for good; empty the folder by hand. | `canvas trash design/wallet W02-Send.html`<br>`canvas trash --list design` |
| `restore` | Put a trash entry back by its id (from `trash --list`). It refuses when something now has the same name. | `canvas restore design wallet/W02-Send-20261029T101034Z` |

## Canvas shortcuts

| Input | Action |
| --- | --- |
| Drag empty space | Pan |
| Mouse wheel, trackpad scroll or pinch | Zoom around the pointer |
| One-finger drag, two-finger pinch (touch) | Pan, zoom |
| `F` | Fit all artboards in view |
| `L` | Show or hide flow arrows |
| Click an artboard title | Copy its ID, for example `W01-Home` |
| Double-click an artboard title | Open the artboard alone in a new tab |
| Drag an artboard title | Move it and save the position |
| `Cmd+Z` / `Ctrl+Z` | Undo the last move |
| `Cmd+Shift+Z` / `Ctrl+Shift+Z`, or `Cmd+Y` / `Ctrl+Y` | Redo |
| Click a group header | Collapse or expand the group |
| Hover an artboard title | Show its note |
| Click a comment count | Open the board's comments; `Esc` closes them |
| `...` on an artboard title, or right-click the title | Board menu: open in a new tab, copy the file name, or delete the board (it moves to `design/.trash/`; the toast's Undo puts it back) |
| Open `.../<idea>/#<board>`, for example `#T01-Home` | Fit that one board in view (dashboard board results link here) |

Moving artboards is not available in a static export. In share mode, moves are saved only when the server was started with `--share-edit`.

## Folder layout

An idea lives inside your project, or in `~/design/` when there is no project:

```text
<project>/design/<idea>/
  canvas.json         layout, groups, flow arrows (links), status and notes, impl records, comments, artifact_url
  boards/*.html       artboards, one screen per file, e.g. W01-Home.html
  shared/tokens.css   colors, type, spacing, radius; every artboard links it
  assets/             images, fonts
  render/             generated PNGs for checking, and render/.thumbs/ for the canvas at low zoom
  compare/            compare output per board: board, app, diff, side PNGs and report.json
  review.md           the mockup-review report, when a review was run
```

`render/` and `compare/` are generated and ignored by git via the idea's `.gitignore`.

User data lives in `~/.mockup-canvas/`, or in the folder set by `MOCKUP_CANVAS_HOME`:

```text
~/.mockup-canvas/
  roots.json    registered design folders, used by registry mode
  config.json   options, e.g. {"forbidden_chars": ["—"]}
  backup/       anything install.sh moved out of the way
```

`forbidden_chars` is a list of characters that `canvas check` reports when they appear in an artboard. The agent also keeps them out of its documents and replies. Default: none.

## Security model

mockup-canvas is a local tool and is meant to stay one. Details are in [SECURITY.md](SECURITY.md).

- **Localhost only by default.** `canvas serve` binds to `127.0.0.1`.
- **Share mode is opt-in.** `--share` binds to the local network and requires a random token on every request (moved into an `HttpOnly; SameSite=Strict` cookie after the first visit). It is read-only unless you pass `--share-edit`, never allows registry changes, and stops after `--minutes` (1 to 240, default 30). A registry share serves the projects registered at start time (or one, with `--project NAME`) and hides folder paths and the management UI. Traffic is plain HTTP, so use it only on networks you trust.
- **Host check.** Every request must name this server in its `Host` header (`127.0.0.1`, `localhost`, or `[::1]` with the port, plus the LAN address in share mode); anything else gets `421`, which blocks DNS rebinding.
- **Path containment.** Only files inside a registered design folder are served. `../`, encoded traversal, absolute paths, and symlinks pointing outside are rejected.
- **Small write surface.** The only write on an idea changes `x` and `y` of an existing board in `canvas.json`, atomically, with a 64 KiB body limit.
- **CSRF checks.** Layout saves and registry changes require a same-origin `Origin` or `Referer` header and the exact media type `application/json`.
- **Sandboxed artboards.** Every file under `boards/`, `assets/`, and `shared/` is served with `Content-Security-Policy: sandbox`, and boards are shown in sandboxed iframes, so a board script cannot call the canvas API. Local fonts get CORS only for sandboxed boards. In share mode a board's asset link opens only its own idea.
- **Page CSP.** The dashboard and the canvas page carry a strict `Content-Security-Policy`: only their own inline scripts run (allowed by SHA-256 hash, no `unsafe-eval`), requests and frames stay on this server, and no other site can frame them.
- **Guarded renders.** Board renders and thumbnails cannot read local files outside the idea or reach localhost or private network addresses. Every connection, WebSockets included, goes through a guard proxy that resolves each name once and connects to the address it checked, so DNS rebinding cannot slip past. Headless Chrome is driven over a pipe, without a DevTools port, and exits when the canvas process ends.
- **Timeouts.** Each connection times out after 15 seconds (live-reload streams excepted) and at most 64 connections are served at once.
- **No outbound requests.** The tool itself contacts nothing on the internet. Artboards may load Google Fonts, the only external resource the skill allows. `snap` and `compare --url` open only the http or https address you give them and warn when it is not on localhost.

Report vulnerabilities privately through GitHub Security Advisories, not public issues.

## FAQ

### How do I get Claude Code to draw UI mockups before writing code?

Install the plugin with `/plugin marketplace add chrisjo-dev/mockup-canvas` and `/plugin install mockup-canvas@mockup-canvas`. Then ask in plain words, for example "Draw a mockup of a habit tracker app: home, add habit, and weekly stats." The agent creates `design/<idea>/`, draws each screen as an HTML artboard, checks and renders them, and gives you a local URL for the canvas. You approve or reject each screen there, and the `mockup-to-code` skill builds only the screens you approved.

### Is there a local, open-source alternative to Figma for reviewing AI-generated mockups?

mockup-canvas is one. It is MIT-licensed, the canvas server binds to `127.0.0.1` unless you turn on share mode, and the tool makes no outbound requests. The mockups are HTML files in your repository, so you can diff them and review them in a pull request without an account. It is not a vector design editor. The agent (or you) writes the HTML, and the canvas is where you arrange, link, review, comment on, and approve the screens.

### How can I check that AI-generated UI code matches the approved mockup?

Run `canvas compare <idea dir> <board> --url <running route>`. It renders the board, captures the app at the same size, and writes a diff image, a side-by-side image, and `report.json` with the mismatch percent. The `mockup-to-code` skill does this for every approved board, fixes differences, and compares again. `canvas impl <idea dir> --strict` exits with an error while an approved board has no recorded implementation.

### Why HTML instead of Figma?

An AI agent writes HTML and CSS well, and the result is a real file in your repo. You can diff it, review it in a pull request, and open it in any browser without an account. When you start building, the same markup and tokens are a short step from the real UI.

### Can it turn mockups into code?

Yes, that is what the `mockup-to-code` skill does. After you approve boards, the agent implements them with your app's own framework and components. It maps the mockup tokens into your token system instead of copying raw values. For each screen it runs `canvas compare` against the running route, looks at `side.png` and `diff.png`, fixes differences, and compares again until only intentional ones remain (real data instead of sample text, font rendering, platform controls). It records each board's route and files with `canvas impl`, so the canvas shows a `built` badge, and `canvas impl <idea dir> --strict` tells you which approved boards are still missing. The final report keeps what it verified apart from what it could not.

### How accurate is compare?

`compare` is a pixel comparison, not a judgment. A pixel counts as different when any color channel differs by more than the threshold (default 24 of 255, set with `--threshold`), and `mismatch_percent` is the share of differing pixels in the compared rows. As a rough guide, under about 2% is usually font rendering and antialiasing, 2% to 10% usually means spacing, line height, or a missing element, and above 10% usually means a shifted layout. Mockups often draw a fake phone status bar or home indicator that the real app does not render. Use `--align-top N` to place the app below the bar, or `--ignore-top N` and `--ignore-bottom N` to leave those bands out. Treat the percentage as a guide and always look at `side.png` and `diff.png`. The skill never claims a screen matches based on the number alone.

### Does it need internet access?

No. The server, canvas, and CLI run offline. Only artboards that use Google Fonts need a connection to load those fonts. Installing the plugin needs access to GitHub.

### Does it work on Windows or Linux?

Linux should work; Windows is untested. The server and canvas use only the Python standard library. Rendering and capturing PNGs (`render`, `overview`, `snap`, `compare`, and the canvas thumbnails) needs Chrome, Chromium, or Edge, which the CLI looks for in this order:

1. The `MOCKUP_CANVAS_CHROME` environment variable.
2. The macOS app paths for Google Chrome, Chromium, and Microsoft Edge in `/Applications`.
3. `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `msedge`, and `chrome` on `PATH`.

If your browser is somewhere else, point to it:

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh` needs a POSIX shell (bash), so on Windows install through the Claude Code plugin instead.

### Which AI agents does mockup-canvas support?

mockup-canvas ships as a Claude Code plugin and as skills for Claude Code and OpenAI Codex (call them with `$mockup-canvas`, `$mockup-review`, or `$mockup-to-code` in Codex). The skills only run the `canvas.py` CLI, so any agent that can run shell commands can follow the same steps.

### How is mockup-canvas different from Figma, v0, or Claude Artifacts?

mockup-canvas is not a hosted design tool or app generator. It handles planning, review, and building, and everything stays in files you own. Every mockup is a local HTML file in your repository, the canvas is served from `127.0.0.1`, and the tool makes no outbound requests. Approvals with notes, review comments, and implementation records live in `canvas.json`, so you have a history of what was approved, rejected, and built. The built screens are checked against the approved mockups. It works with any agent that can run a CLI.

### Can I use it without an AI agent?

Yes. Write the HTML files yourself and use the CLI: `canvas new`, `canvas add`, `canvas link`, `canvas serve`, and later `canvas compare` and `canvas impl` for your own implementation. The skills only automate those same commands.

## Contributing

Issues and pull requests are welcome. Run the test suite (260 tests) before you open a pull request:

```bash
cd tests && python3 -m unittest discover .
```

Render tests are skipped when Chrome is not found. `python3 tests/perf_check.py` measures canvas frame times, long tasks, and time to the fit view in headless Chrome; it is not part of the unit suite.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the end-to-end suite, the performance check, commit style, and how to propose UI changes by drawing them on the canvas first. Changes per release are in [CHANGELOG.md](CHANGELOG.md).

## License

mockup-canvas is released under the [MIT License](LICENSE). Copyright (c) 2026 chrisjo-dev.
