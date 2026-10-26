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
  render <idea dir> [file...] [--full-page] [--wait MS]
  check <idea dir>
  overview <idea dir>
  export <idea dir> <output dir>
  link <idea dir> <from file> <to file> [--label TEXT]
  status <idea dir> <file> <draft|approved|rejected> [--note TEXT]
  artifact <idea dir> [url]
  snap <url> --out FILE.png [--size mobile|tablet|desktop|WxH] [--wait MS] [--full-page]
  compare <idea dir> <file> (--url URL | --png FILE) [--out DIR] [--threshold N] [--wait MS]
          [--ignore-top N] [--ignore-bottom N] [--align-top N]
  impl <idea dir> [--strict]
  impl <idea dir> <file> --route PATH [--file PATH]... | --clear
  comment <idea dir> <file> [TEXT [--by NAME] | --clear]

Run any command with -h/--help to see its usage.

User data lives in ~/.mockup-canvas/ (override with MOCKUP_CANVAS_HOME):
  roots.json   registered design folders (registry mode)
  config.json  options, e.g. {"forbidden_chars": ["\u2014"]}
"""
import sys, os, json, re, shutil, subprocess, time, threading, tempfile, pathlib, signal
import socketserver, socket, secrets, mimetypes, http.client, textwrap
import hmac, hashlib, base64, ipaddress
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
    return [_get_chrome(), '--headless=new', '--use-mock-keychain', f'--user-data-dir={profile_dir}',
            '--no-first-run', '--no-default-browser-check',
            # Keep sandboxed board iframes in-process so --screenshot captures them
            # (they stay sandboxed with an opaque origin either way)
            '--disable-features=IsolateSandboxedIframes',
            f'--window-size={w},{h}', '--hide-scrollbars',
            f'--virtual-time-budget={budget_ms}']

# ── Chrome processes ───────────────────────────────────────────────────────
# Every Chrome canvas.py starts goes through _Chrome: its profile is registered before Chrome
# starts, Chrome is started under the registry lock in its own process group, and kill() takes
# the whole group (renderer and GPU helpers too) and deletes the profile. _kill_all_chrome() runs
# at exit (Ctrl+C, SIGTERM, an exception), so no Chrome or profile outlives the command.

CHROME_PROFILE_PREFIX = 'mockup-canvas-chrome-'
_CHROME_LOCK = threading.Lock()
_CHROMES = set()
_CHROME_SHUTDOWN = False


def _ps_commands():
    """-> [(pid, command line)] of all processes, or None when ps fails."""
    try:
        out = subprocess.run(['ps', '-A', '-ww', '-o', 'pid=,command='],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(' ')
        if pid.isdigit():
            rows.append((int(pid), cmd))
    return rows


def _uses_profile(cmd, profile):
    return f'--user-data-dir={profile}' in cmd


class _Chrome:
    """One Chrome process and its throwaway profile (see the section comment)."""

    def __init__(self):
        mask = getattr(signal, 'pthread_sigmask', None)
        blocked = {signal.SIGINT, signal.SIGTERM}
        if mask:   # Ctrl+C or SIGTERM between mkdtemp and registering would leave the folder
            mask(signal.SIG_BLOCK, blocked)
        try:
            self.profile = tempfile.mkdtemp(prefix=CHROME_PROFILE_PREFIX)
            self.proc, self.spawning, self.dead = None, False, False
            with _CHROME_LOCK:
                _CHROMES.add(self)
        finally:
            if mask:
                mask(signal.SIG_UNBLOCK, blocked)

    def spawn(self, args):
        """Start Chrome. Raises CdpConnectError once kill() or shutdown has run, OSError if it
        cannot start."""
        with _CHROME_LOCK:
            if self.dead or _CHROME_SHUTDOWN:
                raise CdpConnectError('Chrome is shutting down')
            self.spawning = True
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         start_new_session=True)
        return self.proc

    def kill(self):
        """Kill Chrome's process group and delete the profile. Safe to call more than once."""
        with _CHROME_LOCK:
            self.dead = True
            _CHROMES.discard(self)
            proc, spawning = self.proc, self.spawning
        if proc is not None:
            if proc.returncode is None:   # not reaped yet, so the group id is still ours
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                pass
        elif spawning:
            # Interrupted inside Popen: find the Chrome by its profile
            for pid, cmd in _ps_commands() or ():
                if _uses_profile(cmd, self.profile):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
        shutil.rmtree(self.profile, ignore_errors=True)


def _kill_all_chrome():
    """At exit: refuse new Chrome starts, then kill every Chrome started so far."""
    global _CHROME_SHUTDOWN
    with _CHROME_LOCK:   # waits for a start in progress, so its process is registered
        _CHROME_SHUTDOWN = True
        chromes = list(_CHROMES)
    for c in chromes:
        c.kill()


def _clean_stale_profiles(max_age=3600):
    """Delete mockup-canvas-chrome-* temp profiles older than max_age seconds that no running
    process uses (left by a crash or `kill -9`). Returns how many were deleted."""
    base = tempfile.gettempdir()
    try:
        names = [n for n in os.listdir(base) if n.startswith(CHROME_PROFILE_PREFIX)]
    except OSError:
        return 0
    if not names:
        return 0
    procs = _ps_commands()
    if procs is None:   # cannot tell which are in use: keep them all
        return 0
    with _CHROME_LOCK:
        mine = {c.profile for c in _CHROMES}
    removed = 0
    now = time.time()
    for n in names:
        path = os.path.join(base, n)
        try:
            if os.path.islink(path) or not os.path.isdir(path) or now - os.stat(path).st_mtime < max_age:
                continue
        except OSError:
            continue
        if path in mine or any(_uses_profile(cmd, path) for _, cmd in procs):
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    return removed


def _run_chrome(w, h, budget_ms, out_png, url, timeout=None):
    """Old capture path (--screenshot). Headless Chrome keeps the window at least 500 px wide,
    so narrower sizes are laid out at 500 px and cropped. Only used when DevTools fails.
    -> Chrome's exit code; raises subprocess.TimeoutExpired."""
    chrome = _Chrome()
    try:
        proc = chrome.spawn(_chrome_args(chrome.profile, w, h, budget_ms) + [f'--screenshot={out_png}', url])
        return proc.wait(timeout)
    finally:
        chrome.kill()

# ── Chrome DevTools capture ────────────────────────────────────────────────
# render, overview, snap, and compare drive Chrome over the DevTools protocol so the page is laid
# out at the exact requested width (Emulation.setDeviceMetricsOverride) and --wait is real time.


FULL_PAGE_MAX_H = 16384   # --full-page height cap (a taller PNG is mostly a runaway page)
MAX_BOARD_SIDE = 8000     # board w/h from canvas.json are clamped to this for render and compare


class CdpConnectError(RuntimeError):
    """Could not reach Chrome's DevTools endpoint (the caller falls back to --screenshot)."""


class CdpError(RuntimeError):
    """DevTools was reachable but the capture failed."""


WS_MAX_MESSAGE = 256 << 20   # largest DevTools message accepted (a big screenshot is well under)


class _WebSocket:
    """Minimal RFC 6455 client: text frames, masked client frames, fragments, ping/pong, close."""

    def __init__(self, host, port, path, timeout):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        try:
            self._handshake(host, port, path)
        except BaseException:
            self.sock.close()   # connect is retried; do not leak a socket per attempt
            raise

    def _handshake(self, host, port, path):
        self.buf = bytearray()
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n'
                           f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                           'Sec-WebSocket-Version: 13\r\n\r\n').encode())
        while b'\r\n\r\n' not in self.buf:
            self._fill()
        head, rest = bytes(self.buf).split(b'\r\n\r\n', 1)
        self.buf = bytearray(rest)
        lines = head.decode('latin-1').split('\r\n')
        if not lines[0].startswith('HTTP/1.1 101'):
            raise ConnectionError(f'WebSocket handshake refused: {lines[0]}')
        accept = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        headers = {l.split(':', 1)[0].strip().lower(): l.split(':', 1)[1].strip()
                   for l in lines[1:] if ':' in l}
        if headers.get('sec-websocket-accept') != accept:
            raise ConnectionError('WebSocket handshake: bad Sec-WebSocket-Accept')

    def _fill(self):
        chunk = self.sock.recv(1 << 16)
        if not chunk:
            raise ConnectionError('WebSocket closed by Chrome')
        self.buf += chunk

    def _read(self, n):
        while len(self.buf) < n:
            self._fill()
        data = bytes(self.buf[:n])
        del self.buf[:n]
        return data

    @staticmethod
    def encode_frame(opcode, payload, mask=None):
        """One FIN frame; client frames are always masked."""
        mask = os.urandom(4) if mask is None else mask
        n = len(payload)
        if n < 126:
            head = bytes([0x80 | opcode, 0x80 | n])
        elif n < 1 << 16:
            head = bytes([0x80 | opcode, 0x80 | 126]) + n.to_bytes(2, 'big')
        else:
            head = bytes([0x80 | opcode, 0x80 | 127]) + n.to_bytes(8, 'big')
        return head + mask + _ws_mask(payload, mask)

    def send(self, opcode, payload):
        self.sock.sendall(self.encode_frame(opcode, payload))

    def send_text(self, text):
        self.send(0x1, text.encode('utf-8'))

    def recv_text(self):
        """Next complete text message; answers pings and raises on close."""
        parts, kind, total = [], None, 0
        while True:
            b0, b1 = self._read(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = int.from_bytes(self._read(2), 'big')
            elif n == 127:
                n = int.from_bytes(self._read(8), 'big')
            total += n
            if total > WS_MAX_MESSAGE:   # checked before reading the payload
                raise ConnectionError(f'DevTools message over {WS_MAX_MESSAGE >> 20} MB')
            mask = self._read(4) if b1 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = _ws_mask(payload, mask)
            if opcode == 0x9:                       # ping
                self.send(0xA, payload)
                continue
            if opcode == 0xA:                       # pong
                continue
            if opcode == 0x8:                       # close
                try:
                    self.send(0x8, payload[:2])
                except OSError:
                    pass
                raise ConnectionError('WebSocket closed by Chrome')
            if opcode in (0x1, 0x2):
                parts, kind = [payload], opcode
            elif opcode == 0x0 and kind is not None:
                parts.append(payload)
            else:
                raise ConnectionError(f'unexpected WebSocket frame (opcode {opcode})')
            if fin:
                return b''.join(parts).decode('utf-8')

    def close(self):
        try:
            self.send(0x8, (1000).to_bytes(2, 'big'))
        except OSError:
            pass
        self.sock.close()


def _ws_mask(data, mask):
    """XOR data with the repeating 4-byte mask (done on one big int for speed)."""
    n = len(data)
    if not n:
        return b''
    key = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'big') ^ int.from_bytes(key, 'big')).to_bytes(n, 'big')


