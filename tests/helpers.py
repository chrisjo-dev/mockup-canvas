"""Shared helpers for the mockup-canvas test suite (stdlib only)."""
import http.client
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, 'skills', 'mockup-canvas', 'scripts')
CANVAS_PY = os.path.join(SCRIPTS, 'canvas.py')


def load_canvas_module():
    spec = importlib.util.spec_from_file_location('canvas_under_test', CANVAS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


canvas = load_canvas_module()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def board_html(body='<p>hello</p>', extra_head=''):
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<link rel="stylesheet" href="../shared/tokens.css">' + extra_head +
            '</head><body>' + body + '</body></html>')


class TempHomeCase(unittest.TestCase):
    """Each test gets a fake HOME and MOCKUP_CANVAS_HOME under a temp dir."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='mc-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, 'home')
        os.makedirs(self.home)
        self.data_dir = os.path.join(self.home, '.mockup-canvas')
        self.env = dict(os.environ, HOME=self.home, MOCKUP_CANVAS_HOME=self.data_dir)
        # expanduser('~') in the in-process server must see the fake HOME too
        patcher = mock.patch.dict(os.environ, {'HOME': self.home, 'MOCKUP_CANVAS_HOME': self.data_dir})
        patcher.start()
        self.addCleanup(patcher.stop)
        # In-process module state follows the same fake HOME
        for name, value in (
            ('HOME', self.home),
            ('DATA_DIR', self.data_dir),
            ('ROOTS_PATH', os.path.join(self.data_dir, 'roots.json')),
            ('CONFIG_PATH', os.path.join(self.data_dir, 'config.json')),
        ):
            old = getattr(canvas, name)
            setattr(canvas, name, value)
            self.addCleanup(setattr, canvas, name, old)

    # ── CLI ──
    def run_cli(self, *args, script=CANVAS_PY, cwd=None):
        return subprocess.run([sys.executable, script, *args], env=self.env, cwd=cwd,
                              capture_output=True, text=True, timeout=60)

    # ── fixtures ──
    def make_idea(self, design_dir, idea, boards=('A01-One.html',), links=()):
        idea_dir = os.path.join(design_dir, idea)
        os.makedirs(os.path.join(idea_dir, 'boards'), exist_ok=True)
        os.makedirs(os.path.join(idea_dir, 'shared'), exist_ok=True)
        with open(os.path.join(idea_dir, 'shared', 'tokens.css'), 'w') as f:
            f.write(':root{}')
        data = {'boards': {}, 'groups': [], 'links': list(links)}
        for i, b in enumerate(boards):
            with open(os.path.join(idea_dir, 'boards', b), 'w') as f:
                f.write(board_html())
            data['boards'][b] = {'x': i * 500, 'y': 0, 'w': 390, 'h': 844, 'title': b[:-5]}
        with open(os.path.join(idea_dir, 'canvas.json'), 'w') as f:
            json.dump(data, f)
        return idea_dir

    def read_json(self, path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)


class ServerCase(TempHomeCase):
    """Runs a handler in-process on a random free port; always shut down."""

    def start_server(self, base, **attrs):
        handler = type('TestHandler', (base,), dict(attrs))
        server = canvas.ThreadedHTTPServer(('127.0.0.1', 0), handler)
        port = server.server_address[1]
        if issubclass(handler, canvas.RegistryHandler):
            handler.server_port = port
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        def stop():
            server.shutdown()
            server.server_close()
            t.join(5)
        self.addCleanup(stop)
        self.port = port
        return port

    def origin(self):
        return {'Origin': f'http://127.0.0.1:{self.port}'}

    def request(self, method, path, body=None, headers=None, raw_body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        hdrs = dict(headers or {})
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode()
            hdrs.setdefault('Content-Type', 'application/json')
        try:
            conn.request(method, path, body=data, headers=hdrs)
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def raw_request(self, lines, body=b''):
        """Send a hand-written request (for missing or bogus Content-Length)."""
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as s:
            s.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode() + body)
            chunks = []
            while True:
                c = s.recv(65536)
                if not c:
                    break
                chunks.append(c)
        head = b''.join(chunks).split(b'\r\n', 1)[0].decode()
        return int(head.split()[1])
