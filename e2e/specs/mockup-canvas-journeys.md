# mockup-canvas end-to-end test plan

## Application Overview

mockup-canvas is a local, Python standard library server (`skills/mockup-canvas/scripts/canvas.py`) that
shows HTML artboards on a pan and zoom canvas (`viewer.html`). It has a registry mode (many projects on one
index page with add, scan, and remove forms), a single-root mode, a token protected share mode
(read-only by default), and a static export. Boards are loaded in sandboxed iframes, live boards are
virtualized, and zoomed out (below 30% to 40%, with hysteresis) boards show cached PNG thumbnails. Layout moves are saved to
`canvas.json` and can be undone.

Assumptions for every scenario (fresh state):

- Each scenario gets its own temporary HOME with copies of `examples/trailmate` (project `alpha`) and,
  where needed, a second project `beta` or the 71-board large idea. `MOCKUP_CANVAS_HOME` points inside
  that HOME, so the user's real registry is never touched.
- Each scenario starts its own server on a free port (never 4400, 8080, 8787, 5173) and stops it at the end.
- Viewport: 1280x720 desktop, or iPhone 13 (390x664, touch) for the mobile scenarios.

Exploration notes from the running app (planner phase, done with curl and Playwright scripts since the
Playwright MCP tools are not available in this session):

- The registry index shows each project with its ideas, an "Add project" form, a "Find in folders"
  form, and "Remove from list" buttons that use `confirm()`.
- A request with a foreign Host header returns 421. `POST /api/roots/scan` with `Origin: null` returns
  403. A path outside HOME returns 400 "Paths outside the home directory are not allowed".
- `HEAD` on a board returns 501 (the server only implements GET and POST).
- A thumbnail request returns 202 while Chrome renders it in the background.

## Test Scenarios

### 1. Registry dashboard

**Seed:** `seed.spec.ts`. The page follows the approved boards in `design/canvas-dashboard` (B Gallery).

#### 1.1 Cards and thumbnails
1. Register `alpha` and open `/`.
2. Expect "All ideas", the summary "1 idea, 6 boards, 0 open comments", and a trailmate card with "6 boards" and a meter labelled "2 approved, 4 draft, 0 rejected of 6".
3. Expect a PNG thumbnail in the card within 45 s and no iframe on the page; the card link opens `/alpha/trailmate/` without console errors.

#### 1.2 Filter and search
1. Click "Needs decision" in the rail: the URL has `filter=needs-decision`, the summary says "1 idea and 4 boards match".
2. Press `/`, type "plan", choose "Filter the gallery by "plan"": one board tile (T04). Escape clears the search, Clear all returns to All ideas.

#### 1.3 Command palette
1. Cmd/Ctrl K focuses the palette field; empty groups are Recent ideas, Recent boards, Actions.
2. "trail" highlights "Trail" in T02; "zzzz" shows "Nothing matches" and Clear search; "home" and Enter opens `/alpha/trailmate/#T01-Home`.

#### 1.4 Add project, Find in folders, missing root
1. Add project shows the server's error under the field for `/etc`, a missing folder, and a folder without canvas.json; Add stays disabled.
2. For the parent of a design folder it offers "Use this folder"; then "Found 1 idea, 6 boards", the CLI line, and Add registers `beta` and opens it.
3. Find in folders lists alpha (already registered, disabled) and beta (checked) and adds beta.
4. A registered folder that was moved shows "Missing" in the rail and the warning page; Remove from list asks first and deletes no files.

#### 1.5 Theme, size, card menu, phone
1. Shift T switches to light, Compact switches the grid; both survive a reload.
2. The card menu's Copy URL copies `/alpha/trailmate/` (Chromium); the project view shows 6 recent boards and All 6 boards filters by status.
3. On a phone (`@mobile`) the rail is hidden, tabs and the search button are at least 44 px, and the palette is a sheet 44 px from the top.

#### 1.6 Collections across projects
1. With no collection the rail has no Collections heading. The card menu's Move to collection, New collection, a name, and Enter make "Lily"; the rail shows it with 1. Escape in the name field goes back to the list.
2. Moving `beta/second` into Lily from its card menu, then clicking Lily: the URL has `col=Lily`, the heading says "2 ideas from 2 projects" and "Ideas picked from alpha and beta"; a reload keeps it, and Needs decision adds a Lily chip.
3. The project menu's Add to collection (keyboard: Arrow Left goes back) puts all of `beta` in Lily: "Includes all of beta". roots.json keeps `roots` and holds `collections`.
4. Taking every key out removes Lily, the `col` in the URL, and the Collections heading.

