# Security

## Threat model

mockup-canvas is a local design tool. It serves HTML files from folders you choose and writes only layout data back to `canvas.json`.

### Local mode (default)

- `canvas serve` binds to `127.0.0.1` only. Nothing is reachable from other machines.
- **Host allowlist.** Every request (page, file, API, and the live-reload stream) must carry a `Host` header naming this server: `127.0.0.1:PORT`, `localhost:PORT`, or `[::1]:PORT`, plus the LAN address `IP:PORT` in share mode. Anything else, including a missing `Host`, gets `421 Misdirected Request`. This stops DNS rebinding, where a web page points its own domain at `127.0.0.1` to read or call the local server.
- The server serves only files inside a registered design folder: the canvas page, `canvas.json`, and files under `boards/`, `assets/`, and `shared/` of an idea. Paths are resolved with `realpath` and must stay inside the design folder, so `../`, encoded `%2e%2e`, absolute paths, and symlinks that point outside are rejected with 404.
- The only write endpoint on an idea is `POST /<idea>/api/layout` (registry mode: `/<project>/<idea>/api/layout`). It accepts a JSON body of at most 64 KiB, changes only `x` and `y` of an existing board, and writes `canvas.json` atomically (temp file plus rename).
- Both the layout endpoint and registry management (`POST /api/roots/add|remove|scan`) require a same-origin `Origin` or `Referer` header (CSRF protection; in share mode the LAN origin counts) and a `Content-Type` whose media type is exactly `application/json`. Errors sent to the browser are generic (`Invalid request`); details go to the server's stderr. A folder can be added only if it is inside your home directory, is not the home directory itself, is not a hidden or system folder (for example `~/.ssh` or `~/Library`), and contains at least one idea with `canvas.json`.
- **Sandboxed artboards.** Boards, and HTML or SVG files under `assets/` and `shared/`, are served with `Content-Security-Policy: sandbox allow-scripts allow-forms allow-popups`, and the canvas shows boards in iframes with the same `sandbox` flags. A board runs in an opaque origin: its scripts work, but they cannot read the canvas page or call the server's APIs (`/api/layout`, `/api/roots/*`). Font files are sent with `Access-Control-Allow-Origin: *` so sandboxed boards can still use local fonts. When the canvas itself is opened from a `file://` URL (the overview render, or an export opened from disk), there is no server to protect, so the iframes keep the file origin to load `../shared/` styles.
- **Timeouts and limits.** Each connection has a 15 second socket timeout (the live-reload stream is exempt), and at most 64 connections are handled at once; more get `503`. The live-reload stream is capped at 40 clients.
- The server identifies itself as `mockup-canvas` with no Python version. `X-Canvas-Root` (used to detect an already running server) carries a short SHA-256 prefix of the design folder path, never the path.
- Names and paths shown on index pages are HTML-escaped. The canvas data embedded by `canvas export` and `canvas overview` escapes every `<` (and U+2028, U+2029), so a board title cannot close the script tag. The viewer forces board positions and sizes to numbers and accepts only plain color values for group colors.
- `canvas render` and `canvas overview` run headless Chrome with a fresh temporary profile that is deleted afterward and without `--allow-file-access-from-files`, so a board cannot read other local files while it is rendered.
- `canvas export` refuses an output folder that is the idea folder, is inside it, or contains it. It copies symlinks as links and skips any that point outside the idea folder.

### Share mode (`--share`)

- `canvas serve <design dir> --share` binds to `0.0.0.0` so a phone on the same network can open it. Use it only on networks you trust.
- Every request needs a random token. The link carries it once as `?t=...`; the server then sets an `HttpOnly; SameSite=Strict` cookie and redirects to a URL without the token. A 401 response never contains the token.
- Share mode is read-only unless you pass `--share-edit`, never allows registry changes, and stops itself after `--minutes` (1 to 240, default 30; other values are refused).
- Registry share (`canvas serve --share`) serves only the projects registered when it started; later registry edits do not widen it. `--project NAME` shares a single project. The share index shows project and idea names only: no folder paths and no add, remove, or scan controls.
- Tokens are compared as bytes with `hmac.compare_digest`; a malformed or non-ASCII token gets `401`.
- Sandboxed boards do not send the `SameSite=Strict` cookie, so in share mode the canvas loads boards under `/_k/<key>/...`, where the key is derived from the token. That prefix allows `GET` of files under `boards/`, `assets/`, and `shared/` only; the canvas page, `canvas.json`, the live-reload stream, and every write still need the cookie.
- Traffic is plain HTTP. Anyone on the same network who can sniff traffic can read the token and the pages while sharing is on.

### Local files

- `~/.mockup-canvas/roots.json` and `config.json` (or the folder in `$MOCKUP_CANVAS_HOME`) hold your registered folders and options. They contain paths only, no secrets.

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories on this repository ("Report a vulnerability" under the Security tab). Do not open a public issue. Include steps to reproduce and the version or commit you tested.
