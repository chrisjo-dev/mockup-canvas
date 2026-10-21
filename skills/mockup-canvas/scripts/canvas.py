#!/usr/bin/env python3
"""mockup-canvas: local canvas for HTML mockup artboards

Usage: python3 canvas.py <command> [args...]

Commands:
  serve [<design dir>] [--port 4400] [--share [--minutes 30] [--share-edit]]
  serve --share --project NAME   (registry mode: share one project)
  roots [list|add|remove|scan] ...
  new <design dir> <idea>
  add <idea dir> <file> [--group NAME] [--size mobile|tablet|desktop|WxH]
  group <idea dir> <file> <group name>
  render <idea dir> [file...]
  check <idea dir>
  overview <idea dir>
  export <idea dir> <output dir>
  link <idea dir> <from file> <to file> [--label TEXT]
  status <idea dir> <file> <draft|approved|rejected> [--note TEXT]
  artifact <idea dir> [url]

Run any command with -h/--help to see its usage.

User data lives in ~/.mockup-canvas/ (override with MOCKUP_CANVAS_HOME):
  roots.json   registered design folders (registry mode)
  config.json  options, e.g. {"forbidden_chars": ["\u2014"]}
"""
import sys, os, json, re, shutil, subprocess, time, threading, tempfile, pathlib
import socketserver, socket, secrets, mimetypes, http.client, textwrap
import hmac, hashlib
import html as _html
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, unquote, parse_qs, quote as _urlquote

_MACOS_CHROME_PATHS = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
]
_WHICH_NAMES = [
    'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'msedge', 'chrome',
]

def _resolve_chrome():
    """Return a Chrome/Chromium executable path, or None if not found.

    Resolution order:
      1. MOCKUP_CANVAS_CHROME environment variable
      2. macOS: Google Chrome / Chromium / Microsoft Edge app bundles
      3. PATH: google-chrome, google-chrome-stable, chromium, chromium-browser, msedge, chrome
    """
    env_val = os.environ.get('MOCKUP_CANVAS_CHROME', '').strip()
    if env_val:
        return env_val
    for p in _MACOS_CHROME_PATHS:
        if os.path.isfile(p):
            return p
    for name in _WHICH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None

def _get_chrome():
    """Return the Chrome path, or print an error and exit 1."""
    path = _resolve_chrome()
    if not path:
        print(
            'Error: no Chrome/Chromium browser found.\n'
            'Install Google Chrome, Chromium, or Microsoft Edge, or point\n'
            'MOCKUP_CANVAS_CHROME at the executable:\n'
            '  export MOCKUP_CANVAS_CHROME=/path/to/chrome',
            file=sys.stderr,
        )
        sys.exit(1)
    return path

# Module-level alias kept for backward compatibility (e.g. skipUnless checks).
CHROME = _resolve_chrome() or ''