class _Cdp:
    def __init__(self, ws, deadline):
        self.ws, self.deadline, self.next_id, self.events = ws, deadline, 0, []
        self.sink = None   # set to a list to keep every event message (perf tracing)
        self.handler = None   # called with every event message as it arrives

    def _recv(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError
        self.ws.sock.settimeout(left)
        try:
            return json.loads(self.ws.recv_text())
        except socket.timeout:
            raise TimeoutError

    def send(self, method, _session=None, **params):
        """Send without waiting; the reply is skipped by whichever call() reads it.
        _session: an attached child target's sessionId (flat mode)."""
        self.next_id += 1
        msg = {'id': self.next_id, 'method': method, 'params': params}
        if _session:
            msg['sessionId'] = _session
        self.ws.send_text(json.dumps(msg))
        return self.next_id

    def call(self, method, **params):
        mid = self.send(method, **params)
        while True:
            msg = self._recv()
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise CdpError(f'{method}: {msg["error"].get("message", msg["error"])}')
                return msg.get('result', {})
            if 'method' in msg:
                self._event(msg)

    def _event(self, msg):
        self.events.append(msg['method'])
        if self.sink is not None:
            self.sink.append(msg)
        if self.handler:
            self.handler(msg)

    def wait_event(self, name):
        if name in self.events:
            return
        while True:
            msg = self._recv()
            if 'method' in msg:
                self._event(msg)
                if msg['method'] == name:
                    return


def _cdp_launch_args(profile_dir, background=False):
    """Headless Chrome flags for the DevTools path. No file-access flags; throwaway profile;
    DevTools listens on a random localhost port that only this run uses.

    background (viewer thumbnails): software rendering and one renderer process, so it does not
    compete with the viewer's browser for the GPU, and a lower CPU priority (nice) that Chrome's
    helper processes inherit."""
    args = [_get_chrome(), '--headless=new', '--use-mock-keychain', f'--user-data-dir={profile_dir}',
            '--no-first-run', '--no-default-browser-check',
            '--disable-features=IsolateSandboxedIframes', '--hide-scrollbars',
            '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1', 'about:blank']
    if not background:
        return args
    args[1:1] = ['--disable-gpu', '--renderer-process-limit=1']
    nice = shutil.which('nice')
    return [nice, '-n', '10'] + args if nice else args   # nice execs Chrome: same pid


def _cdp_get_json(port, path, timeout):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request('GET', path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise ConnectionError(f'GET {path}: HTTP {resp.status}')
        return json.loads(body)
    finally:
        conn.close()


def _cdp_page_ws(port, timeout):
    """-> websocket path of the first page target."""
    _cdp_get_json(port, '/json/version', timeout)   # the browser endpoint answers first
    for t in _cdp_get_json(port, '/json/list', timeout):
        if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
            return urlparse(t['webSocketDebuggerUrl']).path
    raise ConnectionError('no page target')


_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    '0.0.0.0/8', '10.0.0.0/8', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16',
    '::/128', '::1/128', 'fc00::/7', 'fe80::/10')]
_DNS_TIMEOUT = 2
_DNS_CACHE_SECS = 60
_DNS_CACHE = {}   # host -> (blocked, time checked)
_DNS_LOCK = threading.Lock()


def _ip_blocked(text):
    """True for a loopback, private, link-local, or unspecified address. ValueError if text is
    not an IP literal."""
    ip = ipaddress.ip_address(text.split('%', 1)[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified or
            any(ip in n for n in _BLOCKED_NETS))


def _host_blocked(host):
    """True when a board render must not reach host: localhost names, private IP literals, and
    names that resolve to any private address. A lookup that fails or times out blocks too."""
    host = (host or '').rstrip('.').lower()
    if not host or host == 'localhost' or host.endswith(('.localhost', '.local')):
        return True
    try:
        return _ip_blocked(host)
    except ValueError:
        pass
    now = time.monotonic()
    with _DNS_LOCK:
        hit = _DNS_CACHE.get(host)
    if hit and now - hit[1] < _DNS_CACHE_SECS:
        return hit[0]
    found = []

    def lookup():
        try:
            found.append({a[4][0] for a in socket.getaddrinfo(host, None)})
        except (OSError, UnicodeError):
            found.append(set())
    t = threading.Thread(target=lookup, daemon=True)
    t.start()
    t.join(_DNS_TIMEOUT)
    addrs = found[0] if found else set()
    blocked = not addrs or any(_ip_blocked(a) for a in addrs)
    with _DNS_LOCK:
        _DNS_CACHE[host] = (blocked, now)
    return blocked


class _CdpSession:
    """One headless Chrome with a throwaway profile, driven over DevTools.

    Raises CdpConnectError when DevTools cannot be reached. close() always kills Chrome and
    deletes the profile. capture() can be called many times (thumbnails reuse one Chrome).

    block_private (board renders and thumbnails): http(s) requests to localhost or a private
    network are failed too, so a board cannot bake a local server's page into a PNG. snap and
    compare --url leave it off, since they open the user's own dev server."""

    def __init__(self, connect_timeout=20, background=False, block_private=False):
        self.chrome = _Chrome()
        self.profile = self.chrome.profile
        self.proc = self.ws = self.cdp = None
        self.background = background
        self.block_private = block_private
        self.file_roots = []   # file:// requests are allowed only inside these folders
        try:
            self._start(time.monotonic() + connect_timeout)
        except BaseException:
            self.close()
            raise

    def _start(self, connect_by):
        try:
            self.proc = self.chrome.spawn(_cdp_launch_args(self.profile, self.background))
        except OSError as e:
            raise CdpConnectError(f'cannot start Chrome: {e}')
        # Chrome writes DevToolsActivePort as "<port>\n<browser path>\n"; a file read while it
        # is still being written can hold a partial port, so wait for both lines.
        port_file = os.path.join(self.profile, 'DevToolsActivePort')
        while True:
            try:
                with open(port_file) as f:
                    lines = f.read().split('\n')
                if len(lines) >= 2 and lines[1].strip():
                    port = int(lines[0].strip())
                    if 0 < port < 65536:
                        break
            except (OSError, ValueError):
                pass
            if self.proc.poll() is not None:
                raise CdpConnectError(f'Chrome exited with code {self.proc.returncode} before DevTools started')
            if time.monotonic() > connect_by:
                raise CdpConnectError('DevToolsActivePort did not appear')
            time.sleep(0.05)
        # The port can refuse connections or list no page for a moment after the file appears
        delay = 0.05
        while True:
            try:
                self.ws = _WebSocket('127.0.0.1', port, _cdp_page_ws(port, 5), 10)
                break
            except (OSError, ValueError, http.client.HTTPException) as e:
                if self.proc.poll() is not None:
                    raise CdpConnectError(f'Chrome exited with code {self.proc.returncode}: {e}')
                if time.monotonic() + delay > connect_by:
                    raise CdpConnectError(f'DevTools connection failed: {e}')
                time.sleep(delay)
                delay = min(delay * 2, 0.5)
        self.cdp = _Cdp(self.ws, time.monotonic() + 30)
        self.cdp.call('Page.enable')
        # Chrome lets a file:// page show any local file in an iframe or image, so every file://
        # request is paused here and failed unless it is inside file_roots (the idea folder).
        # With block_private, http(s) requests are paused too and failed for private hosts.
        self.cdp.handler = self._file_guard
        patterns = ['file://*'] + (['http://*', 'https://*'] if self.block_private else [])
        self.patterns = [{'urlPattern': p} for p in patterns]
        self.cdp.call('Fetch.enable', patterns=self.patterns)
        if self.block_private:
            # A cross-origin iframe runs as its own target, and this page's Fetch does not see
            # its requests (an allowed public page could frame localhost). Attach to every child
            # target paused at start, guard it the same way, then let it run.
            self.cdp.call('Target.setAutoAttach', autoAttach=True, waitForDebuggerOnStart=True,
                          flatten=True)

    def _file_guard(self, msg):
        method = msg.get('method')
        if method == 'Target.attachedToTarget':
            child = msg.get('params', {}).get('sessionId')
            if child:
                # Sent in order on the child's session, so Fetch is on before it runs
                self.cdp.send('Fetch.enable', _session=child, patterns=self.patterns)
                self.cdp.send('Target.setAutoAttach', _session=child, autoAttach=True,
                              waitForDebuggerOnStart=True, flatten=True)
                self.cdp.send('Runtime.runIfWaitingForDebugger', _session=child)
            return
        if method != 'Fetch.requestPaused':
            return
        sid = msg.get('sessionId')
        p = msg.get('params', {})
        rid = p.get('requestId')
        try:
            u = urlparse(p['request']['url'])
            if u.scheme in ('http', 'https'):
                ok = self.block_private and not _host_blocked(u.hostname)
            else:
                ok = (u.scheme == 'file' and u.netloc in ('', 'localhost') and
                      any(_within(unquote(u.path), r) for r in self.file_roots))
        except (KeyError, TypeError, ValueError):
            ok = False
        if ok:
            self.cdp.send('Fetch.continueRequest', _session=sid, requestId=rid)
        else:
            self.cdp.send('Fetch.failRequest', _session=sid, requestId=rid, errorReason='AccessDenied')

    def call(self, method, **params):
        return self.cdp.call(method, **params)

    def goto(self, url, w, h, deadline):
        """Lay the page out at exactly w x h CSS px and load url (waits for the load event)."""
        cdp = self.cdp
        cdp.deadline = deadline
        cdp.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                 deviceScaleFactor=1, mobile=w < 768)
        cdp.events.clear()
        nav = cdp.call('Page.navigate', url=url)
        if nav.get('errorText'):
            raise CdpError(f'cannot load {url}: {nav["errorText"]}')
        cdp.wait_event('Page.loadEventFired')
        if w < 768:
            # Mobile emulation lays out a page without <meta name="viewport"> at 980 px.
            # Such a board shows at its own width on the canvas, so reload it without mobile mode.
            r = cdp.call('Runtime.evaluate', expression='innerWidth', returnByValue=True)
            if r.get('result', {}).get('value') != w:
                cdp.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                         deviceScaleFactor=1, mobile=False)
                cdp.events.clear()
                cdp.call('Page.reload')
                cdp.wait_event('Page.loadEventFired')

    def capture(self, url, w, h, wait_ms, out, full_page=False, timeout=60, scale=1, file_roots=()):
        """Write a PNG of url at w x h into out. Raises CdpError or TimeoutError.
        file_roots: folders whose files the page may load over file:// (nothing else)."""
        self.file_roots = [os.path.realpath(r) for r in file_roots]
        deadline = time.monotonic() + timeout
        try:
            self.goto(url, w, h, deadline)
            pause = wait_ms / 1000
            if time.monotonic() + pause > deadline:
                raise TimeoutError
            time.sleep(pause)
            # Two animation frames: what the page has drawn is painted before the capture
            self.cdp.call('Runtime.evaluate', awaitPromise=True, expression=(
                'new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))'))
            shot = {'format': 'png'}
            full_h = h
            if full_page:
                r = self.cdp.call('Runtime.evaluate', returnByValue=True, expression=(
                    'Math.max(document.documentElement.scrollHeight, '
                    'document.body ? document.body.scrollHeight : 0)'))
                full_h = max(h, int(r.get('result', {}).get('value') or h))
                if full_h > FULL_PAGE_MAX_H:
                    print(f'Warning: the page is {full_h} px tall; --full-page captures the first '
                          f'{FULL_PAGE_MAX_H} px', file=sys.stderr)
                    full_h = FULL_PAGE_MAX_H
                shot['captureBeyondViewport'] = True
            if full_page or scale != 1:
                shot['clip'] = {'x': 0, 'y': 0, 'width': w, 'height': full_h, 'scale': scale}
            data = base64.b64decode(self.cdp.call('Page.captureScreenshot', **shot)['data'])
            tmp = out + '.part'
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, out)
        except TimeoutError:
            raise
        except (OSError, ValueError, KeyError) as e:
            raise CdpError(str(e) or e.__class__.__name__)

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except OSError:
                pass
            self.ws = None
        self.chrome.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _cdp_capture(url, w, h, wait_ms, out, full_page, timeout, file_roots=()):
    """Capture url into out over DevTools. Raises CdpConnectError, CdpError, or TimeoutError."""
    start = time.monotonic()
    try:
        # file_roots is given for board renders (local files): they may not reach private hosts
        session = _CdpSession(connect_timeout=min(20, timeout), block_private=bool(file_roots))
    except TimeoutError:
        raise CdpConnectError('DevTools connection timed out')
    with session:
        session.capture(url, w, h, wait_ms, out, full_page, timeout - (time.monotonic() - start),
                        file_roots=file_roots)