### 2. Open an idea and navigate

**Seed:** `seed.spec.ts`

#### 2.1 Boards render with real content

**Steps:**
1. Open `/alpha/trailmate/`.
2. Zoom in with the mouse wheel over `T01-Home` until the zoom is above 40%.

**Expected Results:**
- The loading overlay disappears and six boards with title bars are present.
- The `T01-Home` iframe shows "Pine Ridge Loop" (the board is not blank).

#### 2.2 Wheel zoom in and out, F fits

**Steps:**
1. Record the zoom label after load (the fitted zoom).
2. Wheel up over the stage, then wheel down.
3. Press `F`.

**Expected Results:**
- The zoom label increases after wheel up and decreases after wheel down.
- `F` returns the exact fitted transform.

#### 2.3 Pan by dragging empty space

**Steps:**
1. Find a point where only the stage is under the pointer.
2. Drag it by (150, 80).

**Expected Results:**
- The canvas translate changes by (150, 80) and the zoom does not change.

#### 2.4 Arrows are drawn and L toggles them

**Steps:**
1. Count the arrow paths.
2. Press `L`, then `L` again.

**Expected Results:**
- Four arrows with labels such as "Open trail" are visible.
- The first `L` hides them and shows the toast "Arrows hidden"; the second shows them again.

#### 2.5 Collapsing a group hides its boards (discovered)

**Steps:**
1. Click the group header `v1`.
2. Click it again.

**Expected Results:**
- Boards get the `collapsed` class and no iframes remain; clicking again restores them.

### 3. Drag, undo, redo

**Seed:** `seed.spec.ts`

#### 3.1 Dragging a board by its title bar saves canvas.json

**Steps:**
1. Drag the `T03-Invite` title bar by (200, 120) screen pixels in several steps.

**Expected Results:**
- `canvas.json` on disk has new `x` and `y` for `T03-Invite` (moved by about 200/zoom, 120/zoom).

#### 3.2 Undo and redo the move

**Steps:**
1. After the drag, press Cmd/Ctrl+Z.
2. Press Shift+Cmd/Ctrl+Z.

**Expected Results:**
- Undo restores the original position on disk and shows the toast "Undo: T03-Invite".
- Redo writes the moved position again and shows "Redo: T03-Invite".
- Undo with nothing to undo shows "Nothing to undo" (edge case).

#### 3.3 Dragging does not copy the board id (discovered)

**Steps:**
1. Put known text on the clipboard (Chromium), then drag the `T03-Invite` title bar.

**Expected Results:**
- No "Copied" toast for the dragged board, and the clipboard is unchanged.

#### 3.4 Arrows follow during the drag

**Steps:**
1. Press the mouse on the `T03-Invite` bar and move it without releasing.

**Expected Results:**
- The arrows from `T02` and to `T04` change their path while the mouse is still down.

### 4. Title bar click and double click

**Seed:** `seed.spec.ts`

#### 4.1 Click copies the board id

**Steps:**
1. Click the `T01-Home` title bar.

**Expected Results:**
- A toast with `T01-Home` appears. Where clipboard permission can be granted (Chromium), the clipboard
  contains `T01-Home`.

#### 4.2 Double click opens the board alone in a new tab

**Steps:**
1. Double click the `T01-Home` title bar.

**Expected Results:**
- A new tab opens `.../boards/T01-Home.html` and shows "Pine Ridge Loop".

### 5. Comments and built badge

**Seed:** `seed.spec.ts`

#### 5.1 CLI comments show as a badge and a panel; Esc closes; XSS is text

**Steps:**
1. Add two comments to `T01-Home` with `canvas comment`, one containing `<img src=x onerror=...>` and one `<script>`.
2. Open the idea, click the comment badge, press Escape.

**Expected Results:**
- The badge shows `2`. The panel lists both comments as literal text with the author.
- No injected script ran (`window.__xss` stays undefined, no `img` in the panel).
- Escape closes the panel.

#### 5.2 Built badge tooltip shows the route

**Steps:**
1. Run `canvas impl ... T01-Home.html --route /home --file src/Home.tsx`.
2. Open the idea.

**Expected Results:**
- `T01-Home` has a `built` badge whose tooltip (title) is "Route: /home".

### 6. Live reload

**Seed:** `seed.spec.ts`

#### 6.1 Editing a board file reloads only that iframe

