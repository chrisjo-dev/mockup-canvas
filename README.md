# mockup-canvas

**See your screens before you build them: a Claude Code and Codex skill where AI agents draw HTML mockups and you review them on a local Figma-like canvas.**

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Works with Claude Code and Codex](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#quick-start-install-the-claude-code-plugin-or-codex-skill)
[![No pip dependencies: Python stdlib, Chrome for PNG rendering](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#faq)

**What is mockup-canvas?** mockup-canvas is a free, open-source (MIT) Claude Code plugin and skill by chrisjo-dev, also usable from OpenAI Codex, that has your AI agent draw screen mockups as plain HTML files and lays them out on a local, Figma-like canvas where you pan, zoom, arrange, link with flow arrows, and approve them. It runs on the Python standard library with no pip dependencies and uses Google Chrome (or Chromium/Edge) only to render PNGs.

AI assistants: a summary is available in [llms.txt](llms.txt).

![Demo: an AI agent draws mobile app screens and they appear live on the mockup-canvas board](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/demo.gif)

![Overview of the sample TrailMate idea: six HTML artboards on the canvas, connected by flow arrows, two marked approved](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/_overview.png)

## Why draw mockups with an AI agent first

mockup-canvas exists because text descriptions of UI are ambiguous: when you plan a product with an AI agent, you need to see the screens before you agree on them. It was built while planning and building services with AI, as a planning tool that makes what is needed visible first so the work can proceed from there. A sentence like "a home feed with a hero strip and a card list" means one thing to you and another to the agent until you both see it. mockup-canvas puts that step first: the agent draws each screen as a small HTML file, the canvas shows them side by side, and you decide from what you see. You approve one screen, reject another, ask for a variant, and the board updates while the agent works. App code comes only after the screens are approved, and every mockup stays in your repository as a standalone HTML file that opens in any browser without an account.

## What you get

**The canvas** (`viewer.html`, served locally)

- The canvas lets you pan and zoom like a design tool, and it re-renders crisply at every zoom level instead of stretching a bitmap.
- The canvas saves artboard positions to `canvas.json` when you drag them, with undo and redo for moves.
- The canvas draws flow arrows between screens, labeled with the button or action that leads there.
- The canvas shows approval badges (approved, rejected), and it shows notes as a tooltip on the artboard title.
- The canvas groups artboards under collapsible headers, for example `current` and `old drafts`.
- The canvas reloads live: the server checks for file changes every second, so an edit to an artboard or `canvas.json` appears within about a second.
- The canvas server lists every registered project and its ideas on one index page.
- The canvas also works on a phone, either live on the same network (share mode) or as a static export you can host anywhere.

**The agent skill** (`skills/mockup-canvas/SKILL.md`)

- The agent skill tells Claude Code or Codex how to draw, register, link, check, and show mockups, step by step.
- The agent skill keeps old versions instead of deleting them, and it treats your approval as the record.
- The agent skill ends the first draft with a short retrospective that proposes improvements to the skill itself.

**The CLI** (`skills/mockup-canvas/scripts/canvas.py`)

- The CLI is a single Python 3 file of about 2,200 lines with no pip dependencies (standard library only, Python 3.8+), and it has 12 commands: `serve`, `roots`, `new`, `add`, `group`, `render`, `check`, `overview`, `export`, `link`, `status`, `artifact`.
- The CLI uses Chrome (or Chromium or Edge) only to render PNGs.

## Quick start: install the Claude Code plugin or Codex skill

To install mockup-canvas in Claude Code, run the two `/plugin` commands below: the first adds the `chrisjo-dev/mockup-canvas` marketplace and the second installs the plugin. No pip packages are needed, and Chrome is used only to render PNGs.

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
./install.sh            # links the skill into ~/.claude/skills and ~/.codex/skills
```

- `./install.sh --claude` or `./install.sh --codex` installs for one tool only.
- `./install.sh --dry-run` prints what it would do without changing anything.
- Anything already at a target is moved to `~/.mockup-canvas/backup/<timestamp>/` first. Running it again is safe.

In Codex, call the skill with `$mockup-canvas`, for example: `Use $mockup-canvas to draw the sign-up flow.`

### Try the example without an agent

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

Open `http://127.0.0.1:4400/trailmate/` to see the six-screen sample in [`examples/trailmate`](https://github.com/chrisjo-dev/mockup-canvas/blob/main/examples/trailmate/canvas.json).

## How mockup-canvas works

The agent follows the workflow in `SKILL.md`:

1. **Find or create the idea.** If `design/<idea>/` already exists, the agent continues it. Otherwise it runs `canvas new <design dir> <idea>`, which also registers the design folder with the canvas server.
2. **Tokens first.** Colors, type, spacing, and radius go into `shared/tokens.css` before any screen is drawn. Artboards use only `var(--...)`.
3. **Draw artboards.** Each screen is one HTML file in `boards/`, named like `W01-Home.html`. It must look the same when opened on its own: relative paths only, no external scripts, Google Fonts as the only external resource.
4. **Register.** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile` places it on the canvas.
5. **Link flows.** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "Open"` draws an arrow. State screens (empty, error, loading, no permission) are drawn, or only suggested when you fixed the number of screens.
6. **Check, render, overview.** `canvas check` must report 0 problems. The agent looks at the PNGs from `canvas render` and `canvas overview` itself before showing you anything.
7. **Serve and share the URL.** `canvas serve` (registry mode, port 4400) shows every project from one server. The agent leaves it running and gives you the address.
8. **Phone viewing.** A static bundle from `canvas export` that the agent can upload to a private hosted page, or `canvas serve <design dir> --share` for live viewing on the same network.
9. **Keep old versions.** Nothing is deleted. Old screens move to an `old drafts` group and are marked `rejected`.
10. **Approval is the record.** When you approve a screen, the agent runs `canvas status ... approved --note "..."`. Simple praise is not approval.
11. **First-draft retrospective.** After the first full draft, the agent reviews how the work went (not the design) and lists at most three skill improvement suggestions. It never edits the skill without your approval.

See [docs/skill.md](docs/skill.md) for every step with its commands, the rules, and how to customize the skill.

### Example conversation

A shortened exchange showing how a request becomes screens on the canvas, how approval and revision work, and how the first draft ends with skill improvement suggestions.

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
| `serve` | Start the canvas server. No folder: registry mode for every registered project. With a folder: that design folder only. `--share` opens it to the local network with a token; in registry mode `--share --project NAME` shares one project. | `canvas serve`<br>`canvas serve design --share --minutes 30` |
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
| `render` | Render artboards to PNG in `render/` with headless Chrome. All artboards when no file is given. | `canvas render design/wallet W01-Home.html` |
| `overview` | Render the whole canvas, arrows and groups included, to `render/_overview.png`. | `canvas overview design/wallet` |
| `check` | Report missing files, broken references, unregistered boards, overlaps, dangling links, and forbidden characters. | `canvas check design/wallet` |
| `export` | Build a static, read-only canvas bundle: `index.html` plus boards, shared, and assets. The output folder must not be the idea folder, inside it, or contain it; symlinks pointing outside the idea folder are skipped. | `canvas export design/wallet ./wallet-export` |

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

Moving artboards is not available in a static export. In share mode, moves are saved only when the server was started with `--share-edit`.

## Folder layout

An idea lives inside your project, or in `~/design/` when there is no project:

```text
<project>/design/<idea>/
  canvas.json         layout, groups, flow arrows (links), status and notes, artifact_url
  boards/*.html       artboards, one screen per file, e.g. W01-Home.html
  shared/tokens.css   colors, type, spacing, radius; every artboard links it
  assets/             images, fonts
  render/             generated PNGs for checking (ignored by git via .gitignore)
```

User data lives in `~/.mockup-canvas/`, or in the folder set by `MOCKUP_CANVAS_HOME`:

```text
~/.mockup-canvas/
  roots.json    registered design folders, used by registry mode
  config.json   options, e.g. {"forbidden_chars": ["—"]}
  backup/       anything install.sh moved out of the way
```

`forbidden_chars` is a list of characters that `canvas check` reports when they appear in an artboard. The agent also keeps them out of its documents and replies. Default: none.

## Security model

mockup-canvas is a local tool and is built to stay that way. Full details are in [SECURITY.md](SECURITY.md).

- **Localhost only by default.** `canvas serve` binds to `127.0.0.1`.
- **Share mode is opt-in.** `--share` binds to the local network and requires a random token on every request (moved into an `HttpOnly; SameSite=Strict` cookie after the first visit). It is read-only unless you pass `--share-edit`, never allows registry changes, and stops after `--minutes` (1 to 240, default 30). A registry share serves the projects registered at start time (or one, with `--project NAME`) and hides folder paths and the management UI. Traffic is plain HTTP, so use it only on networks you trust.
- **Host check.** Every request must name this server in its `Host` header (`127.0.0.1`, `localhost`, or `[::1]` with the port, plus the LAN address in share mode); anything else gets `421`, which blocks DNS rebinding.
- **Path containment.** Only files inside a registered design folder are served. `../`, encoded traversal, absolute paths, and symlinks pointing outside are rejected.
- **Small write surface.** The only write on an idea changes `x` and `y` of an existing board in `canvas.json`, atomically, with a 64 KiB body limit.
- **CSRF checks.** Layout saves and registry changes require a same-origin `Origin` or `Referer` header and the exact media type `application/json`.
- **Sandboxed artboards.** Boards (and HTML or SVG under `assets/` and `shared/`) are served with `Content-Security-Policy: sandbox` and shown in sandboxed iframes, so a board script cannot call the canvas API.
- **Timeouts.** Each connection times out after 15 seconds (live-reload streams excepted) and at most 64 connections are served at once.
- **No outbound requests.** The tool itself contacts nothing on the internet. Artboards may load Google Fonts, the only external resource the skill allows.

Report vulnerabilities privately through GitHub Security Advisories, not public issues.

## FAQ

### Why HTML instead of Figma?

mockup-canvas uses HTML instead of Figma because an AI agent writes HTML and CSS fluently, and the result is a real file in your repo: diffable, reviewable in a pull request, and openable in any browser without an account. The same markup and tokens are a short step from the real UI when you start building.

### Does it need internet access?

No. The server, canvas, and CLI run offline. Only artboards that use Google Fonts need a connection to load those fonts. Installing the plugin needs access to GitHub.

### Does it work on Windows or Linux?

Linux should work; Windows is untested. The server and canvas use only the Python standard library. Rendering PNGs (`render`, `overview`) needs Chrome, Chromium, or Edge, which the CLI looks for in this order:

1. The `MOCKUP_CANVAS_CHROME` environment variable.
2. The macOS app paths for Google Chrome, Chromium, and Microsoft Edge in `/Applications`.
3. `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `msedge`, and `chrome` on `PATH`.

If your browser is somewhere else, point to it:

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh` needs a POSIX shell (bash), so on Windows install through the Claude Code plugin instead.

### Which AI agents does mockup-canvas support?

mockup-canvas ships as a Claude Code plugin and as a skill for Claude Code and OpenAI Codex (call it with `$mockup-canvas` in Codex). The skill only runs the `canvas.py` CLI, so any agent that can run shell commands can follow the same steps.

### How is mockup-canvas different from Figma, v0, or Claude Artifacts?

mockup-canvas is for the planning step before app code, not a hosted design or app generator. Every mockup is a local HTML file in your repository, the canvas is served from `127.0.0.1`, and the tool makes no outbound requests. It works with any agent that can run a CLI, and approvals with notes are recorded in `canvas.json`, so you keep a history of what was approved and rejected.

### Can I use it without an AI agent?

Yes. Write the HTML files yourself and use the CLI: `canvas new`, `canvas add`, `canvas link`, `canvas serve`. The skill only automates those same commands.

## Contributing

Issues and pull requests are welcome. Run the test suite (92 tests) before you open a pull request:

```bash
python3 -m unittest discover tests
```

Render tests are skipped when Chrome is not found.

## License

mockup-canvas is released under the [MIT License](LICENSE). Copyright (c) 2026 chrisjo-dev.