def _capture(url, w, h, wait_ms, out, full_page=False, file_roots=()):
    """Screenshot url at exactly w x h CSS px (deviceScaleFactor 1) into out, after the load event
    plus wait_ms of real time. True when a non-empty PNG was written; errors are printed.
    file_roots: the only folders the page may read over file:// (see _CdpSession._file_guard)."""
    if os.path.exists(out):
        os.remove(out)   # a stale file must not count as success
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    limit = wait_ms / 1000 + 60
    try:
        _cdp_capture(url, w, h, wait_ms, out, full_page, limit, file_roots)
    except CdpConnectError as e:
        if urlparse(url).scheme == 'file':
            # --screenshot cannot stop a board from showing other local files
            print(f'Error: could not drive Chrome over DevTools ({e}); a local board is not rendered '
                  'without it, because only DevTools can block access to files outside the idea folder',
                  file=sys.stderr)
            return False
        print(f'Warning: could not drive Chrome over DevTools ({e}); falling back to --screenshot, '
              'so sizes under 500 px wide may be inaccurate' +
              (' and --full-page is ignored' if full_page else ''), file=sys.stderr)
        try:
            # A zero virtual-time budget never finishes, so give it at least 500 ms
            result = _run_chrome(w, h, max(wait_ms, 500), out, url, timeout=limit)
        except subprocess.TimeoutExpired:
            # Virtual time stops while a request stays open (server-sent events, long polling)
            print(f'Error: Chrome did not finish within {limit:.0f} s; the page may keep a request open '
                  '(server-sent events or long polling)', file=sys.stderr)
            return False
        return result == 0 and os.path.isfile(out) and os.path.getsize(out) > 0
    except TimeoutError:
        print(f'Error: Chrome did not finish within {limit:.0f} s (the page never fired its load '
              'event, or --wait is too long)', file=sys.stderr)
        return False
    except CdpError as e:
        print(f'Error: capture failed: {e}', file=sys.stderr)
        return False
    return os.path.isfile(out) and os.path.getsize(out) > 0

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

DASH_SSE_KEY = '*'   # the dashboard listens to every idea's events on one stream (/api/events)

