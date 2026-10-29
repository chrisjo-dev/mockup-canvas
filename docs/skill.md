# The mockup-canvas skills

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas ships three skills that share one CLI:

| Skill | Instructions | Job |
| --- | --- | --- |
| mockup-canvas | [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md) | Draw screen mockups as HTML artboards and show them on the local canvas. |
| mockup-review | [`skills/mockup-review/SKILL.md`](../skills/mockup-review/SKILL.md) | Review drawn screens and leave findings as comments on the boards. |
| mockup-to-code | [`skills/mockup-to-code/SKILL.md`](../skills/mockup-to-code/SKILL.md) | Build approved boards in your app and compare each screen with its board. |

This page explains what the agent does at each step, which commands it runs, and how you can adjust it. The [mockup-review](#the-mockup-review-skill) and [mockup-to-code](#the-mockup-to-code-skill) sections follow the mockup-canvas workflow.

The core idea: **one HTML file is one screen (an artboard), one idea is one canvas, and the HTML is always the source of truth.** The canvas only displays it.

## When it triggers

The agent loads the skill for requests such as:

- "Draw a mockup of ..."
- "Make a few screen designs for ..."
- "Put it on the canvas."
- "Let me see it on my phone."

It also covers revising an existing screen set, adding flow arrows, marking approvals, and phone sharing. It is **not** for critiquing finished screens (that is mockup-review) or for implementing real app code (that is mockup-to-code).

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

This creates `design/wallet/` with `boards/`, `assets/`, `render/`, `shared/tokens.css` (a starter token file), `canvas.json`, and a `.gitignore` that ignores `render/` and `compare/`. It also registers `design/` with the canvas server, so no separate `roots add` is needed. With no project, the agent uses `~/design/<idea>/`.

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

Related screens go on one row, in flow order from left to right. Size presets are `mobile` (390x844), `tablet` (768x1024), and `desktop` (1440x900), or any `WxH` such as `1280x800`. Without `--size`, the size is read from a `width: ...px; height: ...px` style near the top of the file, or defaults to 390x844. If a board's content is cut off, the agent runs `add` again with a new `--size` instead of trimming the content.

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
- The agent opens the PNG from `render` for every artboard it changed. Renders are exactly the board size; `render --full-page` captures content below the fold. When it changed several, it also looks at the `overview` PNG, which includes flow arrows and groups.
- It fixes any error text or broken images it sees before showing you the result.

### 7. Show

```bash
canvas serve
```

Registry mode serves every registered project from one server on port 4400: `http://localhost:4400/` is the dashboard of all projects and ideas, and `http://localhost:4400/<project>/<idea>/` is one idea's canvas. The agent gives you the printed address and leaves the server running. To register existing projects in one go:

```bash
canvas roots scan ~/work ~/projects
```

To serve a single design folder instead, `canvas serve design` gives `http://127.0.0.1:4400/<idea>/`. Projects can also be added, renamed, or removed on the dashboard in the browser. See [Run the server](../README.md#run-the-server) for ports, phone sharing, and running it in the background.

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

The agent deletes only when you ask. Then `canvas trash` moves the idea or board to `design/.trash/`, and `canvas restore` puts it back. The dashboard (Delete idea) and the canvas (the `...` on a board title) do the same, with an Undo in the toast.

### 10. Approval is the record

When you approve a screen, the agent records it:

```bash
canvas status design/wallet W01-Home.html approved --note "home layout and card list"
```

The green badge and the note are the approval record. Simple praise ("looks nice") is not approval. `canvas check` prints how many artboards are approved, for example `Approved boards: 2/6`.

## Rules the agent follows

- **Reply in your language.** The agent answers in the language you write in.
- **Never edit `canvas.json` by hand.** It changes only through `canvas add`, `link`, `status`, `group`, `impl`, and `comment`. Direct edits can overwrite changes made at the same time, for example by subagents drawing in parallel or by you dragging artboards.
- **Stop only its own servers.** It does not touch other ports you use. A server it started only for checking is stopped by its PID or by `lsof -ti:<its port>`, never with `pkill -f canvas.py`, which would also stop yours. A `serve` started for you is left running.
- **Respect `forbidden_chars`.** If `config.json` lists characters, the agent keeps them out of artboards, documents, and reports.
- **Parallel drawing.** For many screens, the agent may split the work across subagents by screen group. The main agent sets `tokens.css` first.
- **A one-time star offer.** After the first finished task on a machine, any of the three skills may end its reply by asking whether you would like it to star mockup-canvas on GitHub (a star helps others find it). It stars only if you say yes, with your signed-in `gh`, or gives you the link. It then creates `${MOCKUP_CANVAS_HOME:-~/.mockup-canvas}/.star-hint-shown` and never mentions it again (create that file yourself to turn it off).

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

## The mockup-review skill

mockup-review reviews an idea the way a second designer would: it checks every artboard and the flow between them, leaves each finding on the board it belongs to, and writes one summary. **The reviewer reports; it does not fix.** It works best when run by a different agent or session than the one that drew the screens, because a fresh context does not share the author's assumptions. If the same session drew the screens, the report says so.

### When it triggers

- "Review the mockups."
- "Check the screens."
- "Critique this design."
- "Is anything missing?"

It applies to screens already drawn under `design/<idea>/`. In Codex, call it with `$mockup-review`. It uses the `canvas.py` script of the sibling mockup-canvas skill (`../mockup-canvas/scripts/canvas.py` from its own folder) and stops if that skill is not installed.

### Steps

1. **Load the context.** The agent finds the idea folder and reads the brief or spec the screens were drawn from, `shared/tokens.css`, `canvas.json` (groups, links, status, notes), and any existing `review.md`. Without a spec, it reviews against the screens alone and says so.
2. **Machine checks.** Every problem `canvas check` reports becomes a finding. The agent also looks at the `canvas overview` PNG for arrows, groups, and screens that sit alone.
3. **Per board.** For each board in the current group (rejected boards and "old drafts" are skipped unless you ask), it renders the board, looks at the PNG, reads the HTML, and goes through `references/checklist.md`: state coverage, flow, token consistency, accessibility basics, mobile thumb reach, copy, and spec match. It uses `--full-page` to see content below the fold before judging it.

   ```bash
   canvas render design/wallet W02-Send.html --full-page
   ```

4. **Flow.** It walks the links from the entry screen. Every button or link on a board should lead to a board on the canvas or be a stated end of the flow. Dead ends, unreachable boards, and links to missing boards are findings.
5. **Spec match.** A required feature with no screen, or a screen that contradicts the spec, is a finding.
6. **Comment on the board.** One finding per comment, on the exact board it concerns, starting with a severity tag:

   ```bash
   canvas comment design/wallet W02-Send.html "[must] No error state for a failed transfer; spec 3.2 requires a retry" --by reviewer
   ```

   | Tag | Meaning |
   | --- | --- |
   | `[must]` | Blocks approval: broken flow, missing required state, spec contradiction, unreadable text, a `check` problem. |
   | `[should]` | A clear problem worth fixing before implementation. |
   | `[could]` | Optional improvement. |

   Before adding, it lists existing comments with `canvas comment <idea dir> <file>` so it does not repeat them. On the canvas, the board then shows a comment count that opens the comment panel.

7. **Summary report.** It writes `design/<idea>/review.md` from `references/review-template.md`. If one exists, it adds a new dated section at the top instead of overwriting.
8. **Recommend status, do not set it.** The report recommends `approve`, `revise`, or `reject` per board with a one-line reason. Approval stays your decision.

The reply to you lists the number of findings by severity, the top three `[must]` items with their board IDs, the status recommendations, the path to `review.md`, and what was checked versus what could not be checked (for example motion or a screen size that was not drawn).

### Rules

- **No edits.** The reviewer never changes artboards, `tokens.css`, assets, or `canvas.json`, not even a typo. It reports instead.
- **No approvals.** It never marks boards approved or rejected for you.
- **Reasons, not taste.** Every finding needs a basis: a checklist rule, the spec, a token, or a concrete user problem.
- **Clearing comments.** `canvas comment ... --clear` is used only on comments it wrote in this session, and only when you ask.
- **Language.** Replies follow your language; comments and `review.md` follow the spec's language, or yours when there is no spec. `forbidden_chars` are kept out of comments and the report.
- **Servers.** It does not start, stop, or reuse servers you run. One started only for checking is stopped by PID or `lsof -ti:<port>`.

### First-review retrospective

The first review is done when every current board has been checked, findings are on the boards, and `review.md` is written. The report then ends with **Skill improvement suggestions**, in the same form as the [first-draft retrospective](#the-first-draft-retrospective): at most three one-line items about how the work went, not about the design. Approved changes are logged in `skills/mockup-review/references/lessons.md`.

## The mockup-to-code skill

mockup-to-code implements approved boards as real screens in your app, then compares each running route with its board until only intentional differences remain. **The approved boards are the visual spec; your app's framework, components, and data are the material.**

### When it triggers

- "Build the approved mockups."
- "Implement the approved screens."
- "Turn the mockup into code."
- "Make the app match the canvas."

In Codex, call it with `$mockup-to-code`. Like mockup-review, it uses the sibling mockup-canvas `canvas.py`. `snap` and `compare` need Chrome, like `render`.

### Steps

1. **Scope is approved boards only.** The agent lists them:

   ```bash
   canvas impl design/wallet
   ```

   Only boards marked `approved` with `canvas status` are in scope. Praise is not approval; if no board is approved, the agent stops and asks which boards you approve. It reads each board's status note and any comments on it.
2. **Inspect the project before writing code.** Framework and version, routing, styling system (CSS variables, Tailwind, CSS modules, a UI kit), existing components and tokens, data layer and API contracts, and the test, lint, typecheck, and dev server commands, plus the project's own instructions (README, AGENTS.md, CLAUDE.md).
3. **Map tokens once.** `shared/tokens.css` is translated into the app's token system in one place (`references/stack-notes.md` has tips per stack). Components use tokens only; no hex, pixel font size, or radius is copied from an artboard.
4. **Shared shell first.** Layout frame, header, navigation, tab bar, page width, and breakpoints come before any single screen.
5. **Screen by screen.** One approved board at a time, on its route. A part that appears on a second board becomes a component. Empty, loading, and error states become real states of the screen, not separate pages.
6. **Real behavior, real data.** Screens use the existing data contracts. Where the backend is not ready, a clearly marked stub (`TODO(mockup-to-code)`) is used and listed in the report. Existing behavior, validation, routing, analytics, and accessibility are kept.
7. **Compare each screen.** With the app's dev server running on a free port:

   ```bash
   canvas compare design/wallet W01-Home.html --url http://localhost:5173/
   ```

   This writes `board.png`, `app.png`, `diff.png`, `side.png`, and `report.json` (with `mismatch_percent`) to `design/wallet/compare/W01-Home/`. The agent looks at `side.png` and `diff.png` itself, fixes layout, spacing, type, color, and missing elements, and compares again. It stops when every remaining difference is intentional (real data, font rendering, antialiasing, a platform control) and it can name each one.

   | Situation | What to do |
   | --- | --- |
   | The board draws a fake status bar the app does not render | `--align-top N` (N is the bar height, often 44 to 54 px); never add a fake bar to the app |
   | The app starts at the top but a band differs | `--ignore-top N` or `--ignore-bottom N` (for a drawn home indicator) |
   | The app fetches data or animates in | Raise `--wait MS` (default 3000) |
   | An extra size or state has no board | `canvas snap <url> --size mobile --out FILE.png` |

   As a guide, under about 2% is usually font rendering and antialiasing, 2% to 10% usually spacing, line height, or a missing element, and above 10% usually a shifted layout. The percentage is a guide, not the goal.
8. **Record the implementation.**

   ```bash
   canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx --file src/components/TabBar.tsx
   canvas impl design/wallet --strict
   ```

   The canvas then shows a `built` badge on the board. `--strict` exits 1 while any approved board has no implementation; `--clear` resets a wrong record.
9. **Project checks.** Tests, lint, and typecheck. A passing build does not prove the screen matches the board, and a matching screenshot does not prove the behavior works; the report covers both.
10. **One polish pass.** After all in-scope screens are done, one pass over alignment, spacing rhythm, type scale, states, focus and hover, and responsive behavior across all screens, then `compare` again for screens it changed. General rules never override what you chose on an approved board.
11. **Stop its own servers** by PID or `lsof -ti:<port>`, leaving yours alone.

The final report (`references/final-reply.md`) lists implemented boards and routes, files changed, compare results per board with the `side.png` and `diff.png` paths, remaining differences and why each is acceptable, stubs and gaps, project check results, and what was verified versus not verified (for example the real backend, other browsers, or sizes without a board).

### Rules

- **Approval is yours.** It never marks boards approved, and it does not implement unapproved boards without your decision.
- **Boards are read-only.** It never edits artboards, `tokens.css`, or `canvas.json` by hand. A board that is wrong or impossible to build as drawn is reported, with a suggested `canvas comment`.
- **The approved board is the reference,** never a rejected board or the old UI.
- **No match claims from the number alone.** It looks at the images before saying a screen matches.
- **Git.** It follows the project's git rules and does not commit, push, or deploy unless you ask.
- **Subagents.** When the work is split, each subagent gets the approved board paths and notes, the token mapping, the shell components, its routes and files, and the compare command. The main agent owns the token mapping and the shell.

### First-implementation retrospective

The first implementation is done when every in-scope board is implemented, compared, and recorded with `impl`, and the project checks were run. The report then ends with **Skill improvement suggestions** in the same form as the [first-draft retrospective](#the-first-draft-retrospective), looking at how the work went, not at the code. Approved changes are logged in `skills/mockup-to-code/references/lessons.md`.

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