**Steps:**
1. Open the idea zoomed in on `T01-Home`; set a marker on `window`.
2. Append a visible element to `boards/T01-Home.html` on disk.

**Expected Results:**
- The iframe shows the new text within about 2 s (time recorded).
- The page marker survives (no full page reload).

#### 6.2 CLI status and link update the open canvas

**Steps:**
1. Run `canvas status ... T03-Invite.html approved`.
2. Run `canvas link ... T04-Plan.html T05-Empty.html --label "QA link"`.

**Expected Results:**
- `T03-Invite` gets the green approved badge; a fifth arrow labeled "QA link" appears; no page reload.

### 7. Large canvas (71 boards)

**Seed:** `seed.spec.ts`

#### 7.1 Zoomed out shows thumbnails or title cards, zoomed in shows live boards, no console errors

**Steps:**
1. Open the 71-board idea (copy of a real design folder, path from `MC_E2E_LARGE_IDEA`).
2. Check the fitted zoom is below 30% and count iframes.
3. Wheel zoom in over a board until above 40%.

**Expected Results:**
- Below 30%: no live iframes; each board shows a thumbnail or its title card.
- Above 40%: some, but not all 71, boards have live iframes (virtualization).
- No console errors or page errors.

#### 7.2 Pan frame rate

**Steps:**
1. With a requestAnimationFrame counter, drive a 2 s scripted pan at the fitted zoom and at about 60%.

**Expected Results:**
- FPS is recorded per browser; the test fails only below 30 FPS.

### 8. Share mode

**Seed:** `seed.spec.ts`

#### 8.1 Without the token the server answers 401

**Steps:**
1. Start `serve <design> --share --minutes 5`.
2. Request `/`, `/trailmate/`, and `/trailmate/canvas.json` without a token.

**Expected Results:**
- All return 401 "This link needs its access token". A wrong token also returns 401.

#### 8.2 The token URL opens a read-only viewer

**Steps:**
1. Open `/?t=<token>`, then the idea.
2. Zoom in on `T01-Home`, then drag its title bar.
3. POST a layout change with the session cookie.

**Expected Results:**
- The token is removed from the URL (cookie set) and the "Read-only" badge is visible.
- Board content loads through the keyed asset path ("Pine Ridge Loop").
- Dragging does not move the board and `canvas.json` on disk is unchanged; the POST returns 403.

#### 8.3 Mobile: badge visible, one-finger pan, two-finger pinch

**Steps:**
1. On iPhone 13 emulation (WebKit, touch), open the token URL and the idea.
2. Dispatch a one-finger touch drag on the stage.
3. Dispatch a two-finger spread.

**Expected Results:**
- The "Read-only" badge is inside the viewport.
- The one-finger drag translates the canvas; the spread increases the zoom.
- Note: Playwright has no multi-touch gesture API; touches are synthesized with `TouchEvent`, which
  exercises the viewer's handlers but not native browser gesture handling.

#### 8.4 Mobile: the toolbar fits inside the phone viewport (discovered)

**Steps:**
1. On iPhone 13 emulation, open the shared idea and measure `#toolbar`.

**Expected Results:**
- The toolbar's left and right edges are inside the 390 px viewport.

### 9. Export

**Seed:** `seed.spec.ts`

#### 9.1 Static export renders boards and arrows, read-only

**Steps:**
1. Run `canvas export <idea> <out>`.
2. Serve `<out>` with `python3 -m http.server` on a free port and open `/`.
3. Zoom in on `T01-Home` and try to drag it.

**Expected Results:**
- Six boards, four arrows, "Read-only" badge, and "Pine Ridge Loop" in the board iframe.
- Dragging does not move the board; no console errors.

### 10. Security smoke

**Seed:** `seed.spec.ts`

#### 10.1 A board script cannot call the registry API or reach the parent

**Steps:**
1. Add a script to a board that POSTs to `/api/roots/scan` and `/api/roots/add`, and reads `parent.document`.
2. Open the idea zoomed in on that board.

**Expected Results:**
- The board reports a blocked request (network error or 403), never `"ok": true`.
- `roots.json` is unchanged; `parent.document` access throws.

#### 10.2 Host header spoofing is rejected

**Steps:**
1. Send GET `/` with `Host: evil.example:<port>` through `APIRequestContext`.
2. Send POST `/api/roots/scan` with a foreign Origin.

**Expected Results:**
- GET with a foreign Host returns 421; `localhost:<port>` returns 200.
- The foreign-Origin POST returns 403.