def _broadcast(key, data):
    if key != DASH_SSE_KEY:
        _broadcast(DASH_SSE_KEY, dict(data, key=key))
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
      or a function returning such a list (re-read every second: projects added later are watched)
    """
    mtimes: dict = {}
    while True:
        try:
            dirs = design_dirs() if callable(design_dirs) else design_dirs
        except Exception:
            dirs = []
        for design_dir, prefix in dirs:
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

# ── Board thumbnails (viewer level of detail) ──────────────────────────────
# At low zoom the viewer shows PNG thumbnails instead of live iframes. They are rendered lazily
# with the DevTools capture, a few at a time in background threads that reuse one Chrome each,
# and cached in <idea>/render/.thumbs/ under a name keyed by the board file's mtime, the
# tokens.css mtime, the board size, and the scale, so an edit makes a new thumbnail.
# The viewer asks for the scale that stays sharp up to the zoom where boards go live (40%) on its
# screen: 0.8 on a 2x display, 0.4 on a 1x one (`?s=`). 0.6 looked blurry at 30 to 40% on 2x.

THUMB_SCALES = {'0.4': 0.4, '0.6': 0.6, '0.8': 0.8, '1': 1.0}
THUMB_SCALE = 0.8   # without ?s=
THUMB_WORKERS = 1   # a second background Chrome rendered faster but made first-open zoom stutter
THUMB_IDLE_SECS = 15
THUMB_VERSION = 3   # in the cache key: version 1 rendered without the file:// guard, 2 had no scale


def _thumb_target(idea_dir, fname, scale=THUMB_SCALE):
    """-> (board path, w, h, cached png path) for a registered board, or None."""
    if not fname.endswith('.html'):
        return None
    try:
        b = load_canvas(idea_dir).get('boards', {}).get(fname)
    except Exception:
        return None
    src = _safe_path(idea_dir, 'boards', fname)
    if not isinstance(b, dict) or not src or not os.path.isfile(src):
        return None
    try:
        w, h = int(b.get('w', DEFAULT_W)), int(b.get('h', DEFAULT_H))
        if not (0 < w <= 8000 and 0 < h <= 8000):
            return None
        key = f'{THUMB_VERSION:x}-{round(scale * 10):x}-{os.stat(src).st_mtime_ns:x}'
        tok = os.path.join(idea_dir, 'shared', 'tokens.css')
        if os.path.isfile(tok):
            key += f'-{os.stat(tok).st_mtime_ns:x}'
    except (OSError, TypeError, ValueError):
        return None
    out = os.path.join(idea_dir, 'render', '.thumbs', f'{fname[:-5]}-{w}x{h}-{key}.png')
    return src, w, h, out


class _ThumbQueue:
    def __init__(self, workers=THUMB_WORKERS):
        self.cv = threading.Condition()
        self.jobs, self.pending, self.failed = [], set(), set()
        self.sessions, self.workers, self.started = [], workers, 0
        self.starting = 0   # workers inside _CdpSession(): Chrome may be running but not listed yet
        self.closed = False

    def request(self, url, w, h, out, sse_key, fname, file_roots=(), scale=THUMB_SCALE):
        """Queue a render unless it is running or failed before. Most recent request first: the
        viewer asks for boards near its viewport once the view rests, so a board asked again moves
        to the front of the queue."""
        with self.cv:
            if self.closed:
                return False
            if out in self.failed:
                return False
            if out in self.pending:
                for i, job in enumerate(self.jobs):
                    if job[3] == out:
                        self.jobs.append(self.jobs.pop(i))
                        break
                return True
            self.pending.add(out)
            self.jobs.append((url, w, h, out, sse_key, fname, tuple(file_roots), scale))
            if self.started < self.workers:
                self.started += 1
                threading.Thread(target=self._work, daemon=True).start()
            self.cv.notify()
        return True

    def _work(self):
        session = None
        try:
            while True:
                with self.cv:
                    if not self.jobs and not self.closed:
                        self.cv.wait(THUMB_IDLE_SECS)
                    if not self.jobs or self.closed:
                        # idle: let Chrome go; a new request starts a new worker
                        self.started -= 1
                        return
                    job = self.jobs.pop()
                url, w, h, out, sse_key, fname, roots, scale = job
                ok = False
                try:
                    if session is None:
                        with self.cv:
                            self.starting += 1
                        try:
                            session = _CdpSession(background=True, block_private=True)
                        finally:
                            with self.cv:
                                self.starting -= 1
                                if session:
                                    self.sessions.append(session)
                                self.cv.notify_all()
                        if self.closed:   # shut down while Chrome was starting
                            raise CdpError('thumbnail queue closed')
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    session.capture(url, w, h, 250, out, timeout=30, scale=scale, file_roots=roots)
                    ok = True
                except CdpConnectError as e:
                    if not self.closed:
                        print(f'[mockup-canvas] thumbnail: Chrome unavailable: {e}', file=sys.stderr, flush=True)
                except (CdpError, TimeoutError, OSError) as e:
                    if not self.closed:
                        print(f'[mockup-canvas] thumbnail failed: {fname}: {e!r}', file=sys.stderr, flush=True)
                    if session:   # a stuck page: start clean for the next job
                        self._drop(session)
                        session = None
                if ok:
                    # older thumbnails of this board at this scale or from an older version:
                    # <board id>-<w>x<h>-<version>-<scale>-<hex key>.png (a 1x and a 2x viewer
                    # keep their own)
                    stale = re.compile(re.escape(fname[:-5]) + r'-\d+x\d+-(?:%x-%x-|(?!%x-))[0-9a-f-]+\.png$'
                                       % (THUMB_VERSION, round(scale * 10), THUMB_VERSION))
                    folder = os.path.dirname(out)
                    for old in os.listdir(folder):
                        if stale.match(old) and old != os.path.basename(out):
                            try:
                                os.remove(os.path.join(folder, old))
                            except OSError:
                                pass
                with self.cv:
                    self.pending.discard(out)
                    if not ok:
                        self.failed.add(out)
                if ok:
                    _broadcast(sse_key, {'type': 'thumb', 'file': fname})
        finally:
            if session:
                self._drop(session)

    def forget_failure(self, out):
        with self.cv:
            self.failed.discard(out)

    def _drop(self, session):
        with self.cv:
            if session in self.sessions:
                self.sessions.remove(session)
        session.close()

    def close_all(self, wait=25):
        """Stop for good: drop queued jobs, wake idle workers, and kill every Chrome, including
        ones still starting (waits up to `wait` s for them; at exit _kill_all_chrome has already
        killed them, so they fail at once)."""
        with self.cv:
            self.closed = True
            self.jobs.clear()
            self.pending.clear()
            self.cv.notify_all()
            self.cv.wait_for(lambda: not self.starting, wait)
            sessions, self.sessions = list(self.sessions), []
        for s in sessions:
            s.close()


_THUMBS = _ThumbQueue()


@__import__('atexit').register
def _close_chrome_at_exit():
    _THUMBS.close_all(wait=0)   # no new jobs, and workers stay quiet about the kills below
    _kill_all_chrome()
    _THUMBS.close_all()         # wait for workers still starting a Chrome


def _stop_on_sigterm():
    """`kill <pid>` (and a closed terminal) exits through atexit too, so Chrome processes are
    not left behind."""
    def stop(*_):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, stop)
        hup = getattr(signal, 'SIGHUP', None)
        if hup is not None and signal.getsignal(hup) is not signal.SIG_IGN:   # keep nohup working
            signal.signal(hup, stop)
    except ValueError:   # not the main thread (tests run servers in threads)
        pass


# ── Dashboard index ────────────────────────────────────────────────────────
# The registry page (dashboard.html) renders from one JSON built from canvas.json and os.stat
# only: no Chrome and no board HTML is read. canvas.json is parsed again only when its mtime or
# size changes; board mtimes are stat'ed on every request (a few ms for hundreds of boards).

DASHBOARD_PATH = os.path.join(HERE, 'dashboard.html')
DASHBOARD_MANAGE_PATH = os.path.join(HERE, 'dashboard-manage.js')
_IDEA_CACHE = {}   # canvas.json path -> ((mtime_ns, size), [board summaries])


def _display_path(path):
    path = os.path.realpath(path) if os.path.exists(path) else os.path.normpath(path)
    if path == HOME:
        return '~'
    return '~/' + path[len(HOME) + 1:] if path.startswith(HOME + os.sep) else path


def _idea_boards(cj):
    """Board summaries of one canvas.json, cached by its mtime and size."""
    st = os.stat(cj)
    key = (st.st_mtime_ns, st.st_size)
    hit = _IDEA_CACHE.get(cj)
    if hit and hit[0] == key:
        return hit[1], st.st_mtime
    try:
        with open(cj, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    boards = data.get('boards') if isinstance(data, dict) else None
    out = []
    for fname, b in (boards.items() if isinstance(boards, dict) else ()):
        if not isinstance(b, dict) or not isinstance(fname, str):
            continue
        impl = b.get('impl')
        comments = b.get('comments')
        try:
            w, h = int(b.get('w', DEFAULT_W)), int(b.get('h', DEFAULT_H))
        except (TypeError, ValueError):
            w, h = DEFAULT_W, DEFAULT_H
        out.append({
            'f': fname,
            't': str(b.get('title') or (fname[:-5] if fname.endswith('.html') else fname))[:200],
            's': b.get('status') if b.get('status') in ('approved', 'rejected') else 'draft',
            'c': len(comments) if isinstance(comments, list) else 0,
            'b': 1 if isinstance(impl, dict) and (impl.get('route') or impl.get('files')) else 0,
            'n': str(b.get('note') or '')[:200],
            'w': w, 'h': h,
        })
    _IDEA_CACHE[cj] = (key, out)
    return out, st.st_mtime


def _idea_summary(project, idea, idea_dir, url):
    boards, cj_mtime = _idea_boards(os.path.join(idea_dir, 'canvas.json'))
    last = cj_mtime
    rows = []
    for b in boards:
        m = None
        if b['f'] == os.path.basename(b['f']):   # a key with a path in it is not a board file
            try:
                m = os.stat(os.path.join(idea_dir, 'boards', b['f'])).st_mtime
            except OSError:
                pass
        if m is not None and m > last:
            last = m
        rows.append(dict(b, m=round(m or cj_mtime, 3)))
    return {'project': project, 'name': idea, 'url': url, 'boards': rows, 'mtime': round(last, 3)}


def _list_ideas(design_dir):
    try:
        names = sorted(os.listdir(design_dir))
    except OSError:
        return []
    return [d for d in names if os.path.isfile(os.path.join(design_dir, d, 'canvas.json'))]


def build_index(roots, single=False, share=False):
    """roots: [{'name', 'path'}]. single: one root served at /<idea>/ (serve <design dir>)."""
    projects, ideas = [], []
    for r in roots:
        name, path = r['name'], r['path']
        missing = not os.path.isdir(path)
        if missing and share:
            continue   # a share never names folders that are not there
        p = {'name': name, 'missing': missing, 'ideas': 0, 'boards': 0}
        if not share:
            p['path'] = _display_path(path)
        if not missing:
            for idea in _list_ideas(path):
                if single:
                    url = '/' + _urlquote(idea, safe='') + '/'
                else:
                    url = '/' + _urlquote(name, safe='') + '/' + _urlquote(idea, safe='') + '/'
                try:
                    s = _idea_summary(name, idea, os.path.join(path, idea), url)
                except OSError:
                    continue
                ideas.append(s)
                p['ideas'] += 1
                p['boards'] += len(s['boards'])
        projects.append(p)
    return {'projects': projects, 'ideas': ideas, 'now': round(time.time(), 3)}


def _reveal_path(path):
    """Show a folder in the file manager (Finder on macOS)."""
    if sys.platform == 'darwin':
        cmd = ['open', '-R', path]
    elif os.name == 'nt':
        cmd = ['explorer', '/select,' + path]
    else:
        cmd = ['xdg-open', os.path.dirname(path)]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _design_folder_info(real):
    """-> (ideas, boards) of a design folder."""
    ideas = _list_ideas(real)
    boards = 0
    for idea in ideas:
        try:
            boards += len(_idea_boards(os.path.join(real, idea, 'canvas.json'))[0])
        except OSError:
            pass
    return len(ideas), boards


# ── HTTP handler ───────────────────────────────────────────────────────────

_SANDBOX_CSP = 'sandbox allow-scripts allow-forms allow-popups'
_ACTIVE_TYPES = ('text/html', 'image/svg+xml', 'application/xhtml+xml', 'text/xml', 'application/xml')
_FONT_EXTS = ('.woff', '.woff2', '.ttf', '.otf', '.eot')

class _NullWriter:
    """Drops a HEAD response's body."""
    def write(self, data):
        return len(data)

    def flush(self):
        pass


