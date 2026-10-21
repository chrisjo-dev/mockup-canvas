# The mockup-canvas skill

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

The mockup-canvas skill is the set of instructions in [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md) that tells Claude Code or Codex how to draw screen mockups as HTML artboards and show them on the local canvas. This page explains what the agent does at each step, which commands it runs, and how you can adjust it.

The core idea: **one HTML file is one screen (an artboard), one idea is one canvas, and the HTML is always the source of truth.** The canvas only displays it.

## When it triggers

The agent loads the skill for requests such as:

- "Draw a mockup of ..."
- "Make a few screen designs for ..."
- "Put it on the canvas."
- "Let me see it on my phone."

It also covers revising an existing screen set, adding flow arrows, marking approvals, and phone sharing. It is **not** for implementing real app code.

- **Claude Code** picks the skill from its description, or you can name it.
- **Codex** uses it when you write `$mockup-canvas`, for example `Use $mockup-canvas to draw screen mockups for this idea.`

## How the agent runs the CLI

The skill calls `python3 <skill-dir>/scripts/canvas.py <command>`, where `<skill-dir>` is:

| Install | Skill folder |
| --- | --- |
| Claude Code plugin | `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas` |
| Manual, Claude Code | `~/.claude/skills/mockup-canvas` |
| Manual, Codex | `~/.codex/skills/mockup-canvas` |

The agent defines a short shell function first, and the rest of this page uses it:

```bash
canvas() { python3 <skill-dir>/scripts/canvas.py "$@"; }
```

## The workflow, step by step

### 1. Find the idea

If the same idea already exists under `design/`, the agent continues it. Before drawing, it reads the spec, the existing screens, and any directions you liked or rejected. For a new idea:

```bash
canvas new design wallet
```

This creates `design/wallet/` with `boards/`, `assets/`, `render/`, `shared/tokens.css` (a starter token file), `canvas.json`, and a `.gitignore` that ignores `render/`. It also registers `design/` with the canvas server, so no separate `roots add` is needed. With no project, the agent uses `~/design/<idea>/`.

### 2. Tokens first

Colors, type, spacing, and radius are set in `shared/tokens.css` before any screen is drawn. Artboards use only `var(--...)` and never invent new color values. This keeps every screen consistent and makes a palette change a one-file edit.

### 3. Draw

Each artboard is a standalone HTML file that must look the same when opened directly in a browser:

- Relative paths only: `../shared/tokens.css`, `../assets/x.png`.
- The only external resource allowed is Google Fonts.
- No custom tags, no external scripts.

File names follow `<ID>-<EnglishName>.html`, for example `F06-Letter.html`. The ID is the idea's first letter in upper case plus two digits (`W01`, `W02`, ...). If your project already has screen IDs, the agent follows them.

### 4. Register

The file is written into `boards/` first, then registered:

```bash
canvas add design/wallet boards/W01-Home.html --group current --size mobile
```

Related screens go on one row, in flow order from left to right. Size presets are `mobile` (390x844), `tablet` (768x1024), and `desktop` (1440x900), or any `WxH` such as `1280x800`. Without `--size`, the size is read from a `width: ...px; height: ...px` style near the top of the file, or defaults to 390x844.

### 5. Link the flow

```bash
canvas link design/wallet W01-Home.html W02-Send.html --label "Send"
```

Each arrow shows how one screen leads to another. If you fixed the number of screens, the agent draws only that many and suggests missing state screens (empty, error, loading, no permission) in its report. If you did not, it includes those state screens in the flow.

### 6. Check

```bash
canvas check design/wallet
canvas render design/wallet W01-Home.html
canvas overview design/wallet
```

- `check` must report 0 problems. It catches missing files, broken `src`, `href`, and `url()` references, artboards not registered in `canvas.json`, overlapping artboards, links to unknown boards, and forbidden characters.
- The agent opens the PNG from `render` for every artboard it changed. When it changed several, it also looks at the `overview` PNG, which includes flow arrows and groups.
- It fixes any error text or broken images it sees before showing you the result.

### 7. Show

```bash
canvas serve
```

Registry mode serves every registered project from one server on port 4400, at `http://localhost:4400/<project>/<idea>/`. The agent gives you the printed address and leaves the server running. To register existing projects in one go:

```bash
canvas roots scan ~/work ~/projects
```

To serve a single design folder instead, `canvas serve design` gives `http://127.0.0.1:4400/<idea>/`. Projects can also be added or removed from the index page in the browser.