DEFAULT_PORT = 4400
DEFAULT_W, DEFAULT_H = 390, 844
SIZE_PRESETS = {
    'mobile':  (390, 844),
    'tablet':  (768, 1024),
    'desktop': (1440, 900),
}
HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER_PATH = os.path.join(HERE, 'viewer.html')
HEADER_ROOT = 'X-Canvas-Root'
REGISTRY_SENTINEL = '__registry__'
HOME = os.path.expanduser('~')
DATA_DIR = os.path.expanduser(os.environ.get('MOCKUP_CANVAS_HOME') or '~/.mockup-canvas')
ROOTS_PATH = os.path.join(DATA_DIR, 'roots.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
# Older versions kept the registry next to the skill folder.
LEGACY_ROOTS_PATH = os.path.join(os.path.dirname(HERE), 'roots.json')

# ── User config ─────────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f'Warning: could not read {CONFIG_PATH}: {e}', file=sys.stderr)
        return {}

def migrate_legacy_roots():
    """Copy the old skill-folder registry to DATA_DIR once, if needed."""
    if os.path.exists(ROOTS_PATH) or not os.path.isfile(LEGACY_ROOTS_PATH):
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    shutil.copy2(LEGACY_ROOTS_PATH, ROOTS_PATH)
    print(f'Migrated project registry: {LEGACY_ROOTS_PATH} -> {ROOTS_PATH}', file=sys.stderr)

# ── Registry ────────────────────────────────────────────────────────────────

_roots_lock = threading.Lock()

def load_roots():
    if not os.path.exists(ROOTS_PATH):
        return []
    try:
        with open(ROOTS_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    roots = []
    for r in data.get('roots', []):
        path = os.path.expanduser(r.get('path', ''))
        name = r.get('name', '').strip()
        if name and path:
            roots.append({'name': name, 'path': path})
    return roots

def save_roots(roots_list):
    serialized = []
    for r in roots_list:
        path = r['path']
        if path.startswith(HOME + os.sep):
            path = '~/' + path[len(HOME)+1:]
        elif path == HOME:
            path = '~'
        serialized.append({'name': r['name'], 'path': path})
    # Write through a symlinked roots.json (e.g. one kept in a dotfiles repo)
    target = os.path.realpath(ROOTS_PATH)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'roots': serialized}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

def load_roots_safe():
    with _roots_lock:
        return load_roots()

def save_roots_safe(roots_list):
    with _roots_lock:
        save_roots(roots_list)

_BLOCKED_FIRST = {'.ssh', '.gnupg', '.aws', '.kube', '.docker', '.config', 'Library', 'System', 'Applications'}

def _validate_design_path(path_str):
    """Returns (error_msg_or_None, real_abs_path)"""
    if not path_str:
        return 'Path is empty', None
    real = os.path.realpath(os.path.expanduser(path_str.strip()))
    if real == '/':
        return 'The filesystem root is not allowed', None
    if not (real == HOME or real.startswith(HOME + os.sep)):
        return 'Paths outside the home directory are not allowed', None
    if real == HOME:
        return 'The home directory itself cannot be added', None
    rel = os.path.relpath(real, HOME)
    first_part = rel.split(os.sep)[0]
    if first_part in _BLOCKED_FIRST or (first_part.startswith('.') and first_part != '.claude'):
        return f'System or hidden directories are not allowed: ~/{first_part}', None
    if not os.path.isdir(real):
        return 'Directory does not exist', None
    has_canvas = False
    try:
        for entry in os.listdir(real):
            if os.path.isdir(os.path.join(real, entry)) and \
               os.path.exists(os.path.join(real, entry, 'canvas.json')):
                has_canvas = True
                break
    except Exception:
        pass
    if not has_canvas:
        return 'Not a mockup-canvas design folder (no subfolder contains canvas.json)', None
    return None, real

_SCAN_SKIP = {'node_modules', '.git', 'Library', 'System', 'Applications', '.Trash'}

def _scan_for_roots(dirs, max_depth=5, timeout_secs=10):
    """Returns list of {'name', 'path', 'already_registered'}."""
    found_designs = set()
    deadline = time.time() + timeout_secs

    def walk(path, depth):
        if time.time() > deadline or depth > max_depth:
            return
        basename = os.path.basename(path)
        if basename in _SCAN_SKIP or basename.endswith('-wt') or basename.startswith('.'):
            return
        try:
            entries = os.listdir(path)
        except (PermissionError, OSError):
            return
        for entry in entries:
            if time.time() > deadline:
                return
            if entry in _SCAN_SKIP or entry.endswith('-wt') or entry.startswith('.'):
                continue
            entry_path = os.path.join(path, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry == 'design':
                try:
                    for idea in os.listdir(entry_path):
                        idea_path = os.path.join(entry_path, idea)
                        if os.path.isdir(idea_path) and \
                           os.path.exists(os.path.join(idea_path, 'canvas.json')):
                            found_designs.add(entry_path)
                            break
                except Exception:
                    pass
            else:
                walk(entry_path, depth + 1)

    for d in dirs:
        real_d = os.path.realpath(os.path.expanduser(d))
        if os.path.isdir(real_d):
            walk(real_d, 0)

    existing_paths = {os.path.realpath(r['path']) for r in load_roots()}
    results = []
    for design_path in sorted(found_designs):
        project_dir = os.path.dirname(design_path)
        name = os.path.basename(project_dir)
        results.append({
            'name': name,
            'path': design_path,
            'already_registered': os.path.realpath(design_path) in existing_paths,
        })
    return results

# ── Utilities ──────────────────────────────────────────────────────────────

def load_canvas(idea_dir):
    p = os.path.join(idea_dir, 'canvas.json')
    if not os.path.exists(p):
        return {'boards': {}, 'groups': []}
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def save_canvas_atomic(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def find_free_port(start):
    for p in range(start, start + 200):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', p))
                return p
        except OSError:
            continue
    raise RuntimeError('No free port found')

def _root_id(path):
    """Opaque id for a design folder, sent in X-Canvas-Root instead of the path."""
    return hashlib.sha256(os.path.realpath(path).encode('utf-8')).hexdigest()[:16]

def _media_type(value):
    """'application/json; charset=utf-8' -> 'application/json'"""
    return (value or '').split(';', 1)[0].strip().lower()

def _embed_json(data):
    """JSON safe to place inside an inline <script>."""
    return (json.dumps(data, ensure_ascii=False)
        .replace('<', '\\u003c')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029'))

def _within(path, base):
    path, base = os.path.realpath(path), os.path.realpath(base)
    return path == base or path.startswith(base + os.sep)

def _copytree_inside(src, dst, root):
    """copytree that keeps symlinks as links and skips links resolving outside root."""
    def ignore(d, names):
        skip = []
        for n in names:
            p = os.path.join(d, n)
            if os.path.islink(p) and not _within(p, root):
                print(f'Skipped symlink outside the idea folder: {p}', file=sys.stderr)
                skip.append(n)
        return skip
    shutil.copytree(src, dst, symlinks=True, ignore=ignore)

def _chrome_args(profile_dir, w, h, budget_ms):
    """Headless Chrome flags for render/overview. No file-access flags; throwaway profile."""
    return [_get_chrome(), '--headless=new', f'--user-data-dir={profile_dir}',
            '--no-first-run', '--no-default-browser-check',
            # Keep sandboxed board iframes in-process so --screenshot captures them
            # (they stay sandboxed with an opaque origin either way)
            '--disable-features=IsolateSandboxedIframes',
            f'--window-size={w},{h}', '--hide-scrollbars',
            f'--virtual-time-budget={budget_ms}']

def _run_chrome(w, h, budget_ms, out_png, url):
    profile = tempfile.mkdtemp(prefix='mockup-canvas-chrome-')
    try:
        return subprocess.run(_chrome_args(profile, w, h, budget_ms) + [f'--screenshot={out_png}', url],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(profile, ignore_errors=True)

def _parse_minutes(args, default=30):
    if '--minutes' not in args:
        return default
    idx = args.index('--minutes')
    raw = args[idx + 1] if idx + 1 < len(args) else ''
    try:
        minutes = int(raw)
    except ValueError:
        minutes = 0
    if not 1 <= minutes <= 240:
        print(f'Error: --minutes must be a whole number from 1 to 240 (got {raw!r})', file=sys.stderr)
        sys.exit(2)
    return minutes

def check_existing_server(port):
    """Returns the X-Canvas-Root header value, or '' if not running."""
    try:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
        conn.request('GET', '/')
        resp = conn.getresponse()
        root = resp.getheader(HEADER_ROOT, '')
        conn.close()
        return root
    except Exception:
        return ''

def _safe_path(base, *parts):
    real_base = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base, *parts))
    if not target.startswith(real_base + os.sep) and target != real_base:
        return None
    return target

def find_free_x(boards, w=DEFAULT_W, gap=40):
    if not boards:
        return 0, 0
    max_x2 = max(b['x'] + b['w'] for b in boards.values())
    return max_x2 + gap, 0

def _is_help(args):
    return any(a in ('-h', '--help') for a in args)

def _board_key(file_arg):
    """Board keys in canvas.json are bare file names: 'boards/A.html' or 'A' -> 'A.html'."""
    name = os.path.basename(file_arg.rstrip('/'))
    return name if name.endswith('.html') else name + '.html'

def _ensure_group(canvas, group_name):
    groups = canvas.setdefault('groups', [])
    if not any(g.get('id') == group_name for g in groups):
        groups.append({'id': group_name, 'label': group_name})

# ── SSE ────────────────────────────────────────────────────────────────────

_sse_clients: dict = {}
_sse_lock = threading.Lock()
_sse_max = 40

def _add_sse(key, wfile):
    with _sse_lock:
        total = sum(len(v) for v in _sse_clients.values())
        if total >= _sse_max:
            return False
        _sse_clients.setdefault(key, []).append(wfile)
        return True

def _rm_sse(key, wfile):
    with _sse_lock:
        lst = _sse_clients.get(key, [])
        try:
            lst.remove(wfile)
        except ValueError:
            pass

def _broadcast(key, data):
    msg = ('data: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode()
    dead = []
    with _sse_lock:
        clients = list(_sse_clients.get(key, []))
    for wf in clients:
        try:
            wf.write(msg)
            wf.flush()
        except Exception:
            dead.append(wf)
    for d in dead:
        _rm_sse(key, d)

def _watch_thread(design_dirs):
    """
    design_dirs: list of (design_dir, key_prefix)
      single-root: [(design_dir, '')]
      registry:    [(design_dir1, 'proj1/'), (design_dir2, 'proj2/')]
    """
    mtimes: dict = {}
    while True:
        for design_dir, prefix in design_dirs:
            try:
                for idea in os.listdir(design_dir):
                    idea_dir = os.path.join(design_dir, idea)
                    if not os.path.isdir(idea_dir):
                        continue
                    sse_key = prefix + idea
                    boards_dir = os.path.join(idea_dir, 'boards')
                    if os.path.isdir(boards_dir):
                        for fname in os.listdir(boards_dir):
                            if not fname.endswith('.html'):
                                continue
                            p = os.path.join(boards_dir, fname)
                            try:
                                mt = os.stat(p).st_mtime
                            except Exception:
                                continue
                            mkey = (sse_key, fname)
                            if mkey in mtimes and mtimes[mkey] != mt:
                                _broadcast(sse_key, {'type': 'board', 'file': fname})
                            mtimes[mkey] = mt
                    cj = os.path.join(idea_dir, 'canvas.json')
                    if os.path.exists(cj):
                        try:
                            mt = os.stat(cj).st_mtime
                        except Exception:
                            continue
                        mkey = (sse_key, 'canvas.json')
                        if mkey in mtimes and mtimes[mkey] != mt:
                            _broadcast(sse_key, {'type': 'canvas'})
                        mtimes[mkey] = mt
            except Exception:
                pass
        time.sleep(1)

# ── HTTP handler ───────────────────────────────────────────────────────────

_SANDBOX_CSP = 'sandbox allow-scripts allow-forms allow-popups'
_ACTIVE_TYPES = ('text/html', 'image/svg+xml', 'application/xhtml+xml', 'text/xml', 'application/xml')
_FONT_EXTS = ('.woff', '.woff2', '.ttf', '.otf', '.eot')

class CanvasHandler(BaseHTTPRequestHandler):
    design_dir: str = ''
    share_token: str = ''
    share_edit: bool = True
    read_only: bool = False
    share_host: str = ''      # LAN IP accepted in the Host header in share mode
    server_version = 'mockup-canvas'
    sys_version = ''
    timeout = 15              # socket timeout per connection (SSE clears it)

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        pass

    def _log_error(self, what, err):
        print(f'[mockup-canvas] {what}: {err!r}', file=sys.stderr, flush=True)

    # ── request gate: Host allowlist (DNS rebinding) ──
    def _allowed_hosts(self):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}', f'[::1]:{port}'}
        if self.share_token and self.share_host:
            hosts.add(f'{self.share_host}:{port}'.lower())
        return hosts

    def parse_request(self):
        if not super().parse_request():
            return False
        host = (self.headers.get('Host') or '').strip().lower()
        if host not in self._allowed_hosts():
            self.close_connection = True
            body = b'Misdirected Request'
            self.send_response(421)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
            return False
        return True

    def _add_root_header(self):
        if not self.share_token:
            self.send_header(HEADER_ROOT, _root_id(self.design_dir))

    def _check_auth(self):
        if not self.share_token:
            return True
        token = self.share_token.encode('utf-8')
        cookies = {}
        for h in self.headers.get_all('Cookie') or []:
            for part in h.split(';'):
                kv = part.strip().split('=', 1)
                if len(kv) == 2:
                    cookies[kv[0].strip()] = kv[1].strip()
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        given = (qs.get('t') or [''])[0]
        if given and hmac.compare_digest(given.encode('utf-8', 'surrogateescape'), token):
            return 'set_cookie'
        cookie_val = cookies.get('canvas_token', '')
        return hmac.compare_digest(cookie_val.encode('utf-8', 'surrogateescape'), token)

    def _check_same_origin(self):
        """CSRF: Origin (or Referer) must be one of this server's own origins."""
        allowed = {'http://' + h for h in self._allowed_hosts()}
        origin = self.headers.get('Origin', '').strip().rstrip('/').lower()
        if origin:
            return origin in allowed
        referer = self.headers.get('Referer', '').strip().lower()
        if referer:
            for a in allowed:
                if referer.startswith(a + '/') or referer == a:
                    return True
        return False

    def _read_json_body(self):
        """Checks Origin, Content-Type and size; returns the parsed body or None (error already sent)."""
        if not self._check_same_origin():
            self._json({'ok': False, 'error': 'CSRF check failed: a same-origin Origin or Referer header is required'}, 403)
            return None
        if _media_type(self.headers.get('Content-Type')) != 'application/json':
            self._json({'ok': False, 'error': 'Content-Type: application/json is required'}, 400)
            return None
        cl_hdr = self.headers.get('Content-Length')
        if cl_hdr is None:
            self._json({'ok': False, 'error': 'Content-Length required'}, 400)
            return None
        try:
            length = int(cl_hdr)
            if length < 0:
                raise ValueError
        except ValueError:
            self._json({'ok': False, 'error': 'Invalid Content-Length'}, 400)
            return None
        if length > 65536:
            self._json({'ok': False, 'error': 'Request too large'}, 413)
            return None
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._log_error('invalid JSON body', e)
            self._json({'ok': False, 'error': 'Invalid request'}, 400)
            return None
        if not isinstance(body, dict):
            self._json({'ok': False, 'error': 'Invalid request'}, 400)
            return None
        return body

    def _save_layout(self, idea_dir):
        cj_path = os.path.join(idea_dir, 'canvas.json')
        if not os.path.realpath(cj_path).endswith('canvas.json'):
            self._json({'ok': False, 'error': 'Not allowed'}, 403)
            return
        payload = self._read_json_body()
        if payload is None:
            return
        try:
            board = str(payload['board'])
            new_x = int(payload['x'])
            new_y = int(payload['y'])
            canvas = load_canvas(idea_dir)
            if board in canvas.get('boards', {}):
                canvas['boards'][board]['x'] = new_x
                canvas['boards'][board]['y'] = new_y
                save_canvas_atomic(cj_path, canvas)
            self._json({'ok': True})
        except Exception as e:
            self._log_error('layout save failed', e)
            self._json({'ok': False, 'error': 'Invalid request'}, 400)

    # ── share mode: static files for sandboxed boards ──
    # A sandboxed board has an opaque origin, so the SameSite=Strict token cookie is not sent
    # with its CSS, font, and image requests. In share mode the viewer loads boards under
    # /_k/<asset key>/..., and that prefix authorizes GET of boards/, assets/, shared/ files only.
    STATIC_DIR_INDEX = 1   # parts index of 'boards' | 'assets' | 'shared'

    def _asset_key(self):
        return hmac.new(self.share_token.encode('utf-8'), b'mockup-canvas assets',
                        hashlib.sha256).hexdigest()[:32]

    def _keyed_static_parts(self):
        """Share mode: the path parts after a valid /_k/<key>/ prefix, else None."""
        if not self.share_token:
            return None
        parts, _ = self._parse()
        if len(parts) < 2 or parts[0] != '_k':
            return None
        if not hmac.compare_digest(parts[1].encode('utf-8', 'surrogateescape'), self._asset_key().encode()):
            return None
        return parts[2:]

    def _is_static(self, parts):
        i = self.STATIC_DIR_INDEX
        return len(parts) == i + 2 and parts[i] in ('boards', 'assets', 'shared')

    def _gate_get(self):
        """Auth for GET. Returns the path parts to serve, or None when a response was sent."""
        keyed = self._keyed_static_parts()
        if keyed is not None:
            if not self._is_static(keyed):
                self._404()
                return None
            return keyed
        auth = self._check_auth()
        if auth == 'set_cookie':
            self._set_token_cookie_and_redirect()
            return None
        if not auth:
            self._unauthorized()
            return None
        return self._parse()[0]

    def _set_token_cookie_and_redirect(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        qs.pop('t', None)
        clean = parsed.path
        if qs:
            from urllib.parse import urlencode
            clean += '?' + urlencode({k: v[0] for k, v in qs.items()})
        self.send_response(302)
        self.send_header('Location', clean)
        self.send_header('Set-Cookie',
            f'canvas_token={self.share_token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400')
        self._add_root_header()
        self.end_headers()

    def _unauthorized(self):
        body = 'This link needs its access token'.encode()
        self.send_response(401)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._add_root_header()
        self.end_headers()
        self.wfile.write(body)

    def _parse(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip('/')
        parts = [p for p in path.split('/') if p]
        return parts, parsed

    def _safe(self, *parts):
        return _safe_path(self.design_dir, *parts)

    def _serve_static(self, path, fname, board=False):
        """boards/, assets/, shared/: active documents are sandboxed; fonts get CORS for sandboxed boards."""
        if board:
            mt = 'text/html; charset=utf-8'
        else:
            mt, _ = mimetypes.guess_type(fname)
            mt = mt or 'application/octet-stream'
        extra = {}
        if board or mt.split(';')[0] in _ACTIVE_TYPES:
            extra['Content-Security-Policy'] = _SANDBOX_CSP
        elif fname.lower().endswith(_FONT_EXTS):
            extra['Access-Control-Allow-Origin'] = '*'
        extra['X-Content-Type-Options'] = 'nosniff'
        extra['Referrer-Policy'] = 'no-referrer'
        self._serve_file(path, mt, extra)

    def do_GET(self):
        parts = self._gate_get()
        if parts is None:
            return

        if not parts:
            self._serve_index()
            return

        idea = parts[0]
        idea_dir = self._safe(idea)
        if not idea_dir or not os.path.isdir(idea_dir):
            self._404(); return

        if len(parts) == 1:
            self._serve_viewer()
            return

        if parts[1] == 'canvas.json' and len(parts) == 2:
            p = os.path.join(idea_dir, 'canvas.json')
            self._serve_file(p, 'application/json; charset=utf-8')
            return

        if parts[1] == 'api' and len(parts) == 3 and parts[2] == 'events':
            self._serve_sse(idea)
            return

        if parts[1] == 'boards' and len(parts) == 3:
            fname = parts[2]
            p = self._safe(idea, 'boards', fname)
            if not p:
                self._404(); return
            self._serve_static(p, fname, board=True)
            return

        if parts[1] in ('assets', 'shared') and len(parts) == 3:
            fname = parts[2]
            p = self._safe(idea, parts[1], fname)
            if not p:
                self._404(); return
            self._serve_static(p, fname)
            return

        self._404()

    def do_POST(self):
        if self.read_only or (self.share_token and not self.share_edit):
            self._json({'ok': False, 'error': 'Read-only'}, 403)
            return

        auth = self._check_auth()
        if not auth or auth == 'set_cookie':
            self._unauthorized(); return

        parts, _ = self._parse()

        if len(parts) == 3 and parts[1] == 'api' and parts[2] == 'layout':
            idea_dir = self._safe(parts[0])
            if not idea_dir:
                self._404(); return
            self._save_layout(idea_dir)
            return

        self._404()

    def _serve_index(self):
        ideas = []
        try:
            for d in sorted(os.listdir(self.design_dir)):
                p = os.path.join(self.design_dir, d)
                if os.path.isdir(p) and os.path.exists(os.path.join(p, 'canvas.json')):
                    ideas.append(d)
        except Exception:
            pass

        items = ''
        for idea in ideas:
            canvas = load_canvas(os.path.join(self.design_dir, idea))
            cnt = len(canvas.get('boards', {}))
            idea_url = _urlquote(idea, safe='')
            idea_text = _html.escape(idea)
            items += f'<a href="/{idea_url}/">{idea_text}<span class="cnt">{cnt} artboards</span></a>\n'

        html = textwrap.dedent(f"""
            <!doctype html><html lang="en"><head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Mockup Canvas</title>
            <style>
              *{{box-sizing:border-box}}
              body{{margin:0;background:#1e1e1e;font:15px -apple-system,sans-serif;
                    display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:40px 16px}}
              h1{{color:#fff;font-size:22px;font-weight:700;margin-bottom:20px}}
              a{{display:flex;justify-content:space-between;align-items:center;
                 background:#2a2a2a;border-radius:10px;padding:14px 18px;margin-bottom:8px;
                 max-width:480px;width:100%;color:#e0e0e0;text-decoration:none;font-weight:600}}
              a:hover{{background:#333}}
              .cnt{{font-weight:400;color:#888;font-size:13px}}
            </style></head><body>
            <h1>Mockup Canvas</h1>
            {items}
            </body></html>
        """).strip()

        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._add_root_header()
        self.end_headers()
        self.wfile.write(body)

    def _serve_viewer(self):
        """Serve viewer.html, injecting CANVAS_READ_ONLY when the session is read-only."""
        is_ro = (self.share_token and not self.share_edit) or self.read_only
        try:
            with open(VIEWER_PATH, 'rb') as fh:
                data = fh.read()
        except Exception:
            self._404(); return
        if is_ro:
            inject = b'<script>var CANVAS_READ_ONLY=true;</script>\n'
            data = data.replace(b'</head>', inject + b'</head>', 1)
        if self.share_token:
            inject = f'<script>var CANVAS_ASSET_PREFIX="/_k/{self._asset_key()}";</script>\n'.encode()
            data = data.replace(b'</head>', inject + b'</head>', 1)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self._add_root_header()
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path, content_type, extra_headers=None):
        if not path or not os.path.isfile(path):
            self._404(); return
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except Exception:
            self._404(); return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self._add_root_header()
        self.end_headers()
        self.wfile.write(data)

    def _serve_sse(self, key):
        if not _add_sse(key, self.wfile):
            self._json({'ok': False, 'error': 'Too many connections'}, 503)
            return
        # Long-lived stream: exempt from the per-connection socket timeout
        self.connection.settimeout(None)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        self._add_root_header()
        self.end_headers()
        self.wfile.write(b': ping\n\n')
        self.wfile.flush()
        try:
            while True:
                time.sleep(25)
                self.wfile.write(b': ping\n\n')
                self.wfile.flush()
        except Exception:
            pass
        finally:
            _rm_sse(key, self.wfile)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._add_root_header()
        self.end_headers()
        self.wfile.write(body)

    def _404(self):
        self.send_response(404)
        self._add_root_header()
        self.end_headers()

    def _403(self):
        self.send_response(403)
        self._add_root_header()
        self.end_headers()


# ── Registry handler ───────────────────────────────────────────────────────

_REGISTRY_MANAGE_HTML = """
  <h2>Add project</h2>
  <div class="panel">
    <div class="field">
      <label for="add-path">Design folder path</label>
      <input id="add-path" type="text" placeholder="~/project/design" autocomplete="off">
    </div>
    <div class="field">
      <label for="add-name">Name (leave empty to use the folder name)</label>
      <div class="row">
        <input id="add-name" type="text" placeholder="project">
        <button class="btn-primary" onclick="addProject()">Add</button>
      </div>
    </div>
    <div class="msg" id="add-msg"></div>
  </div>

  <h2>Find in folders</h2>
  <div class="panel">
    <div class="field">
      <label for="scan-dir">Folders to search (comma separated)</label>
      <div class="row">
        <input id="scan-dir" type="text" placeholder="~/work, ~/projects" autocomplete="off">
        <button class="btn-secondary" onclick="scanProjects()">Search</button>
      </div>
    </div>
    <div class="msg" id="scan-msg"></div>
    <div class="scan-results" id="scan-results"></div>
    <div id="scan-add-row" style="display:none;margin-top:12px">
      <button class="btn-primary" onclick="addScanned()">Add selected</button>
    </div>
  </div>
"""

_REGISTRY_MANAGE_SCRIPT = """<script>
(function(){
  'use strict';

  function msg(id, text, isErr) {
    var el = document.getElementById(id);
    el.textContent = text;
    el.className = 'msg ' + (isErr ? 'err' : 'ok');
  }

  async function apiPost(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Origin': location.origin},
      body: JSON.stringify(body)
    });
    return r.json();
  }

  window.removeProject = async function(name) {
    if (!confirm('Remove \\'' + name + '\\' from the list?\\n(No files are deleted)')) return;
    try {
      const d = await apiPost('/api/roots/remove', {name});
      if (d.ok) location.reload();
      else alert('Error: ' + d.error);
    } catch(e) { alert('Error: ' + e.message); }
  };

  window.addProject = async function() {
    const path = document.getElementById('add-path').value.trim();
    const name = document.getElementById('add-name').value.trim();
    if (!path) { msg('add-msg', 'Enter a path', true); return; }
    msg('add-msg', 'Checking...', false);
    try {
      const d = await apiPost('/api/roots/add', {path, name: name || undefined});
      if (d.ok) { msg('add-msg', 'Added: ' + d.name, false); setTimeout(() => location.reload(), 600); }
      else msg('add-msg', 'Error: ' + d.error, true);
    } catch(e) { msg('add-msg', 'Error: ' + e.message, true); }
  };

  window.scanProjects = async function() {
    const raw = document.getElementById('scan-dir').value.trim();
    if (!raw) { msg('scan-msg', 'Enter a folder', true); return; }
    const dirs = raw.split(',').map(s => s.trim()).filter(Boolean);
    msg('scan-msg', 'Searching...', false);
    document.getElementById('scan-results').innerHTML = '';
    document.getElementById('scan-add-row').style.display = 'none';
    try {
      const d = await apiPost('/api/roots/scan', {dirs});
      if (!d.ok) { msg('scan-msg', 'Error: ' + d.error, true); return; }
      const found = d.found || [];
      if (!found.length) { msg('scan-msg', 'No design folders found', false); return; }
      msg('scan-msg', 'Found ' + found.length, false);
      const container = document.getElementById('scan-results');
      found.forEach(function(item, i) {
        const div = document.createElement('div');
        div.className = 'scan-item';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.id = 'scan-cb-' + i;
        cb.dataset.path = item.path;
        cb.dataset.name = item.name;
        cb.disabled = item.already_registered;
        cb.checked = !item.already_registered;
        const lbl = document.createElement('label');
        lbl.htmlFor = 'scan-cb-' + i;
        lbl.innerHTML = '<span>' + escHtml(item.name) + (item.already_registered ? '<span class=\\"tag-registered\\">already registered</span>' : '') + '</span><span class=\\"scan-path\\">' + escHtml(item.path) + '</span>';
        div.appendChild(cb);
        div.appendChild(lbl);
        container.appendChild(div);
      });
      if (found.some(f => !f.already_registered))
        document.getElementById('scan-add-row').style.display = 'block';
    } catch(e) { msg('scan-msg', 'Error: ' + e.message, true); }
  };

  window.addScanned = async function() {
    const cbs = document.querySelectorAll('#scan-results input[type=checkbox]:checked:not(:disabled)');
    if (!cbs.length) { return; }
    let added = 0, errors = [];
    for (const cb of cbs) {
      try {
        const d = await apiPost('/api/roots/add', {path: cb.dataset.path, name: cb.dataset.name});
        if (d.ok) added++;
        else errors.push(cb.dataset.name + ': ' + d.error);
      } catch(e) { errors.push(cb.dataset.name + ': ' + e.message); }
    }
    if (added) { msg('scan-msg', 'Added ' + added, false); setTimeout(() => location.reload(), 600); }
    else msg('scan-msg', errors.join(' / '), true);
  };

  function escHtml(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
})();
</script>
"""


class RegistryHandler(CanvasHandler):
    """Registry mode: serve many projects from one server."""
    server_port: int = DEFAULT_PORT
    frozen_roots = None   # share mode: the roots list captured at start time

    def _add_root_header(self):
        if not self.share_token:
            self.send_header(HEADER_ROOT, REGISTRY_SENTINEL)

    def _roots(self):
        if self.frozen_roots is not None:
            return list(self.frozen_roots)
        return load_roots_safe()

    def _roots_map(self):
        return {r['name']: r['path'] for r in self._roots()}

    def _resolve(self, parts):
        """Returns (project, idea, design_dir, idea_dir) or None."""
        if len(parts) < 2:
            return None
        project = parts[0]
        rm = self._roots_map()
        design_dir = rm.get(project)
        if not design_dir:
            return None
        # Set instance attribute so _safe works correctly
        self.design_dir = design_dir
        idea = parts[1]
        idea_dir = _safe_path(design_dir, idea)
        if not idea_dir:
            return None
        return project, idea, design_dir, idea_dir

    STATIC_DIR_INDEX = 2

    def do_GET(self):
        parts = self._gate_get()
        if parts is None:
            return
        # Reject traversal even if client normalizes before sending
        raw = urlparse(self.path).path
        if '..' in unquote(raw).split('/'):
            self._404(); return

        if not parts:
            self._serve_registry_index()
            return

        resolved = self._resolve(parts)
        if not resolved:
            self._404(); return

        project, idea, design_dir, idea_dir = resolved
        if not os.path.isdir(idea_dir):
            self._404(); return

        rest = parts[2:]

        if not rest:
            self._serve_viewer()
            return

        if rest[0] == 'canvas.json' and len(rest) == 1:
            p = os.path.join(idea_dir, 'canvas.json')
            self._serve_file(p, 'application/json; charset=utf-8')
            return

        if rest[0] == 'api' and len(rest) == 2 and rest[1] == 'events':
            sse_key = project + '/' + idea
            self._serve_sse(sse_key)
            return

        if rest[0] == 'boards' and len(rest) == 2:
            fname = rest[1]
            p = _safe_path(design_dir, idea, 'boards', fname)
            if not p:
                self._404(); return
            self._serve_static(p, fname, board=True)
            return

        if rest[0] in ('assets', 'shared') and len(rest) == 2:
            fname = rest[1]
            p = _safe_path(design_dir, idea, rest[0], fname)
            if not p:
                self._404(); return
            self._serve_static(p, fname)
            return

        self._404()

    def do_POST(self):
        parts, _ = self._parse()

        # ── Registry management API ─────────────────────────────────────
        if len(parts) >= 2 and parts[0] == 'api' and parts[1] == 'roots':
            self._handle_roots_api(parts[2] if len(parts) >= 3 else '')
            return

        # ── Save layout (/<project>/<idea>/api/layout) ───────────────────
        if self.read_only or (self.share_token and not self.share_edit):
            self._json({'ok': False, 'error': 'Read-only'}, 403)
            return

        auth = self._check_auth()
        if not auth or auth == 'set_cookie':
            self._unauthorized(); return

        if len(parts) == 4 and parts[2] == 'api' and parts[3] == 'layout':
            resolved = self._resolve(parts)
            if not resolved:
                self._404(); return
            project, idea, design_dir, idea_dir = resolved
            if not os.path.isdir(idea_dir):
                self._404(); return
            self._save_layout(idea_dir)
            return

        self._404()

    def _handle_roots_api(self, action):
        """POST /api/roots/{add|remove|scan}"""
        # Never allow registry changes in share mode
        if self.share_token:
            self._json({'ok': False, 'error': 'Not allowed in share mode'}, 403)
            return

        body = self._read_json_body()
        if body is None:
            return

        if action == 'add':
            path_str = str(body.get('path') or '')
            name = str(body.get('name') or '').strip()
            err, real = _validate_design_path(path_str)
            if err:
                self._json({'ok': False, 'error': err}, 400)
                return
            if not name:
                parent = os.path.dirname(real)
                name = os.path.basename(parent) or os.path.basename(real)
            roots = load_roots_safe()
            existing_names = {r['name'] for r in roots}
            existing_paths = {os.path.realpath(r['path']) for r in roots}
            if name in existing_names:
                self._json({'ok': False, 'error': f'Name already in use: {name}'}, 409)
                return
            if real in existing_paths:
                dup = next(r for r in roots if os.path.realpath(r['path']) == real)
                self._json({'ok': False, 'error': f'Already registered: {dup["name"]}'}, 409)
                return
            roots.append({'name': name, 'path': real})
            save_roots_safe(roots)
            self._json({'ok': True, 'name': name, 'path': real})
            return

        if action == 'remove':
            name = str(body.get('name') or '').strip()
            if not name:
                self._json({'ok': False, 'error': 'The name field is required'}, 400)
                return
            roots = load_roots_safe()
            new_roots = [r for r in roots if r['name'] != name]
            if len(new_roots) == len(roots):
                self._json({'ok': False, 'error': f'Not found: {name}'}, 404)
                return
            save_roots_safe(new_roots)
            self._json({'ok': True, 'removed': name})
            return

        if action == 'scan':
            dirs = body.get('dirs', [])
            if not dirs or not isinstance(dirs, list):
                self._json({'ok': False, 'error': 'A dirs array is required'}, 400)
                return
            # Every dir must also be under HOME
            safe_dirs = []
            for d in dirs[:10]:
                real_d = os.path.realpath(os.path.expanduser(str(d)))
                if real_d.startswith(HOME + os.sep) or real_d == HOME:
                    if os.path.isdir(real_d):
                        safe_dirs.append(real_d)
            found = _scan_for_roots(safe_dirs, max_depth=5, timeout_secs=10)
            self._json({'ok': True, 'found': found})
            return

        self._json({'ok': False, 'error': 'Unknown API'}, 404)

    def _serve_registry_index(self):
        roots = self._roots()
        # Share mode: no absolute paths and no registry management UI
        share = bool(self.share_token)
        projects_html = ''
        for r in roots:
            name = r['name']
            path = r['path']
            exists = os.path.isdir(path)
            name_esc = _html.escape(name)
            path_esc = _html.escape(path)
            name_url = _urlquote(name, safe='')

            if share:
                if not exists:
                    continue
                path_html = ''
                remove_html = ''
            else:
                path_html = f'<span class="proj-path">{path_esc}</span>'
                remove_html = (f'<button class="btn-remove" data-name="{name_esc}" '
                               'onclick="removeProject(this.dataset.name)">Remove from list</button>')

            if not exists:
                projects_html += f'''
<section class="project missing">
  <div class="proj-header">
    <div class="proj-title">
      <span class="proj-name">{name_esc}</span>
      <span class="proj-path">{path_esc} <span class="missing-tag">missing</span></span>
    </div>
    <button class="btn-remove" data-name="{name_esc}" onclick="removeProject(this.dataset.name)">Remove from list</button>
  </div>
</section>'''
            else:
                ideas = []
                try:
                    for d in sorted(os.listdir(path)):
                        dp = os.path.join(path, d)
                        if os.path.isdir(dp) and os.path.exists(os.path.join(dp, 'canvas.json')):
                            canvas = load_canvas(dp)
                            cnt = len(canvas.get('boards', {}))
                            ideas.append((d, cnt))
                except Exception:
                    pass

                ideas_html = ''
                for idea, cnt in ideas:
                    idea_url = _urlquote(idea, safe='')
                    idea_esc = _html.escape(idea)
                    ideas_html += f'<a class="idea-link" href="/{name_url}/{idea_url}/">{idea_esc}<span class="cnt">{cnt} artboards</span></a>\n'
                if not ideas_html:
                    ideas_html = '<p class="no-ideas">No ideas yet</p>'

                projects_html += f'''
<section class="project">
  <div class="proj-header">
    <div class="proj-title">
      <span class="proj-name">{name_esc}</span>
      {path_html}
    </div>
    {remove_html}
  </div>
  <div class="ideas">{ideas_html}</div>
</section>'''

        manage_html = '' if share else _REGISTRY_MANAGE_HTML
        manage_script = '' if share else _REGISTRY_MANAGE_SCRIPT
        html = textwrap.dedent(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mockup Canvas</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#1e1e1e;font:15px/1.5 -apple-system,'Helvetica Neue',Arial,sans-serif;color:#e0e0e0;min-height:100vh;padding:32px 16px 64px}}
.wrap{{max-width:640px;margin:0 auto}}
h1{{color:#fff;font-size:22px;font-weight:700;margin-bottom:28px}}
h2{{color:#ccc;font-size:14px;font-weight:700;margin-bottom:16px;margin-top:36px;text-transform:uppercase;letter-spacing:.05em}}
.project{{background:#2a2a2a;border-radius:12px;margin-bottom:12px;overflow:hidden}}
.project.missing{{opacity:.55}}
.proj-header{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px}}
.proj-title{{min-width:0}}
.proj-name{{font-weight:700;font-size:16px;color:#fff;display:block}}
.proj-path{{font-size:12px;color:#888;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.missing-tag{{color:#f87171;margin-left:4px}}
.ideas{{padding:0 16px 14px;display:flex;flex-direction:column;gap:6px}}
.idea-link{{display:flex;justify-content:space-between;align-items:center;background:#1e1e1e;border-radius:8px;padding:10px 14px;color:#d0d0d0;text-decoration:none;font-weight:500;font-size:14px}}
.idea-link:hover{{background:#252525}}
.cnt{{font-weight:400;color:#888;font-size:12px}}
.no-ideas{{color:#666;font-size:13px;padding:4px 0}}
.btn-remove{{flex-shrink:0;background:transparent;border:1px solid #555;color:#999;border-radius:6px;padding:5px 10px;font-size:12px;cursor:pointer;white-space:nowrap}}
.btn-remove:hover{{background:#3a2020;border-color:#f87171;color:#f87171}}
.panel{{background:#242424;border:1px solid #383838;border-radius:12px;padding:20px;margin-top:12px}}
.field{{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}}
label{{font-size:13px;color:#aaa;font-weight:600}}
input[type=text]{{background:#1a1a1a;border:1px solid #444;border-radius:8px;padding:9px 12px;color:#e0e0e0;font-size:14px;outline:none;width:100%}}
input[type=text]:focus{{border-color:#2a52d4}}
.row{{display:flex;gap:8px}}
.row input[type=text]{{flex:1}}
.btn-primary{{background:#2a52d4;color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600;cursor:pointer;white-space:nowrap}}
.btn-primary:hover{{background:#3060e0}}
.btn-secondary{{background:#333;color:#ccc;border:none;border-radius:8px;padding:9px 14px;font-size:14px;cursor:pointer;white-space:nowrap}}
.btn-secondary:hover{{background:#3a3a3a}}
.msg{{font-size:13px;margin-top:10px;min-height:20px}}
.msg.ok{{color:#4ade80}}
.msg.err{{color:#f87171}}
.scan-results{{margin-top:14px;display:flex;flex-direction:column;gap:6px}}
.scan-item{{display:flex;align-items:center;gap:10px;background:#1e1e1e;border-radius:8px;padding:10px 12px}}
.scan-item label{{font-size:13px;color:#ccc;font-weight:400;cursor:pointer;flex:1;margin:0}}
.scan-item .scan-path{{font-size:11px;color:#666;display:block}}
.scan-item input[type=checkbox]{{width:16px;height:16px;cursor:pointer;flex-shrink:0}}
.tag-registered{{font-size:11px;color:#888;background:#333;padding:2px 6px;border-radius:4px;margin-left:6px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>Mockup Canvas</h1>
  <div id="projects">{projects_html if projects_html else '<p style="color:#666">No projects registered</p>'}</div>
{manage_html}
</div>

{manage_script}</body>
</html>""")

        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._add_root_header()
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    max_connections = 64   # concurrent connections; more get 503

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(self.max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\n'
                                b'Content-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

# ── serve ──────────────────────────────────────────────────────────────────

def cmd_serve(args):
    if _is_help(args):
        print('Usage: canvas.py serve [<design dir>] [--port 4400] [--share [--minutes 30] [--share-edit]]\n'
              '       canvas.py serve --share --project NAME   (registry mode: share one project)', flush=True)
        return

    # No arguments, or a flag first: registry mode
    if not args or args[0].startswith('--'):
        _cmd_serve_registry(args)
        return

    # Single-root mode
    design_dir = os.path.realpath(os.path.expanduser(args[0]))
    port = DEFAULT_PORT
    share = '--share' in args
    share_edit = '--share-edit' in args
    read_only = False

    if '--port' in args:
        idx = args.index('--port')
        port = int(args[idx + 1])
    minutes = _parse_minutes(args)

    existing_root = check_existing_server(port)
    if existing_root:
        if existing_root == _root_id(design_dir):
            print(f'Already running: http://127.0.0.1:{port}/')
            return
        else:
            new_port = find_free_port(port + 1)
            print(f'Another server is running on port {port} -> using port {new_port}')
            port = new_port

    bind_addr = '0.0.0.0' if share else '127.0.0.1'
    token = secrets.token_urlsafe(9) if share else ''

    lan_ip = get_lan_ip() if share else ''
    CanvasHandler.design_dir = design_dir
    CanvasHandler.share_token = token
    CanvasHandler.share_edit = share_edit or not share
    CanvasHandler.read_only = read_only
    CanvasHandler.share_host = lan_ip

    t = threading.Thread(target=_watch_thread, args=([(design_dir, '')],), daemon=True)
    t.start()

    server = ThreadedHTTPServer((bind_addr, port), CanvasHandler)

    if share:
        url_with_token = f'http://{lan_ip}:{port}/?t={token}'
        print(f'Share URL: {url_with_token}', flush=True)
        print(f'  {"editable" if share_edit else "read-only"}, stops automatically after {minutes} min', flush=True)

        def auto_stop():
            time.sleep(minutes * 60)
            print('\nShare time is over, stopping server', flush=True)
            server.shutdown()

        threading.Thread(target=auto_stop, daemon=True).start()
    else:
        print(f'Server started: http://127.0.0.1:{port}/', flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')


def _cmd_serve_registry(args):
    port = DEFAULT_PORT
    share = '--share' in args
    share_edit = '--share-edit' in args
    project = None
    if '--port' in args:
        idx = args.index('--port')
        port = int(args[idx + 1])
    minutes = _parse_minutes(args)
    if '--project' in args:
        idx = args.index('--project')
        project = args[idx + 1] if idx + 1 < len(args) else ''
        if not share:
            print('Error: --project is only used with --share', file=sys.stderr)
            sys.exit(2)

    existing = check_existing_server(port)
    if existing == REGISTRY_SENTINEL:
        print(f'Already running (registry mode): http://127.0.0.1:{port}/')
        return
    elif existing:
        new_port = find_free_port(port + 1)
        print(f'Another server is running on port {port} -> using port {new_port}')
        port = new_port

    roots = load_roots()
    if not roots:
        print('No projects registered. Add one first with: canvas roots add <design dir>')
        return
    if project is not None:
        roots = [r for r in roots if r['name'] == project]
        if not roots:
            print(f'Error: no registered project named {project!r} (see: canvas roots)', file=sys.stderr)
            sys.exit(2)

    bind_addr = '0.0.0.0' if share else '127.0.0.1'
    token = secrets.token_urlsafe(9) if share else ''
    lan_ip = get_lan_ip() if share else ''

    RegistryHandler.server_port = port
    RegistryHandler.share_token = token
    RegistryHandler.share_edit = share_edit or not share
    RegistryHandler.read_only = False
    RegistryHandler.share_host = lan_ip
    # A share serves the projects registered right now; later registry edits do not widen it
    RegistryHandler.frozen_roots = [dict(r) for r in roots] if share else None

    watch_list = [(r['path'], r['name'] + '/') for r in roots if os.path.isdir(r['path'])]
    t = threading.Thread(target=_watch_thread, args=(watch_list,), daemon=True)
    t.start()

    server = ThreadedHTTPServer((bind_addr, port), RegistryHandler)

    if share:
        url_with_token = f'http://{lan_ip}:{port}/?t={token}'
        print(f'Share URL: {url_with_token}', flush=True)
        scope = f'project {project}' if project is not None else f'{len(roots)} project(s)'
        print(f'  {"editable" if share_edit else "read-only"}, {scope}, stops automatically after {minutes} min', flush=True)

        def auto_stop():
            time.sleep(minutes * 60)
            print('\nShare time is over, stopping server', flush=True)
            server.shutdown()

        threading.Thread(target=auto_stop, daemon=True).start()
    else:
        print(f'Server started (registry mode): http://127.0.0.1:{port}/', flush=True)
        for r in roots:
            exists = 'ok' if os.path.isdir(r['path']) else 'missing'
            print(f'  {r["name"]}: {r["path"]} [{exists}]', flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')

# ── roots ──────────────────────────────────────────────────────────────────

def cmd_roots(args):
    if args and args[0] in ('-h', '--help'):
        print(textwrap.dedent("""
            Usage:
              canvas.py roots                              list projects
              canvas.py roots add <design dir> [--name N]  add a project
              canvas.py roots remove <name>                remove a project
              canvas.py roots scan <dir>...                find and add design folders
        """).strip())
        return

    sub = args[0] if args else 'list'
    rest = args[1:] if args else []

    if sub == 'list' or sub not in ('add', 'remove', 'scan'):
        roots = load_roots()
        if not roots:
            print('No projects registered')
            return
        for r in roots:
            path = r['path']
            exists = os.path.isdir(path)
            ideas = []
            if exists:
                try:
                    for d in os.listdir(path):
                        if os.path.isdir(os.path.join(path, d)) and \
                           os.path.exists(os.path.join(path, d, 'canvas.json')):
                            ideas.append(d)
                except Exception:
                    pass
            e_mark = 'ok' if exists else 'missing'
            print(f'{r["name"]:25s}  {path}  ({len(ideas)} ideas)  {e_mark}')
        return

    if sub == 'add':
        if not rest or _is_help(rest):
            print('Usage: canvas.py roots add <design dir> [--name N]')
            return
        design_dir_arg = rest[0]
        name = None
        if '--name' in rest:
            name = rest[rest.index('--name') + 1]
        design_abs = os.path.realpath(os.path.expanduser(design_dir_arg))
        if name is None:
            parent = os.path.dirname(design_abs)
            name = os.path.basename(parent) or os.path.basename(design_abs)
        roots = load_roots()
        for r in roots:
            if r['name'] == name:
                print(f'Already registered (same name): {name} ({r["path"]})')
                return
            if os.path.realpath(r['path']) == design_abs:
                print(f'Already registered (same path): {r["name"]} -> {design_abs}')
                return
        roots.append({'name': name, 'path': design_abs})
        save_roots(roots)
        print(f'Registered: {name} -> {design_abs}')
        return

    if sub == 'remove':
        if not rest:
            print('Usage: canvas.py roots remove <name>')
            return
        name = rest[0]
        roots = load_roots()
        new_roots = [r for r in roots if r['name'] != name]
        if len(new_roots) == len(roots):
            print(f'Not found: {name}')
            return
        save_roots(new_roots)
        print(f'Removed: {name}')
        return

    if sub == 'scan':
        if not rest or _is_help(rest):
            print('Usage: canvas.py roots scan <dir>...')
            return
        scan_dirs = [os.path.expanduser(d) for d in rest]
        found = _scan_for_roots(scan_dirs)
        if not found:
            print('No design folders found')
            return
        roots = load_roots()
        existing_paths = {os.path.realpath(r['path']) for r in roots}
        existing_names = {r['name'] for r in roots}
        added = []
        for item in found:
            real = os.path.realpath(item['path'])
            if real in existing_paths:
                print(f'Skipped (already registered): {item["name"]} -> {item["path"]}')
                continue
            name = item['name']
            # Resolve name clashes
            base_name = name
            suffix = 2
            while name in existing_names:
                name = f'{base_name}-{suffix}'
                suffix += 1
            roots.append({'name': name, 'path': item['path']})
            existing_names.add(name)
            existing_paths.add(real)
            added.append(f'{name} -> {item["path"]}')
        if added:
            save_roots(roots)
            for a in added:
                print(f'Added: {a}')
        else:
            print('Nothing new to add')
        return

# ── new ────────────────────────────────────────────────────────────────────

def cmd_new(args):
    if len(args) < 2 or _is_help(args):
        print('Usage: canvas.py new <design dir> <idea>'); return
    design_dir, idea = args[0], args[1]
    design_abs = os.path.realpath(os.path.expanduser(design_dir))

    # Register the design folder automatically if it is new
    roots = load_roots()
    if not any(os.path.realpath(r['path']) == design_abs for r in roots):
        parent = os.path.dirname(design_abs)
        name = os.path.basename(parent) or os.path.basename(design_abs)
        existing_names = {r['name'] for r in roots}
        base_name = name
        suffix = 2
        while name in existing_names:
            name = f'{base_name}-{suffix}'
            suffix += 1
        roots.append({'name': name, 'path': design_abs})
        save_roots(roots)
        print(f'Registered design folder: {name} -> {design_abs}')

    idea_dir = os.path.join(design_abs, idea)
    for d in ('boards', 'assets', 'render', 'shared'):
        os.makedirs(os.path.join(idea_dir, d), exist_ok=True)
    cj = os.path.join(idea_dir, 'canvas.json')
    if not os.path.exists(cj):
        save_canvas_atomic(cj, {'boards': {}, 'groups': [], 'links': []})

    tokens_css = os.path.join(idea_dir, 'shared', 'tokens.css')
    if not os.path.exists(tokens_css):
        template = textwrap.dedent("""\
            /* Shared design tokens
             * Link them from boards/*.html like this:
             *   <link rel="stylesheet" href="../shared/tokens.css">
             */

            :root {
              /* Color */
              --color-primary: #2a52d4;
              --color-primary-dark: #1e3fa8;
              --color-bg: #ffffff;
              --color-bg-secondary: #f5f5f5;
              --color-surface: #ffffff;
              --color-border: #e0e0e0;
              --color-text: #1a1a1a;
              --color-text-secondary: #666666;
              --color-text-placeholder: #aaaaaa;

              /* Type */
              --font-sans: -apple-system, 'Helvetica Neue', Arial, sans-serif;
              --font-size-xs: 11px;
              --font-size-sm: 13px;
              --font-size-base: 15px;
              --font-size-lg: 18px;
              --font-size-xl: 22px;

              /* Spacing */
              --space-1: 4px;
              --space-2: 8px;
              --space-3: 12px;
              --space-4: 16px;
              --space-6: 24px;
              --space-8: 32px;

              /* Radius */
              --radius-sm: 6px;
              --radius-md: 12px;
              --radius-lg: 20px;
              --radius-full: 9999px;
            }
        """)
        with open(tokens_css, 'w', encoding='utf-8') as f:
            f.write(template)

    gitignore = os.path.join(idea_dir, '.gitignore')
    if not os.path.exists(gitignore):
        with open(gitignore, 'w', encoding='utf-8') as f:
            f.write('render/\n')

    print(f'Created: {idea_dir}')

# ── add ────────────────────────────────────────────────────────────────────

def cmd_add(args):
    if len(args) < 2 or _is_help(args):
        print('Usage: canvas.py add <idea dir> <file> [--group NAME] [--size mobile|tablet|desktop|WxH]'); return
    idea_dir = os.path.abspath(args[0])
    src = os.path.abspath(args[1])
    group = None
    size_override = None
    if '--group' in args:
        group = args[args.index('--group') + 1]
    if '--size' in args:
        sv = args[args.index('--size') + 1]
        if sv in SIZE_PRESETS:
            size_override = SIZE_PRESETS[sv]
        else:
            m = re.match(r'^(\d+)[xX](\d+)$', sv)
            if m:
                size_override = (int(m.group(1)), int(m.group(2)))
            else:
                print(f'Unknown size: {sv} (use mobile|tablet|desktop|WxH)'); return

    fname = os.path.basename(src)
    boards_dir = os.path.join(idea_dir, 'boards')
    dest = os.path.join(boards_dir, fname)
    os.makedirs(boards_dir, exist_ok=True)

    if os.path.isfile(src) and os.path.abspath(src) != os.path.abspath(dest):
        if os.path.isfile(dest):
            import filecmp
            if not filecmp.cmp(src, dest, shallow=False):
                print(f'Error: a different file already exists at boards/{fname}. Check it manually.')
                return
        else:
            shutil.copy2(src, dest)
            print(f'Copied: {src} -> {dest}')

    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    boards = canvas.setdefault('boards', {})
    if fname not in boards:
        if size_override:
            w, h = size_override
        else:
            w, h = DEFAULT_W, DEFAULT_H
            if os.path.isfile(dest):
                try:
                    content = open(dest, encoding='utf-8').read()
                    m = re.search(r'width:\s*(\d+)px[^;]*;[^"]*height:\s*(\d+)px', content[:3000])
                    if m:
                        w, h = int(m.group(1)), int(m.group(2))
                except Exception:
                    pass
        x, y = find_free_x(boards, w)
        entry = {'x': x, 'y': y, 'w': w, 'h': h, 'title': fname.replace('.html', '')}
        if group:
            entry['group'] = group
            _ensure_group(canvas, group)
        boards[fname] = entry
        save_canvas_atomic(cj, canvas)
        print(f'Registered: {fname} -> ({x}, {y})  {w}x{h}')
    else:
        print(f'Already registered: {fname}')

# ── render ─────────────────────────────────────────────────────────────────

def cmd_render(args):
    if not args or _is_help(args):
        print('Usage: canvas.py render <idea dir> [file...]'); return
    idea_dir = os.path.abspath(args[0])
    files = [os.path.basename(f) for f in args[1:]] if len(args) > 1 else []

    boards_dir = os.path.join(idea_dir, 'boards')
    render_dir = os.path.join(idea_dir, 'render')
    os.makedirs(render_dir, exist_ok=True)

    canvas = load_canvas(idea_dir)
    boards = canvas.get('boards', {})

    if not files:
        files = [f for f in os.listdir(boards_dir) if f.endswith('.html')]

    failed = []
    for fname in files:
        src = os.path.join(boards_dir, fname)
        if not os.path.isfile(src):
            print(f'Not found: {fname}'); continue
        b = boards.get(fname, {})
        w, h = b.get('w', DEFAULT_W), b.get('h', DEFAULT_H)
        out = os.path.join(render_dir, fname.replace('.html', '.png'))
        result = _run_chrome(w, h, 3000, out, pathlib.Path(src).as_uri())
        if result.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
            print(f'Error: render failed ({fname})', file=sys.stderr)
            failed.append(fname)
        else:
            print(f'Rendered: {out}')
    if failed:
        sys.exit(1)

# ── overview ───────────────────────────────────────────────────────────────

def cmd_overview(args):
    if not args or _is_help(args):
        print('Usage: canvas.py overview <idea dir>'); return
    idea_dir = os.path.abspath(args[0])
    canvas = load_canvas(idea_dir)
    boards = canvas.get('boards', {})
    if not boards:
        print('No artboards'); return

    xs  = [b['x'] for b in boards.values()]
    ys  = [b['y'] for b in boards.values()]
    x2s = [b['x'] + b['w'] for b in boards.values()]
    y2s = [b['y'] + b['h'] for b in boards.values()]
    total_w = max(x2s) - min(xs) + 160
    total_h = max(y2s) - min(ys) + 200

    TARGET_W = 2400
    scale = min(1, TARGET_W / total_w)
    out_w = max(600, int(total_w * scale))
    out_h = max(600, int(total_h * scale))

    render_dir = os.path.join(idea_dir, 'render')
    os.makedirs(render_dir, exist_ok=True)
    out_png = os.path.join(render_dir, '_overview.png')

    tmp_dir = os.path.join(render_dir, '_overview_tmp')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    boards_src = os.path.join(idea_dir, 'boards')
    if os.path.isdir(boards_src):
        _copytree_inside(boards_src, os.path.join(tmp_dir, 'boards'), idea_dir)
    else:
        os.makedirs(os.path.join(tmp_dir, 'boards'))

    for sub in ('assets', 'shared'):
        sub_src = os.path.join(idea_dir, sub)
        if os.path.isdir(sub_src):
            _copytree_inside(sub_src, os.path.join(tmp_dir, sub), idea_dir)

    viewer_src = open(VIEWER_PATH, encoding='utf-8').read()
    canvas_json_str = _embed_json(canvas)
    inject = (
        '\n<script id="canvas-data-script">'
        f'var STATIC_CANVAS = {canvas_json_str};'
        '</script>\n'
    )
    static_html = viewer_src.replace('</head>', inject + '</head>', 1)
    tmp_index = os.path.join(tmp_dir, 'index.html')
    with open(tmp_index, 'w', encoding='utf-8') as f:
        f.write(static_html)

    try:
        result = _run_chrome(out_w, out_h, 5000, out_png,
                             pathlib.Path(tmp_index).as_uri() + '?overview=1')

        if result.returncode != 0 or not os.path.isfile(out_png) or os.path.getsize(out_png) == 0:
            print(f'Error: overview render failed (Chrome exit code: {result.returncode})', file=sys.stderr)
            sys.exit(1)

        print(f'Overview: {out_png}  ({out_w}x{out_h}px)')
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ── check ──────────────────────────────────────────────────────────────────

def cmd_check(args):
    if not args or _is_help(args):
        print('Usage: canvas.py check <idea dir>'); return
    idea_dir = os.path.abspath(args[0])
    boards_dir = os.path.join(idea_dir, 'boards')
    canvas = load_canvas(idea_dir)
    boards = canvas.get('boards', {})
    errors = []

    for fname in list(boards.keys()):
        fpath = os.path.join(boards_dir, fname)
        if not os.path.isfile(fpath):
            errors.append(f'missing file in boards: {fname}')
            continue
        try:
            content = open(fpath, encoding='utf-8', errors='replace').read()
        except Exception as e:
            errors.append(f'{fname}: read error - {e}')
            continue

        refs = set()
        refs.update(re.findall(r'src=["\']([^"\']+)["\']', content))
        refs.update(re.findall(r'href=["\']([^"\']+)["\']', content))
        refs.update(re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', content))
        for ref in refs:
            if ref.startswith(('http', 'data:', '#', 'javascript:', 'mailto:')):
                continue
            ref_path = os.path.normpath(os.path.join(os.path.dirname(fpath), ref))
            if not os.path.exists(ref_path):
                errors.append(f'{fname}: broken reference -> {ref}')

    if os.path.isdir(boards_dir):
        for fname in os.listdir(boards_dir):
            if fname.endswith('.html') and fname not in boards:
                errors.append(f'not registered in canvas.json: {fname}')

    blist = list(boards.items())
    for i in range(len(blist)):
        for j in range(i + 1, len(blist)):
            na, a = blist[i]
            nb, b = blist[j]
            if (a['x'] < b['x'] + b['w'] and a['x'] + a['w'] > b['x'] and
                    a['y'] < b['y'] + b['h'] and a['y'] + a['h'] > b['y']):
                errors.append(f'overlap: {na} <-> {nb}')

    # Optional user rule: characters that must not appear in artboards
    forbidden = [c for c in load_config().get('forbidden_chars', []) if isinstance(c, str) and c]
    if forbidden and os.path.isdir(boards_dir):
        for fname in os.listdir(boards_dir):
            if not fname.endswith('.html'):
                continue
            fpath = os.path.join(boards_dir, fname)
            try:
                content = open(fpath, encoding='utf-8', errors='replace').read()
            except Exception:
                continue
            for ch in forbidden:
                if ch in content:
                    code = ' '.join(f'U+{ord(c):04X}' for c in ch)
                    errors.append(f'forbidden character ({code}) found: {fname}')

    for lnk in canvas.get('links', []):
        for end in ('from', 'to'):
            if lnk.get(end) not in boards:
                errors.append(f'link {end} is not a registered board: {lnk.get("from")} -> {lnk.get("to")}')

    approved = sum(1 for b in boards.values() if b.get('status') == 'approved')
    print(f'Approved boards: {approved}/{len(boards)}')

    if errors:
        for e in errors:
            print('Error:', e)
        print(f'\n{len(errors)} problem(s) total')
    else:
        print('All good (0 problems)')
    return len(errors)

# ── link ───────────────────────────────────────────────────────────────────

def cmd_link(args):
    if len(args) < 3 or _is_help(args):
        print('Usage: canvas.py link <idea dir> <from file> <to file> [--label TEXT]'); return
    idea_dir = os.path.abspath(args[0])
    from_file = args[1]
    to_file = args[2]
    label = None
    if '--label' in args:
        label = args[args.index('--label') + 1]

    from_file = _board_key(from_file)
    to_file = _board_key(to_file)

    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    boards = canvas.get('boards', {})
    missing = [f for f in (from_file, to_file) if f not in boards]
    if missing:
        for f in missing:
            print(f'Error: no such board registered: {f}', file=sys.stderr)
        return 1
    links = canvas.setdefault('links', [])

    for lnk in links:
        if lnk['from'] == from_file and lnk['to'] == to_file:
            print(f'Already linked: {from_file} -> {to_file}')
            return

    entry = {'from': from_file, 'to': to_file}
    if label:
        entry['label'] = label
    links.append(entry)
    save_canvas_atomic(cj, canvas)
    desc = f' ({label})' if label else ''
    print(f'Link added: {from_file} -> {to_file}{desc}')

# ── status ──────────────────────────────────────────────────────────────────

def cmd_status(args):
    if len(args) < 3 or _is_help(args):
        print('Usage: canvas.py status <idea dir> <file> <draft|approved|rejected> [--note TEXT]'); return
    idea_dir = os.path.abspath(args[0])
    file_arg = args[1]
    status_val = args[2]
    if status_val not in ('draft', 'approved', 'rejected'):
        print(f'Unknown status: {status_val}  (one of draft|approved|rejected)', file=sys.stderr); return 1
    note = None
    if '--note' in args:
        note = args[args.index('--note') + 1]

    file_arg = _board_key(file_arg)

    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    boards = canvas.setdefault('boards', {})
    if file_arg not in boards:
        print(f'Error: no such board registered: {file_arg}', file=sys.stderr); return 1

    if status_val == 'draft':
        boards[file_arg].pop('status', None)
        boards[file_arg].pop('note', None)
    else:
        boards[file_arg]['status'] = status_val
    if note is not None:
        boards[file_arg]['note'] = note

    save_canvas_atomic(cj, canvas)
    desc = f'  (note: {note})' if note else ''
    print(f'Status set: {file_arg} -> {status_val}{desc}')

# ── group ───────────────────────────────────────────────────────────────────

def cmd_group(args):
    if len(args) < 3 or _is_help(args):
        print('Usage: canvas.py group <idea dir> <file> <group name>'); return
    idea_dir = os.path.abspath(args[0])
    file_arg = args[1]
    group_name = args[2]
    file_arg = _board_key(file_arg)

    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    boards = canvas.setdefault('boards', {})
    if file_arg not in boards:
        print(f'Error: no such board registered: {file_arg}', file=sys.stderr); return 1

    boards[file_arg]['group'] = group_name
    _ensure_group(canvas, group_name)
    save_canvas_atomic(cj, canvas)
    print(f'Group set: {file_arg} -> {group_name}')

# ── artifact ────────────────────────────────────────────────────────────────

def cmd_artifact(args):
    if not args or _is_help(args):
        print('Usage: canvas.py artifact <idea dir> [url]'); return
    idea_dir = os.path.abspath(args[0])
    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)

    if len(args) >= 2:
        url = args[1]
        canvas['artifact_url'] = url
        save_canvas_atomic(cj, canvas)
        print(f'artifact_url set: {url}')
    else:
        url = canvas.get('artifact_url', '')
        print(url if url else '(none)')

# ── export ─────────────────────────────────────────────────────────────────

def cmd_export(args):
    if len(args) < 2 or _is_help(args):
        print('Usage: canvas.py export <idea dir> <output dir>'); return
    idea_dir = os.path.realpath(args[0])
    outdir = os.path.realpath(args[1])
    if _within(outdir, idea_dir) or _within(idea_dir, outdir):
        print('Error: the output folder must not be the idea folder, inside it, or contain it', file=sys.stderr)
        return 1
    os.makedirs(outdir, exist_ok=True)

    canvas = load_canvas(idea_dir)

    for subdir in ('boards', 'assets', 'shared'):
        src_dir = os.path.join(idea_dir, subdir)
        dst_dir = os.path.join(outdir, subdir)
        if os.path.isdir(src_dir):
            if os.path.islink(dst_dir) or os.path.isfile(dst_dir):
                os.remove(dst_dir)
            elif os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
            _copytree_inside(src_dir, dst_dir, idea_dir)

    viewer_src = open(VIEWER_PATH, encoding='utf-8').read()
    canvas_json_str = _embed_json(canvas)
    inject = (
        '\n<script id="canvas-data-script">'
        f'var STATIC_CANVAS = {canvas_json_str};'
        '</script>\n'
    )
    static_viewer = viewer_src.replace('</head>', inject + '</head>', 1)
    with open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(static_viewer)
    print(f'Exported: {outdir}')
    print(f'  boards: {len(canvas.get("boards", {}))}, assets copied')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
        _s.bind(('127.0.0.1', 0))
        port = _s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
        cwd=outdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        time.sleep(1.5)
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/')
        resp = conn.getresponse()
        conn.close()
        if resp.status == 200:
            print(f'Check OK: http://127.0.0.1:{port}/ (server stopped)')
        else:
            print(f'Check failed: HTTP {resp.status}')
    except Exception as e:
        print(f'Check error: {e}')
    finally:
        proc.terminate()
        proc.wait()

# ── main ───────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(line_buffering=True)
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); return
    cmd = sys.argv[1]
    migrate_legacy_roots()
    dispatch = {
        'serve': cmd_serve, 'roots': cmd_roots,
        'new': cmd_new, 'add': cmd_add,
        'render': cmd_render, 'check': cmd_check,
        'overview': cmd_overview, 'export': cmd_export,
        'link': cmd_link, 'status': cmd_status, 'artifact': cmd_artifact,
        'group': cmd_group,
    }
    if cmd in dispatch:
        ret = dispatch[cmd](sys.argv[2:])
        if isinstance(ret, int) and ret != 0:
            sys.exit(1)
    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)

if __name__ == '__main__':
    main()