class CanvasHandler(BaseHTTPRequestHandler):
    design_dir: str = ''
    share_token: str = ''
    share_edit: bool = True
    read_only: bool = False
    share_host: str = ''      # LAN IP accepted in the Host header in share mode
    share_until: float = 0.0  # share mode: when the server stops (time.time()), for the dashboard banner
    server_version = 'mockup-canvas'
    sys_version = ''
    timeout = 15              # socket timeout per connection (SSE clears it)
    _head = False             # answering HEAD: headers as for GET, no body

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

    def _serve_thumb(self, idea_dir, name, sse_key):
        """thumbs/<board id>.png: the cached thumbnail (ETag), or 202 while it is being rendered.
        ?cached=1 answers 204 instead of queueing a render (the dashboard palette's small rows);
        ?retry=1 renders again a board whose render failed before (the dashboard's Retry)."""
        qs = parse_qs(urlparse(self.path).query)
        s = qs.get('s', [''])[0]
        scale = THUMB_SCALES.get(s, THUMB_SCALE)
        target = _thumb_target(idea_dir, name[:-4] + '.html', scale) if name.endswith('.png') else None
        if not target:
            self._404(); return
        src, w, h, out = target
        etag = '"' + os.path.basename(out) + '"'
        if os.path.isfile(out):
            if self.headers.get('If-None-Match') == etag:
                self.send_response(304)
                self.send_header('ETag', etag)
                self._add_root_header()
                self.end_headers()
                return
            self._serve_file(out, 'image/png', {'X-Content-Type-Options': 'nosniff', 'ETag': etag},
                             cache='no-cache')
            return
        if qs.get('cached', [''])[0] == '1':   # 204, not 404: nothing failed, there is just no PNG yet
            self.send_response(204)
            self._add_root_header()
            self.end_headers()
            return
        if qs.get('retry', [''])[0] == '1':
            _THUMBS.forget_failure(out)
        # Rendered from file:// with every file:// request outside the idea folder failed over
        # DevTools (_CdpSession._file_guard). Loading the board from this server under its CSP
        # sandbox instead gave it an opaque origin, whose HTTP cache is partitioned: every board
        # downloaded its web fonts again, and a 71-board idea took minutes instead of 30 s.
        board = name[:-4] + '.html'
        if not _THUMBS.request(pathlib.Path(src).as_uri(), w, h, out, sse_key, board, file_roots=[idea_dir],
                               scale=scale):
            self._404(); return
        self._json({'pending': True}, 202)

    def do_HEAD(self):
        """Same status and headers as GET (auth and Host checks included), without the body."""
        wfile, self._head = self.wfile, True
        try:
            self.do_GET()
        finally:
            self.wfile, self._head = wfile, False

    def end_headers(self):
        super().end_headers()
        if self._head:
            self.wfile = _NullWriter()   # what follows is the body

    def do_GET(self):
        parts = self._gate_get()
        if parts is None:
            return

        if not parts:
            self._serve_dashboard()
            return

        if parts == ['api', 'index']:
            self._json(self._index_data(), cache='no-store')
            return
        if parts == ['api', 'events']:
            self._serve_sse(DASH_SSE_KEY)
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

        if parts[1] == 'thumbs' and len(parts) == 3:
            self._serve_thumb(idea_dir, parts[2], idea)
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

        if parts == ['api', 'reveal']:
            self._reveal()
            return

        if len(parts) == 3 and parts[1] == 'api' and parts[2] == 'layout':
            idea_dir = self._safe(parts[0])
            if not idea_dir:
                self._404(); return
            self._save_layout(idea_dir)
            return

        self._404()

    # ── dashboard (the index page) ──
    def _index_roots(self):
        """-> (roots, single). Single-root mode: the design folder as one project named after the
        folder that holds it (like `roots add`)."""
        real = os.path.realpath(self.design_dir)
        return [{'name': os.path.basename(os.path.dirname(real)) or os.path.basename(real),
                 'path': self.design_dir}], True

    def _index_data(self):
        roots, single = self._index_roots()
        share = bool(self.share_token)
        data = build_index(roots, single=single, share=share)
        data.update(mode='single' if single else 'registry', share=share,
                    readOnly=bool(self.read_only or (share and not self.share_edit)),
                    closesAt=int(self.share_until) if share and self.share_until else None)
        return data

    def _serve_dashboard(self):
        """dashboard.html with the index inlined (first paint needs no second request). The
        management script (add, remove, reveal) is left out of share and read-only pages."""
        try:
            with open(DASHBOARD_PATH, encoding='utf-8') as f:
                html = f.read()
            manage = ''
            if not self.share_token and not self.read_only:
                with open(DASHBOARD_MANAGE_PATH, encoding='utf-8') as f:
                    manage = f.read()
        except OSError:
            self._404(); return
        data = self._index_data()
        data.pop('now', None)   # the page is the same for a GET and a HEAD (and its script hashes too)
        html = html.replace('<!--BOOT-->', f'<script>window.MC_BOOT={_embed_json(data)};</script>', 1)
        html = html.replace('<!--MANAGE-->', f'<script>\n{manage}</script>' if manage else '', 1)
        # Inline scripts run by their hash: an injected script would not match
        hashes = ' '.join("'sha256-%s'" % base64.b64encode(hashlib.sha256(m.encode()).digest()).decode()
                          for m in re.findall(r'<script>(.*?)</script>', html, re.S))
        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy',
                         f"default-src 'none'; script-src {hashes}; "
                         "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                         "font-src https://fonts.gstatic.com; img-src 'self' blob: data:; connect-src 'self'; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self._add_root_header()
        self.end_headers()
        self.wfile.write(body)

    def _reveal_target(self, body):
        """The folder to reveal: the idea folder, or the design folder without an idea."""
        return self._reveal_in(self.design_dir, body.get('idea'))

    @staticmethod
    def _reveal_in(design_dir, idea):
        if not design_dir or not os.path.isdir(design_dir):
            return None
        if idea is None or idea == '':
            return os.path.realpath(design_dir)
        idea = str(idea)
        if idea != os.path.basename(idea) or idea in ('.', '..'):
            return None
        p = _safe_path(design_dir, idea)
        return p if p and os.path.isdir(p) else None

    def _reveal(self):
        """POST /api/reveal {project?, idea?}: the server picks the folder from its own registry,
        never from a path the page sends. Local mode only."""
        if self.share_token or self.read_only:
            self._json({'ok': False, 'error': 'Not allowed in share mode'}, 403); return
        body = self._read_json_body()
        if body is None:
            return
        target = self._reveal_target(body)
        if not target:
            self._json({'ok': False, 'error': 'Folder not found'}, 404); return
        try:
            _reveal_path(target)
        except OSError as e:
            self._log_error('reveal failed', e)
            self._json({'ok': False, 'error': 'Could not open the file manager'}, 500); return
        self._json({'ok': True})

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

    def _serve_file(self, path, content_type, extra_headers=None, cache='no-store'):
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
        self.send_header('Cache-Control', cache)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self._add_root_header()
        self.end_headers()
        self.wfile.write(data)

    def _serve_sse(self, key):
        if self._head:   # a HEAD must not open the stream
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self._add_root_header()
            self.end_headers()
            return
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

    def _json(self, data, status=200, cache=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if cache:
            self.send_header('Cache-Control', cache)
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

    def _index_roots(self):
        return self._roots(), False

    def _reveal_target(self, body):
        project = str(body.get('project') or '')
        return self._reveal_in(self._roots_map().get(project), body.get('idea'))

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
            self._serve_dashboard()
            return

        if parts == ['api', 'index']:
            self._json(self._index_data(), cache='no-store')
            return
        if parts == ['api', 'events']:
            self._serve_sse(DASH_SSE_KEY)
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

        if rest[0] == 'thumbs' and len(rest) == 2:
            self._serve_thumb(idea_dir, rest[1], project + '/' + idea)
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
        if parts == ['api', 'reveal']:
            self._reveal()
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

    @staticmethod
    def _suggest_design(path_str):
        """A path that is not a design folder: is there one inside it (<path>/design)?"""
        real = os.path.realpath(os.path.expanduser(path_str.strip()))
        err, inner = _validate_design_path(os.path.join(real, 'design'))
        if err:
            return None
        ideas, boards = _design_folder_info(inner)
        return {'path': _display_path(inner), 'ideas': ideas, 'boards': boards}

    def _handle_roots_api(self, action):
        """POST /api/roots/{check|add|remove|rename|scan}"""
        # Never allow registry changes in share mode
        if self.share_token:
            self._json({'ok': False, 'error': 'Not allowed in share mode'}, 403)
            return

        body = self._read_json_body()
        if body is None:
            return

        if action in ('add', 'check'):
            # check: the same validation without registering (the dialog's live result)
            path_str = str(body.get('path') or '')
            name = str(body.get('name') or '').strip()
            err, real = _validate_design_path(path_str)
            if err:
                out = {'ok': False, 'error': err}
                if 'canvas.json' in err:
                    sug = self._suggest_design(path_str)
                    if sug:
                        out['suggest'] = sug
                self._json(out, 400 if action == 'add' else 200)
                return
            if not name:
                parent = os.path.dirname(real)
                name = os.path.basename(parent) or os.path.basename(real)
            roots = load_roots_safe()
            same_name = next((r for r in roots if r['name'] == name), None)
            # Locate folder: a project whose folder is gone takes the new path under its old name
            if same_name and os.path.isdir(same_name['path']):
                self._json({'ok': False, 'error': f'Name already in use: {name}', 'name': name},
                           409 if action == 'add' else 200)
                return
            dup = next((r for r in roots if os.path.realpath(r['path']) == real), None)
            if dup:
                self._json({'ok': False, 'error': f'Already registered: {dup["name"]}'},
                           409 if action == 'add' else 200)
                return
            if action == 'check':
                ideas, boards = _design_folder_info(real)
                self._json({'ok': True, 'name': name, 'path': _display_path(real), 'ideas': ideas,
                            'boards': boards, 'replaces': bool(same_name)})
                return
            if same_name:
                same_name['path'] = real
            else:
                roots.append({'name': name, 'path': real})
            save_roots_safe(roots)
            self._json({'ok': True, 'name': name, 'path': real})
            return

        if action == 'rename':
            name = str(body.get('name') or '').strip()
            new_name = str(body.get('new_name') or '').strip()
            if not name or not new_name:
                self._json({'ok': False, 'error': 'The name and new_name fields are required'}, 400)
                return
            if '/' in new_name or new_name in ('.', '..', 'api') or len(new_name) > 100:
                self._json({'ok': False, 'error': 'Use a short name without /'}, 400)
                return
            roots = load_roots_safe()
            if any(r['name'] == new_name for r in roots):
                self._json({'ok': False, 'error': f'Name already in use: {new_name}'}, 409)
                return
            target = next((r for r in roots if r['name'] == name), None)
            if not target:
                self._json({'ok': False, 'error': f'Not found: {name}'}, 404)
                return
            target['name'] = new_name
            save_roots_safe(roots)
            self._json({'ok': True, 'name': new_name})
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
    _clean_stale_profiles()   # left by a server that was killed with -9 or crashed

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
    CanvasHandler.share_until = time.time() + minutes * 60 if share else 0.0

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

    _stop_on_sigterm()
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
    if not roots and share:
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
    RegistryHandler.share_until = time.time() + minutes * 60 if share else 0.0
    # A share serves the projects registered right now; later registry edits do not widen it
    RegistryHandler.frozen_roots = [dict(r) for r in roots] if share else None

    def watch_list():
        current = RegistryHandler.frozen_roots if RegistryHandler.frozen_roots is not None else load_roots_safe()
        return [(r['path'], r['name'] + '/') for r in current if os.path.isdir(r['path'])]
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
        if not roots:
            print('  No projects registered yet: add one on the page or with canvas roots add <design dir>',
                  flush=True)
        for r in roots:
            exists = 'ok' if os.path.isdir(r['path']) else 'missing'
            print(f'  {r["name"]}: {r["path"]} [{exists}]', flush=True)

    _stop_on_sigterm()
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
            f.write('render/\ncompare/\n')

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
    elif size_override and (boards[fname].get('w'), boards[fname].get('h')) != size_override:
        # Re-running add with --size resizes a registered board (e.g. a long page that was cut off)
        boards[fname]['w'], boards[fname]['h'] = size_override
        save_canvas_atomic(cj, canvas)
        print(f'Resized: {fname} -> {size_override[0]}x{size_override[1]}')
    else:
        print(f'Already registered: {fname}')

# ── render ─────────────────────────────────────────────────────────────────

def _parse_wait(vals, default):
    """--wait value in ms, or None after printing an error."""
    try:
        wait = int(vals['--wait'][-1]) if vals['--wait'] else default
        if not 0 <= wait <= 120000:
            raise ValueError
    except ValueError:
        print('Error: --wait must be a whole number of milliseconds from 0 to 120000', file=sys.stderr)
        return None
    return wait


def _board_size(b):
    """(w, h) of a canvas.json board entry, each clamped to 1..MAX_BOARD_SIDE."""
    def side(key, default):
        try:
            v = int(b.get(key, default))
        except (TypeError, ValueError, AttributeError):
            v = default
        return min(max(v, 1), MAX_BOARD_SIDE)
    return side('w', DEFAULT_W), side('h', DEFAULT_H)


def cmd_render(args):
    usage = ('Usage: canvas.py render <idea dir> [file...] [--full-page] [--wait MS]\n'
             '  Render boards to <idea>/render/<board>.png at their registered size.\n'
             '  --full-page  capture the whole scroll height (width stays the board width)\n'
             '  --wait MS    wait this long after the page load event (default 1000)')
    if not args or _is_help(args):
        print(usage); return
    parsed = _split_args(args, ('--wait',), ('--full-page',))
    if parsed is None:
        return 1
    pos, vals, flags = parsed
    if not pos:
        print(usage, file=sys.stderr); return 1
    wait = _parse_wait(vals, 1000)
    if wait is None:
        return 1
    idea_dir = os.path.abspath(pos[0])
    files = [os.path.basename(f) for f in pos[1:]]

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
        w, h = _board_size(b)
        out = os.path.join(render_dir, fname.replace('.html', '.png'))
        if not _capture(pathlib.Path(src).as_uri(), w, h, wait, out, flags['--full-page'],
                        file_roots=[idea_dir]):
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
        if not _capture(pathlib.Path(tmp_index).as_uri() + '?overview=1', out_w, out_h, 2000, out_png,
                        file_roots=[idea_dir]):
            print('Error: overview render failed', file=sys.stderr)
            sys.exit(1)

        print(f'Overview: {out_png}  ({out_w}x{out_h}px)')
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ── check ──────────────────────────────────────────────────────────────────

def _visible_text(html_src):
    """Lower-cased text a reader sees in a board (no scripts, styles, or tags; spaces collapsed)."""
    t = re.sub(r'(?is)<(script|style|template)\b.*?</\1\s*>', ' ', html_src)
    t = re.sub(r'(?s)<!--.*?-->', ' ', t)
    t = _html.unescape(re.sub(r'<[^>]*>', ' ', t))
    return ' '.join(t.split()).casefold()


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

    infos = []
    texts = {}
    for lnk in canvas.get('links', []):
        for end in ('from', 'to'):
            if lnk.get(end) not in boards:
                errors.append(f'link {end} is not a registered board: {lnk.get("from")} -> {lnk.get("to")}')
        # A label normally names the button that leads on; say so when the board has no such text
        label, src = str(lnk.get('label') or '').strip(), lnk.get('from')
        if not label or src not in boards:
            continue
        if src not in texts:
            try:
                with open(os.path.join(boards_dir, src), encoding='utf-8', errors='replace') as f:
                    texts[src] = _visible_text(f.read())
            except OSError:
                texts[src] = None
        if texts[src] is not None and ' '.join(label.split()).casefold() not in texts[src]:
            infos.append(f'link label "{label}" not found in the text of {src}')

    # impl files are paths in the project that holds the design folder (<project>/<design>/<idea>)
    project_root = os.path.dirname(os.path.dirname(idea_dir))
    for fname, b in boards.items():
        impl = b.get('impl')
        if not isinstance(impl, dict):
            continue
        for f in impl.get('files') or []:
            if not _in_project(project_root, f):
                errors.append(f'impl file is outside the project: {fname} -> {f}')
            elif not os.path.exists(os.path.join(project_root, f)):
                errors.append(f'impl file not found: {fname} -> {f}')

    approved = sum(1 for b in boards.values() if b.get('status') == 'approved')
    print(f'Approved boards: {approved}/{len(boards)}')
    commented = [(f, len(b['comments'])) for f, b in boards.items()
                 if isinstance(b.get('comments'), list) and b['comments']]
    if commented:
        print(f'Comments: {sum(n for _, n in commented)} on {len(commented)} board(s)')
        for f, n in commented:
            print(f'  {f}: {n}')

    for i in infos:
        print('Info:', i)
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

# ── PNG (stdlib only) ──────────────────────────────────────────────────────
# Enough PNG for compare: decode 8-bit RGB/RGBA non-interlaced images (what Chrome writes)
# and encode 8-bit RGB. Rows are kept as bytes objects so whole-row operations stay fast.

_PNG_SIG = b'\x89PNG\r\n\x1a\n'


class PngError(ValueError):
    pass


def _png_add(a, b):
    """Byte-wise (a + b) mod 256 of two equal-length byte strings, computed on big-int lanes."""
    n = len(a)
    if not n:
        return b''
    x, y = int.from_bytes(a, 'big'), int.from_bytes(b, 'big')
    lo = int.from_bytes(b'\x7f' * n, 'big')
    hi = int.from_bytes(b'\x80' * n, 'big')
    return (((x & lo) + (y & lo)) ^ ((x ^ y) & hi)).to_bytes(n, 'big')


PNG_MAX_W, PNG_MAX_H, PNG_MAX_PIXELS = 8000, 20000, 160_000_000


def png_read(path):
    """Decode a PNG -> (w, h, channels, rows); each row is w*channels bytes."""
    import zlib
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != _PNG_SIG:
        raise PngError(f'not a PNG file: {path}')
    pos, ihdr, idat = 8, None, []
    while True:
        if pos + 12 > len(data):
            raise PngError(f'truncated PNG (no IEND chunk): {path}')
        length = int.from_bytes(data[pos:pos + 4], 'big')
        end = pos + 8 + length
        if end + 4 > len(data):
            raise PngError(f'PNG chunk runs past the end of the file: {path}')
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:end]
        if zlib.crc32(ctype + body) != int.from_bytes(data[end:end + 4], 'big'):
            raise PngError(f'PNG CRC mismatch in chunk {ctype.decode("latin-1")!r}: {path}')
        pos = end + 4
        if ctype == b'IHDR':
            ihdr = body
        elif ctype == b'IDAT':
            idat.append(body)
        elif ctype == b'IEND':
            break
    if not ihdr or len(ihdr) < 13:
        raise PngError(f'missing IHDR chunk: {path}')
    w = int.from_bytes(ihdr[0:4], 'big')
    h = int.from_bytes(ihdr[4:8], 'big')
    # Check the size before inflating anything: a tiny file can claim a huge image
    if w <= 0 or h <= 0 or w > PNG_MAX_W or h > PNG_MAX_H or w * h > PNG_MAX_PIXELS:
        raise PngError(f'PNG size {w}x{h} is outside the supported range (1 to {PNG_MAX_W} wide, '
                       f'1 to {PNG_MAX_H} tall, at most {PNG_MAX_PIXELS} pixels): {path}')
    depth, color, interlace = ihdr[8], ihdr[9], ihdr[12]
    if depth != 8 or color not in (2, 6):
        raise PngError(f'unsupported PNG format (bit depth {depth}, color type {color}); '
                       f'only 8-bit RGB or RGBA is supported: {path}')
    if interlace:
        raise PngError(f'interlaced PNG is not supported: {path}')
    ch = 3 if color == 2 else 4
    stride = w * ch
    need = (stride + 1) * h
    try:
        raw = zlib.decompressobj().decompress(b''.join(idat), need)   # never more than the image needs
    except zlib.error as e:
        raise PngError(f'corrupt PNG data: {path}: {e}')
    if len(raw) < need:
        raise PngError(f'truncated PNG data: {path}')
    rows = []
    prev = bytes(stride)
    for y in range(h):
        off = y * (stride + 1)
        ft = raw[off]
        line = raw[off + 1:off + 1 + stride]
        if ft == 0:      # None
            cur = line
        elif ft == 2:    # Up
            cur = _png_add(line, prev)
        elif ft == 1:    # Sub
            cur = bytearray(line)
            for i in range(ch, stride):
                cur[i] = (cur[i] + cur[i - ch]) & 255
            cur = bytes(cur)
        elif ft == 3:    # Average
            cur = bytearray(line)
            for i in range(stride):
                left = cur[i - ch] if i >= ch else 0
                cur[i] = (cur[i] + ((left + prev[i]) >> 1)) & 255
            cur = bytes(cur)
        elif ft == 4:    # Paeth
            cur = bytearray(line)
            for i in range(stride):
                b = prev[i]
                if i >= ch:
                    a, c = cur[i - ch], prev[i - ch]
                else:
                    a = c = 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                cur[i] = (cur[i] + pr) & 255
            cur = bytes(cur)
        else:
            raise PngError(f'bad PNG filter type {ft} in row {y}: {path}')
        rows.append(cur)
        prev = cur
    return w, h, ch, rows