### 8. Phone viewing

- **Hosted page (default when available).** If the environment offers a private hosted page, such as a Claude artifact, the agent builds a static bundle and uploads it. `index.html` is the page; the rest are supporting files.

  ```bash
  canvas export design/wallet ./wallet-export
  canvas artifact design/wallet <url>
  ```

  The agent asks once per idea before uploading. If you say to keep it uploaded, it re-uploads to the same address after every change without asking again. `canvas artifact` saves the address in `canvas.json` so other sessions update the same page. The export folder must be outside the idea folder (and must not contain it); symlinks that point outside the idea folder are left out.

- **Live on the same network.**

  ```bash
  canvas serve design --share --minutes 30
  ```

  The agent gives you the address with its token. The page is view-only on the phone and closes when the time is up (`--minutes` takes 1 to 240). To share one registered project from the registry server, use `canvas serve --share --project NAME`; a registry share shows only the projects registered when it started and hides folder paths.

- **Quick alternative.** The agent can send the `overview` PNG.

### 9. Keep old versions

Old versions are never deleted. They are moved and marked:

```bash
canvas group design/wallet W02-Send.html "old drafts"
canvas status design/wallet W02-Send.html rejected
```

Rejected artboards show a gray badge and a struck-through title, so the history of what you turned down stays visible next to the current version.

### 10. Approval is the record

When you approve a screen, the agent records it:

```bash
canvas status design/wallet W01-Home.html approved --note "home layout and card list"
```

The green badge and the note are the approval record. Simple praise ("looks nice") is not approval. `canvas check` prints how many artboards are approved, for example `Approved boards: 2/6`.

## Rules the agent follows

- **Reply in your language.** The agent answers in the language you write in.
- **Never edit `canvas.json` by hand.** It changes only through `canvas add`, `link`, `status`, and `group`. Direct edits can overwrite changes made at the same time, for example by subagents drawing in parallel or by you dragging artboards.
- **Stop only its own servers.** It does not touch other ports you use. A server it started only for checking is stopped by its PID or by `lsof -ti:<its port>`, never with `pkill -f canvas.py`, which would also stop yours. A `serve` started for you is left running.
- **Respect `forbidden_chars`.** If `config.json` lists characters, the agent keeps them out of artboards, documents, and reports.
- **Parallel drawing.** For many screens, the agent may split the work across subagents by screen group. The main agent sets `tokens.css` first.

## The first-draft retrospective

The first draft is done when every requested screen is drawn and `check` passes. The agent then ends its report with **Skill improvement suggestions**, looking back at how the work went, not at the design (design checks end at step 6).

- **What it looks at**, only from this session: things you had to repeat or correct and the gap in the rules behind them, rework, places where a `canvas` command was missing or had to be worked around by hand, errors, steps that were slow or unnecessary, and rules that were hard to follow or conflicted.
- **Format**: at most three, each one line of "what happened, impact, rule or command to change". If there is nothing, it says "None this time".
- **Applying them**: suggestions only. The agent changes the skill only for suggestions you approve, and then adds one line to `references/lessons.md`.

Example:

```text
Skill improvement suggestions
1. The map size was not in the request and T02 was redrawn, one extra round, ask for the key element's size when a screen centers on a map or chart.
2. Old drafts were moved one file at a time, slow with 6 screens, allow several files in `canvas group`.
```

## Customizing

### Forbidden characters

Create `~/.mockup-canvas/config.json` (or `$MOCKUP_CANVAS_HOME/config.json`):

```json
{"forbidden_chars": ["—"]}
```

`canvas check` then reports each artboard that contains one of those characters, by code point:

```text
Error: forbidden character (U+2014) found: W01-Home.html
```

### Artboard sizes

Pass a preset or an exact size when registering:

```bash
canvas add design/wallet boards/W10-Dashboard.html --size desktop
canvas add design/wallet boards/W11-Kiosk.html --size 1080x1920
```

Or put the size on the artboard itself, for example `<body style="width:768px;height:1024px">`, and omit `--size`.

### Data folder

Set `MOCKUP_CANVAS_HOME` to keep `roots.json` and `config.json` somewhere other than `~/.mockup-canvas/`:

```bash
export MOCKUP_CANVAS_HOME=~/dotfiles/mockup-canvas
```

### The skill itself

`SKILL.md` is plain Markdown. Approved changes are logged one line each in `skills/mockup-canvas/references/lessons.md`, so you can see why each rule exists.