def png_write(path, w, h, rows):
    """Encode 8-bit RGB rows (w*3 bytes each) as a PNG (filter None, zlib)."""
    import zlib

    def chunk(kind, body):
        return (len(body).to_bytes(4, 'big') + kind + body +
                (zlib.crc32(kind + body) & 0xffffffff).to_bytes(4, 'big'))
    ihdr = w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + bytes([8, 2, 0, 0, 0])
    raw = b''.join(b'\x00' + r for r in rows)
    data = (_PNG_SIG + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 6)) +
            chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(data)


def _rgb_rows(w, ch, rows):
    """Drop the alpha channel (screens are compared as opaque)."""
    if ch == 3:
        return rows
    out = []
    for r in rows:
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = r[0::4], r[1::4], r[2::4]
        out.append(bytes(rgb))
    return out


def _resize_nearest(rows, sw, sh, dw, dh):
    """Nearest-neighbour resize of RGB rows from sw x sh to dw x dh."""
    xs = [min(sw - 1, x * sw // dw) for x in range(dw)]
    out = []
    for y in range(dh):
        src = rows[min(sh - 1, y * sh // dh)]
        line = bytearray(dw * 3)
        for x, sx in enumerate(xs):
            line[x * 3:x * 3 + 3] = src[sx * 3:sx * 3 + 3]
        out.append(bytes(line))
    return out


# Diff image: board pixels dimmed toward gray, mismatches in magenta
_DIM = bytes(96 + v * 3 // 8 for v in range(256))
_MAGENTA = b'\xff\x00\xff'
_IGNORED = bytes(v // 4 for v in range(256))


def _diff_rows(rows_a, rows_b, w, threshold):
    """-> (diff rows, mismatched pixel count). A pixel differs if any channel differs by > threshold."""
    out, bad = [], 0
    for ra, rb in zip(rows_a, rows_b):
        dim = ra.translate(_DIM)
        if ra == rb:
            out.append(dim)
            continue
        line = bytearray(dim)
        for x in range(w):
            i = x * 3
            if ra[i:i + 3] == rb[i:i + 3]:
                continue
            if (abs(ra[i] - rb[i]) > threshold or abs(ra[i + 1] - rb[i + 1]) > threshold or
                    abs(ra[i + 2] - rb[i + 2]) > threshold):
                line[i:i + 3] = _MAGENTA
                bad += 1
        out.append(bytes(line))
    return out, bad


# ── args helper (snap, compare, impl, comment) ─────────────────────────────

def _split_args(args, value_opts=(), flag_opts=()):
    """-> (positionals, {opt: [values]}, {flag: bool}); None after printing an error."""
    pos, vals, flags = [], {o: [] for o in value_opts}, {f: False for f in flag_opts}
    i = 0
    while i < len(args):
        a = args[i]
        if a in vals:
            if i + 1 >= len(args):
                print(f'Error: {a} needs a value', file=sys.stderr)
                return None
            vals[a].append(args[i + 1])
            i += 2
            continue
        if a in flags:
            flags[a] = True
        elif a.startswith('--'):
            print(f'Error: unknown option: {a}', file=sys.stderr)
            return None
        else:
            pos.append(a)
        i += 1
    return pos, vals, flags


def _parse_size(sv):
    if sv in SIZE_PRESETS:
        return SIZE_PRESETS[sv]
    m = re.match(r'^(\d+)[xX](\d+)$', sv)
    if m and 0 < int(m.group(1)) <= 8000 and 0 < int(m.group(2)) <= 8000:
        return int(m.group(1)), int(m.group(2))
    return None


def _require_board(canvas, file_arg):
    """Board key for file_arg, or None after printing an error."""
    key = _board_key(file_arg)
    if key not in canvas.get('boards', {}):
        print(f'Error: no such board registered: {key}', file=sys.stderr)
        return None
    return key


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

# ── snap ───────────────────────────────────────────────────────────────────

_LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')


def _check_app_url(url):
    """Only http(s) URLs; warn when the host is not this machine. Returns False if rejected."""
    try:
        u = urlparse(url)
        host = u.hostname
    except ValueError:
        u, host = None, None
    if not u or u.scheme not in ('http', 'https') or not host:
        print(f'Error: only http:// or https:// URLs are supported (got {url!r})', file=sys.stderr)
        return False
    if host.lower() not in _LOCAL_HOSTS:
        print(f'Warning: {host} is not localhost; snap is meant for an app running on this machine',
              file=sys.stderr)
    return True


def cmd_snap(args):
    usage = ('Usage: canvas.py snap <url> --out FILE.png [--size mobile|tablet|desktop|WxH] [--wait MS] [--full-page]\n'
             '  Screenshot a running app page (http/https) with headless Chrome at exactly that size.\n'
             '  Default size: mobile. --wait: real time to wait after the page load event (default 3000 ms).\n'
             '  --full-page: capture the whole scroll height (width stays the same).')
    if not args or _is_help(args):
        print(usage); return
    parsed = _split_args(args, ('--out', '--size', '--wait'), ('--full-page',))
    if parsed is None:
        return 1
    pos, vals, flags = parsed
    if len(pos) != 1 or not vals['--out']:
        print(usage, file=sys.stderr); return 1
    url, out = pos[0], vals['--out'][-1]
    size = _parse_size(vals['--size'][-1]) if vals['--size'] else SIZE_PRESETS['mobile']
    if not size:
        print(f'Error: unknown size: {vals["--size"][-1]} (use mobile|tablet|desktop|WxH)', file=sys.stderr)
        return 1
    wait = _parse_wait(vals, 3000)
    if wait is None:
        return 1
    if not _check_app_url(url):
        return 1
    if not _capture(url, size[0], size[1], wait, out, flags['--full-page']):
        print(f'Error: snap failed (no PNG written): {url}', file=sys.stderr)
        return 1
    print(f'Snapped: {out}  ({size[0]}x{size[1]}{", full page" if flags["--full-page"] else ""})')

# ── compare ────────────────────────────────────────────────────────────────

def _parse_px(vals, opt, limit):
    """Whole-pixel option value (0 when absent), or None after printing an error."""
    try:
        v = int(vals[opt][-1]) if vals[opt] else 0
        if not 0 <= v < limit:
            raise ValueError
    except ValueError:
        print(f'Error: {opt} must be a whole number of pixels from 0 to {limit - 1}', file=sys.stderr)
        return None
    return v


def cmd_compare(args):
    usage = ('Usage: canvas.py compare <idea dir> <file> (--url URL | --png FILE) [--out DIR] [--threshold N]\n'
             '                         [--wait MS] [--ignore-top N] [--ignore-bottom N] [--align-top N]\n'
             '  Render the board at its registered size, get the app screen at the same size, and write\n'
             '  board.png, app.png, diff.png, side.png, report.json to <idea>/compare/<board id>/ (or --out DIR).\n'
             '  A pixel differs when any channel differs by more than the threshold (default 24).\n'
             '  --wait MS          real time to wait after the app page load event (default 3000)\n'
             '  --ignore-top N     leave the top N rows out of the mismatch (e.g. a status bar)\n'
             '  --ignore-bottom N  leave the bottom N rows out of the mismatch\n'
             '  --align-top N      the board draws N px (e.g. a fake status bar) the app does not have:\n'
             '                     snap the app N px shorter and place it N px down; those N rows are ignored')
    if len(args) < 2 or _is_help(args):
        print(usage); return
    parsed = _split_args(args, ('--url', '--png', '--out', '--threshold', '--wait',
                                '--ignore-top', '--ignore-bottom', '--align-top'))
    if parsed is None:
        return 1
    pos, vals, _ = parsed
    url = vals['--url'][-1] if vals['--url'] else None
    png = vals['--png'][-1] if vals['--png'] else None
    if len(pos) != 2 or (url is None) == (png is None):
        print(usage, file=sys.stderr); return 1
    try:
        threshold = int(vals['--threshold'][-1]) if vals['--threshold'] else 24
        if not 0 <= threshold <= 255:
            raise ValueError
    except ValueError:
        print('Error: --threshold must be a whole number from 0 to 255', file=sys.stderr); return 1
    wait = _parse_wait(vals, 3000)
    if wait is None:
        return 1

    idea_dir = os.path.abspath(pos[0])
    canvas = load_canvas(idea_dir)
    key = _require_board(canvas, pos[1])
    if not key:
        return 1
    src = os.path.join(idea_dir, 'boards', key)
    if not os.path.isfile(src):
        print(f'Error: board file not found: {src}', file=sys.stderr); return 1
    b = canvas['boards'][key]
    w, h = _board_size(b)
    bands = [_parse_px(vals, o, h) for o in ('--ignore-top', '--ignore-bottom', '--align-top')]
    if None in bands:
        return 1
    ignore_top, ignore_bottom, align_top = bands
    skip_top = max(ignore_top, align_top)
    if skip_top + ignore_bottom >= h:
        print(f'Error: the ignored rows cover the whole board ({h} px tall)', file=sys.stderr); return 1
    if url is not None and not _check_app_url(url):
        return 1
    if png is not None and not os.path.isfile(png):
        print(f'Error: PNG not found: {png}', file=sys.stderr); return 1
    if png is not None:
        # Check the claimed size before decoding: an app image far larger than the board only
        # costs memory and time, since it is resized to the board anyway
        try:
            with open(png, 'rb') as f:
                head = f.read(24)
        except OSError as e:
            print(f'Error: {e}', file=sys.stderr); return 1
        if head[:8] == _PNG_SIG and head[12:16] == b'IHDR':
            pw, ph = int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')
            if pw > 2 * w or ph > 2 * h + FULL_PAGE_MAX_H:
                print(f'Error: app PNG is {pw}x{ph}, too large for a {w}x{h} board (at most '
                      f'{2 * w} wide and {2 * h + FULL_PAGE_MAX_H} tall): {png}', file=sys.stderr)
                return 1
    board_id = key[:-5]
    out_dir = os.path.abspath(vals['--out'][-1]) if vals['--out'] else os.path.join(idea_dir, 'compare', board_id)
    os.makedirs(out_dir, exist_ok=True)

    board_png = os.path.join(out_dir, 'board.png')
    app_png = os.path.join(out_dir, 'app.png')
    app_h = h - align_top    # the app's own viewport is below the board's extra band
    if not _capture(pathlib.Path(src).as_uri(), w, h, 1000, board_png, file_roots=[idea_dir]):
        print(f'Error: render failed ({key})', file=sys.stderr); return 1
    if url is not None:
        if not _capture(url, w, app_h, wait, app_png):
            print(f'Error: snap failed (no PNG written): {url}', file=sys.stderr); return 1
    elif os.path.realpath(png) != os.path.realpath(app_png):
        shutil.copyfile(png, app_png)

    try:
        bw, bh, bch, brows = png_read(board_png)
        aw, ah, ach, arows = png_read(app_png)
    except (PngError, OSError) as e:
        print(f'Error: {e}', file=sys.stderr); return 1
    brows = _rgb_rows(bw, bch, brows)
    arows = _rgb_rows(aw, ach, arows)
    want_h = bh - align_top
    if aw == bw and ah > want_h and align_top:
        arows = arows[:want_h]    # a full-height app shot: its bottom rows fall off after the shift
    elif (aw, ah) != (bw, want_h):
        print(f'Warning: app image is {aw}x{ah}, expected {bw}x{want_h}; app image resized to compare',
              file=sys.stderr)
        arows = _resize_nearest(arows, aw, ah, bw, want_h)
    if align_top:
        arows = [b'\x80' * (bw * 3)] * align_top + arows

    top, bottom = skip_top, bh - ignore_bottom
    drows, bad = _diff_rows(brows[top:bottom], arows[top:bottom], bw, threshold)
    # Ignored rows: the board, darkened, never counted
    drows = ([r.translate(_IGNORED) for r in brows[:top]] + drows +
             [r.translate(_IGNORED) for r in brows[bottom:]])
    png_write(os.path.join(out_dir, 'diff.png'), bw, bh, drows)
    gap = 16
    sep = b'\x1e' * (gap * 3)
    png_write(os.path.join(out_dir, 'side.png'), bw * 3 + gap * 2, bh,
              [r1 + sep + r2 + sep + r3 for r1, r2, r3 in zip(brows, arows, drows)])
    percent = round(100.0 * bad / max(1, bw * (bottom - top)), 2)
    report = {'board': key, 'url': url, 'png': png, 'size': {'w': bw, 'h': bh},
              'mismatch_percent': percent, 'threshold': threshold,
              'ignore_top': ignore_top, 'ignore_bottom': ignore_bottom, 'align_top': align_top,
              'compared_rows': {'from': top, 'to': bottom}, 'created': _now()}
    if url is not None:
        report['wait_ms'] = wait
    save_canvas_atomic(os.path.join(out_dir, 'report.json'), report)

    # Keep comparison output out of git in ideas created before compare existed
    gi = os.path.join(idea_dir, '.gitignore')
    if not vals['--out'] and os.path.isfile(gi):
        with open(gi, encoding='utf-8') as f:
            content = f.read()
        if not {'compare', 'compare/'} & {l.strip() for l in content.splitlines()}:
            with open(gi, 'a', encoding='utf-8') as f:
                f.write(('' if not content or content.endswith('\n') else '\n') + 'compare/\n')
            print(f'Added compare/ to {gi}')

    rows_note = f', rows {top}-{bottom}' if (top, bottom) != (0, bh) else ''
    print(f'Mismatch: {percent}% of {bw}x{bottom - top} pixels (threshold {threshold}{rows_note})')
    print(f'Wrote: {out_dir}/{{board,app,diff,side}}.png, report.json')

# ── impl ───────────────────────────────────────────────────────────────────

def _in_project(project_root, f):
    """True when f is a relative path that stays inside project_root (no absolute path, no ..)."""
    if not isinstance(f, str) or not f or os.path.isabs(f):
        return False
    root = os.path.normpath(project_root)
    path = os.path.normpath(os.path.join(root, f))
    return path != root and path.startswith(root + os.sep)


def cmd_impl(args):
    usage = ('Usage: canvas.py impl <idea dir> [--strict]\n'
             '         list approved boards and whether each has an implementation\n'
             '         (--strict: exit 1 if an approved board has none)\n'
             '       canvas.py impl <idea dir> <file> --route PATH [--file PATH]...\n'
             '         record the route and source files (relative to the project root) of a board\n'
             '       canvas.py impl <idea dir> <file> --clear\n'
             '       canvas.py impl <idea dir> <file>   show one board')
    if not args or _is_help(args):
        print(usage); return
    parsed = _split_args(args, ('--route', '--file'), ('--clear', '--strict'))
    if parsed is None:
        return 1
    pos, vals, flags = parsed
    if not 1 <= len(pos) <= 2:
        print(usage, file=sys.stderr); return 1
    idea_dir = os.path.abspath(pos[0])
    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    boards = canvas.get('boards', {})

    if len(pos) == 1:
        if vals['--route'] or vals['--file'] or flags['--clear']:
            print(usage, file=sys.stderr); return 1
        missing = 0
        approved = [(f, b) for f, b in boards.items() if b.get('status') == 'approved']
        print(f'Approved boards: {len(approved)}/{len(boards)}')
        for f, b in approved:
            impl = b.get('impl')
            if isinstance(impl, dict) and impl.get('route'):
                print(f'  implemented  {f}  route {impl["route"]}  ({len(impl.get("files") or [])} file(s))')
            else:
                print(f'  missing      {f}')
                missing += 1
        for f, b in boards.items():
            if b.get('status') != 'approved' and isinstance(b.get('impl'), dict):
                print(f'Warning: {f} has an implementation but is not approved')
        if missing:
            print(f'{missing} approved board(s) without an implementation')
            if flags['--strict']:
                return 1
        return

    key = _require_board(canvas, pos[1])
    if not key:
        return 1
    b = boards[key]
    if flags['--clear']:
        if vals['--route'] or vals['--file']:
            print(usage, file=sys.stderr); return 1
        b.pop('impl', None)
        save_canvas_atomic(cj, canvas)
        print(f'Implementation cleared: {key}')
        return
    if not vals['--route']:
        if vals['--file']:
            print('Error: --route is required to record an implementation', file=sys.stderr); return 1
        impl = b.get('impl')
        if not isinstance(impl, dict):
            print(f'{key}: no implementation recorded'); return
        print(f'{key}: route {impl.get("route")}  updated {impl.get("updated", "")}')
        for f in impl.get('files') or []:
            print(f'  {f}')
        return
    files = []
    project_root = os.path.dirname(os.path.dirname(idea_dir))
    for f in vals['--file']:
        if not _in_project(project_root, f):
            print(f'Error: --file must be a path relative to the project root ({project_root}) '
                  f'that stays inside it: {f}', file=sys.stderr)
            return 1
        f = os.path.normpath(f).replace(os.sep, '/')
        if f not in files:
            files.append(f)
    b['impl'] = {'route': vals['--route'][-1], 'files': files, 'updated': _now()}
    save_canvas_atomic(cj, canvas)
    print(f'Implementation recorded: {key} -> {b["impl"]["route"]} ({len(files)} file(s))')

# ── comment ────────────────────────────────────────────────────────────────

def cmd_comment(args):
    usage = ('Usage: canvas.py comment <idea dir> <file> TEXT [--by NAME]   add a comment\n'
             '       canvas.py comment <idea dir> <file>                     list comments\n'
             '       canvas.py comment <idea dir> <file> --clear             remove all comments')
    if len(args) < 2 or _is_help(args):
        print(usage); return
    parsed = _split_args(args, ('--by',), ('--clear',))
    if parsed is None:
        return 1
    pos, vals, flags = parsed
    if not 2 <= len(pos) <= 3 or (flags['--clear'] and (len(pos) == 3 or vals['--by'])):
        print(usage, file=sys.stderr); return 1
    idea_dir = os.path.abspath(pos[0])
    cj = os.path.join(idea_dir, 'canvas.json')
    canvas = load_canvas(idea_dir)
    key = _require_board(canvas, pos[1])
    if not key:
        return 1
    b = canvas['boards'][key]
    comments = b.get('comments') if isinstance(b.get('comments'), list) else []

    if flags['--clear']:
        b.pop('comments', None)
        save_canvas_atomic(cj, canvas)
        print(f'Comments cleared: {key} ({len(comments)} removed)')
        return
    if len(pos) == 2:
        if not comments:
            print(f'{key}: no comments'); return
        for i, c in enumerate(comments, 1):
            if isinstance(c, dict):
                print(f'{i}. [{c.get("by", "")} {c.get("created", "")}] {c.get("text", "")}')
        return
    text = pos[2].strip()
    if not text:
        print('Error: comment text is empty', file=sys.stderr); return 1
    entry = {'text': text, 'by': vals['--by'][-1] if vals['--by'] else 'user', 'created': _now()}
    comments.append(entry)
    b['comments'] = comments
    save_canvas_atomic(cj, canvas)
    print(f'Comment added: {key} ({len(comments)} total)')

# ── main ───────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(line_buffering=True)
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); return
    cmd = sys.argv[1]
    _stop_on_sigterm()
    migrate_legacy_roots()
    dispatch = {
        'serve': cmd_serve, 'roots': cmd_roots,
        'new': cmd_new, 'add': cmd_add,
        'render': cmd_render, 'check': cmd_check,
        'overview': cmd_overview, 'export': cmd_export,
        'link': cmd_link, 'status': cmd_status, 'artifact': cmd_artifact,
        'group': cmd_group,
        'snap': cmd_snap, 'compare': cmd_compare,
        'impl': cmd_impl, 'comment': cmd_comment,
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
