"""Regression tests for the pre-publication security review (H1, H2, M1-M3, L1-L6, install.sh)."""
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from unittest import mock

from helpers import CANVAS_PY, REPO, ServerCase, TempHomeCase, canvas, free_port


def recv_all(sock, timeout):
    sock.settimeout(timeout)
    data = b''
    while True:
        c = sock.recv(65536)
        if not c:
            return data
        data += c


# ── H1: Host allowlist (DNS rebinding) ─────────────────────────────────────

class HostAllowlist(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.make_idea(self.design, 'demo')

    def raw(self, request_line, host, extra=()):
        lines = [request_line] + ([f'Host: {host}'] if host is not None else []) + list(extra)
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as s:
            s.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode())
            s.settimeout(3)
            head = s.recv(65536).split(b'\r\n', 1)[0].decode()
        return int(head.split()[1])

    def check_handler(self, base, paths, **attrs):
        self.start_server(base, **attrs)
        p = self.port
        bad_hosts = ('evil.example', f'evil.example:{p}', f'127.0.0.1:{p + 1}', f'localhost.evil.example:{p}',
                     f'192.168.1.20:{p}', None)
        for path in paths:
            for host in bad_hosts:
                self.assertEqual(self.raw(f'GET {path} HTTP/1.1', host), 421, (path, host))
            for host in (f'127.0.0.1:{p}', f'localhost:{p}', f'[::1]:{p}', f'LOCALHOST:{p}'):
                self.assertNotEqual(self.raw(f'GET {path} HTTP/1.1', host), 421, (path, host))
        # POST is gated before any body handling
        self.assertEqual(self.raw('POST /api/roots/scan HTTP/1.1', f'evil.example:{p}',
                                  [f'Origin: http://evil.example:{p}', 'Content-Type: application/json',
                                   'Content-Length: 2']), 421)

    def test_canvas_handler_rejects_foreign_host(self):
        self.check_handler(canvas.CanvasHandler, ('/', '/demo/', '/demo/canvas.json', '/demo/api/events'),
                           design_dir=self.design, share_token='', share_edit=True, read_only=False)

    def test_registry_handler_rejects_foreign_host(self):
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})
        self.check_handler(canvas.RegistryHandler, ('/', '/p/demo/', '/p/demo/api/events'),
                           share_token='', share_edit=True, read_only=False)

    def test_share_mode_accepts_lan_host_only_in_share_mode(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='tok_lan_1',
                          share_edit=False, read_only=False, share_host='192.168.1.20')
        self.assertEqual(self.raw('GET / HTTP/1.1', f'192.168.1.20:{self.port}',
                                  ['Cookie: canvas_token=tok_lan_1']), 200)
        self.assertEqual(self.raw('GET / HTTP/1.1', f'192.168.1.21:{self.port}',
                                  ['Cookie: canvas_token=tok_lan_1']), 421)
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='',
                          share_edit=True, read_only=False, share_host='192.168.1.20')
        self.assertEqual(self.raw('GET / HTTP/1.1', f'192.168.1.20:{self.port}'), 421)


# ── M1: layout POST needs same Origin and exact JSON media type ────────────

class LayoutCsrf(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo')
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token='', share_edit=True, read_only=False)

    def post(self, headers, raw=b'{"board":"A01-One.html","x":7,"y":8}'):
        return self.request('POST', '/demo/api/layout', raw_body=raw, headers=headers)[0]

    def test_layout_requires_same_origin(self):
        json_ct = {'Content-Type': 'application/json'}
        for extra in ({}, {'Origin': 'http://evil.example'}, {'Origin': 'null'},
                      {'Origin': f'http://127.0.0.1:{self.port + 1}'}, {'Referer': 'http://evil.example/demo/'}):
            self.assertEqual(self.post(dict(json_ct, **extra)), 403, extra)
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['x'], 0)
        self.assertEqual(self.post(dict(json_ct, Referer=f'http://localhost:{self.port}/demo/')), 200)
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['x'], 7)

    def test_layout_requires_exact_json_media_type(self):
        for ct in ('text/plain', 'text/plain; x=application/json', 'application/jsonp',
                   'application/json-patch+json', 'multipart/form-data; boundary=application/json', ''):
            self.assertEqual(self.post(dict(self.origin(), **{'Content-Type': ct})), 400, ct)
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['x'], 0)
        self.assertEqual(self.post(dict(self.origin(), **{'Content-Type': 'Application/JSON; charset=utf-8'})), 200)

    def test_share_edit_accepts_lan_origin(self):
        token = 'tok_edit_1'
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token=token,
                          share_edit=True, read_only=False, share_host='192.168.1.20')
        lan = f'192.168.1.20:{self.port}'
        base = {'Host': lan, 'Cookie': 'canvas_token=' + token, 'Content-Type': 'application/json'}
        self.assertEqual(self.post(dict(base, Origin='http://evil.example')), 403)
        self.assertEqual(self.post(dict(base, Origin='http://' + lan)), 200)

    def test_viewer_sends_json_content_type(self):
        with open(canvas.VIEWER_PATH, encoding='utf-8') as f:
            viewer = f.read()
        self.assertIn("headers: { 'Content-Type': 'application/json' }", viewer)


# ── M2: boards are sandboxed ───────────────────────────────────────────────

class SandboxedBoards(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo')
        os.makedirs(os.path.join(self.idea, 'assets'))
        for name, data in (('art.svg', '<svg xmlns="http://www.w3.org/2000/svg"/>'), ('page.html', '<p>x</p>'),
                           ('f.woff2', 'x'), ('pic.png', 'x')):
            with open(os.path.join(self.idea, 'assets', name), 'w') as f:
                f.write(data)

    def test_board_and_active_assets_get_sandbox_csp(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token='', share_edit=True, read_only=False)
        csp = 'sandbox allow-scripts allow-forms allow-popups'
        for path in ('/demo/boards/A01-One.html', '/demo/assets/art.svg', '/demo/assets/page.html'):
            status, headers, _ = self.request('GET', path)
            self.assertEqual(status, 200, path)
            self.assertEqual(headers.get('Content-Security-Policy'), csp, path)
        status, headers, _ = self.request('GET', '/demo/assets/f.woff2')
        self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')
        for path in ('/demo/assets/pic.png', '/demo/shared/tokens.css', '/demo/canvas.json', '/demo/'):
            _, headers, _ = self.request('GET', path)
            self.assertNotIn('Access-Control-Allow-Origin', headers, path)
        self.assertNotIn('Content-Security-Policy', self.request('GET', '/demo/shared/tokens.css')[1])

    def test_viewer_iframes_are_sandboxed(self):
        with open(canvas.VIEWER_PATH, encoding='utf-8') as f:
            viewer = f.read()
        self.assertIn("iframe.setAttribute('sandbox', 'allow-scripts allow-forms allow-popups'", viewer)
        self.assertNotIn("allow-same-origin'", viewer.replace("' allow-same-origin'", ''))

    def test_share_mode_keyed_static_path(self):
        token = 'tok_keyed_1'
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token=token,
                          share_edit=False, read_only=False)
        _, _, body = self.request('GET', '/demo/', headers={'Cookie': 'canvas_token=' + token})
        html = body.decode()
        self.assertIn('var CANVAS_ASSET_PREFIX="/_k/', html)
        prefix = html.split('CANVAS_ASSET_PREFIX="', 1)[1].split('"', 1)[0]
        self.assertNotIn(token, prefix)
        # Without a cookie (as from a sandboxed board), static files load through the key only
        self.assertEqual(self.request('GET', '/demo/shared/tokens.css')[0], 401)
        self.assertEqual(self.request('GET', prefix + '/demo/shared/tokens.css')[0], 200)
        self.assertEqual(self.request('GET', prefix + '/demo/boards/A01-One.html')[0], 200)
        for path in ('/demo/', '/demo/canvas.json', '/demo/api/events', '/', '/demo/shared/%2e%2e/canvas.json'):
            self.assertEqual(self.request('GET', prefix + path)[0], 404, path)
        self.assertEqual(self.request('GET', '/_k/' + '0' * 32 + '/demo/shared/tokens.css')[0], 401)
        self.assertEqual(self.request('POST', prefix + '/demo/api/layout', {'board': 'A01-One.html', 'x': 1, 'y': 1},
                                      headers=self.origin())[0], 403)

    def test_registry_share_keyed_static_path(self):
        token = 'tok_keyed_2'
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=False, read_only=False,
                          frozen_roots=[{'name': 'p', 'path': self.design}])
        _, _, body = self.request('GET', '/p/demo/', headers={'Cookie': 'canvas_token=' + token})
        prefix = body.decode().split('CANVAS_ASSET_PREFIX="', 1)[1].split('"', 1)[0]
        self.assertEqual(self.request('GET', prefix + '/p/demo/shared/tokens.css')[0], 200)
        self.assertEqual(self.request('GET', prefix + '/p/demo/canvas.json')[0], 404)
        self.assertEqual(self.request('GET', prefix + '/p/demo/')[0], 404)


# ── M3: timeouts and connection limit ──────────────────────────────────────

class Timeouts(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.make_idea(self.design, 'demo')

    def test_default_timeout_and_limit(self):
        self.assertEqual(canvas.CanvasHandler.timeout, 15)
        self.assertEqual(canvas.ThreadedHTTPServer.max_connections, 64)

    def test_idle_connection_is_closed(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='',
                          share_edit=True, read_only=False, timeout=1)
        with socket.create_connection(('127.0.0.1', self.port)) as s:
            s.sendall(b'GET / HTTP/1.1\r\n')   # never finishes the request
            t0 = time.time()
            self.assertEqual(recv_all(s, 10), b'')
            self.assertLess(time.time() - t0, 5)

    def test_sse_is_exempt_from_timeout(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='',
                          share_edit=True, read_only=False, timeout=1)
        with socket.create_connection(('127.0.0.1', self.port)) as s:
            s.sendall(f'GET /demo/api/events HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n\r\n'.encode())
            s.settimeout(5)
            got = b''
            while b': ping' not in got:
                got += s.recv(65536)
            self.assertIn(b'200', got.split(b'\r\n', 1)[0])
            s.settimeout(2.5)
            with self.assertRaises(socket.timeout):   # still open after the 1 s handler timeout
                s.recv(65536)

    def test_connection_limit_returns_503(self):
        server_cls = type('Small', (canvas.ThreadedHTTPServer,), {'max_connections': 2})
        handler = type('H', (canvas.CanvasHandler,), {'design_dir': self.design, 'share_token': '',
                                                      'share_edit': True, 'read_only': False, 'timeout': 5})
        server = server_cls(('127.0.0.1', 0), handler)
        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close()))
        port = server.server_address[1]
        idle = [socket.create_connection(('127.0.0.1', port)) for _ in range(2)]
        try:
            time.sleep(0.3)
            with socket.create_connection(('127.0.0.1', port)) as s:
                # The server answers before reading anything
                self.assertTrue(recv_all(s, 5).startswith(b'HTTP/1.1 503'))
        finally:
            for s in idle:
                s.close()
        # Slots come back once the idle connections close
        deadline = time.time() + 5
        while True:
            with socket.create_connection(('127.0.0.1', port)) as s:
                s.sendall(f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n'.encode())
                resp = recv_all(s, 5)
            if b' 200 ' in resp.split(b'\r\n', 1)[0] or time.time() > deadline:
                break
            time.sleep(0.2)
        self.assertIn(b' 200 ', resp.split(b'\r\n', 1)[0])


# ── L1: registry share mode ────────────────────────────────────────────────

class RegistryShareIndex(ServerCase):
    def setUp(self):
        super().setUp()
        self.d_a = os.path.join(self.home, 'work', 'alpha', 'design')
        self.d_b = os.path.join(self.home, 'work', 'beta', 'design')
        self.make_idea(self.d_a, 'ideaA')
        self.make_idea(self.d_b, 'ideaB')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {'roots': [{'name': 'alpha', 'path': self.d_a}]})

    def test_share_index_hides_paths_and_management(self):
        token = 'tok_idx_1'
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=False, read_only=False,
                          frozen_roots=[{'name': 'alpha', 'path': self.d_a},
                                        {'name': 'gone', 'path': os.path.join(self.home, 'gone')}])
        status, _, body = self.request('GET', '/', headers={'Cookie': 'canvas_token=' + token})
        html = body.decode()
        self.assertEqual(status, 200)
        self.assertIn('/alpha/ideaA/', html)
        for hidden in (self.home, 'Add project', 'Find in folders', 'removeProject', 'class="btn-remove"',
                       '/api/roots', 'gone'):
            self.assertNotIn(hidden, html, hidden)

    def test_local_index_keeps_management(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        html = self.request('GET', '/')[2].decode()
        for shown in ('~/work/alpha/design', 'Add project', 'Find in folders', 'removeProject', "'/api/roots/scan'",
                      'from the list? No files are deleted.', "'/api/reveal'"):
            self.assertIn(shown, html, shown)

    def test_share_roots_are_frozen(self):
        token = 'tok_idx_2'
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=False, read_only=False,
                          frozen_roots=[{'name': 'alpha', 'path': self.d_a}])
        cookie = {'Cookie': 'canvas_token=' + token}
        self.write_json(self.roots_json, {'roots': [{'name': 'alpha', 'path': self.d_a},
                                                    {'name': 'beta', 'path': self.d_b}]})
        self.assertEqual(self.request('GET', '/beta/ideaB/', headers=cookie)[0], 404)
        self.assertNotIn(b'beta', self.request('GET', '/', headers=cookie)[2])
        self.assertEqual(self.request('GET', '/alpha/ideaA/', headers=cookie)[0], 200)


class ServeProjectCli(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.d_a = os.path.join(self.home, 'work', 'alpha', 'design')
        self.d_b = os.path.join(self.home, 'work', 'beta', 'design')
        self.make_idea(self.d_a, 'ideaA')
        self.make_idea(self.d_b, 'ideaB')
        self.write_json(os.path.join(self.data_dir, 'roots.json'),
                        {'roots': [{'name': 'alpha', 'path': self.d_a}, {'name': 'beta', 'path': self.d_b}]})

    def test_share_single_project(self):
        port = free_port()
        proc = subprocess.Popen([sys.executable, CANVAS_PY, 'serve', '--port', str(port), '--share',
                                 '--project', 'beta', '--minutes', '1'],
                                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (proc.poll() is None and proc.kill(), proc.wait(5),
                                 proc.stdout.close(), proc.stderr.close()))
        url = proc.stdout.readline().split('Share URL: ', 1)[1].strip()
        self.assertIn('project beta', proc.stdout.readline())
        token = url.split('?t=', 1)[1]
        import http.client
        def get(path):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            try:
                conn.request('GET', path, headers={'Cookie': 'canvas_token=' + token})
                r = conn.getresponse()
                return r.status, r.read()
            finally:
                conn.close()
        status, body = get('/')
        self.assertEqual(status, 200)
        self.assertIn(b'/beta/ideaB/', body)
        self.assertNotIn(b'alpha', body)
        self.assertEqual(get('/alpha/ideaA/')[0], 404)
        self.assertEqual(get('/beta/ideaB/')[0], 200)

    def test_project_errors(self):
        r = self.run_cli('serve', '--share', '--project', 'nope', '--port', str(free_port()))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no registered project named 'nope'", r.stderr)
        r = self.run_cli('serve', '--project', 'alpha', '--port', str(free_port()))
        self.assertEqual(r.returncode, 2)
        self.assertIn('--project is only used with --share', r.stderr)


# ── L2: token comparison ───────────────────────────────────────────────────

class TokenBytes(ServerCase):
    def test_non_ascii_token_is_401(self):
        design = os.path.join(self.home, 'p', 'design')
        self.make_idea(design, 'demo')
        self.start_server(canvas.CanvasHandler, design_dir=design, share_token='tok_ascii_1',
                          share_edit=False, read_only=False)
        self.assertEqual(self.request('GET', '/?t=%C3%A9%E2%80%A8')[0], 401)
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as s:
            s.sendall(f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n'.encode() +
                      'Cookie: canvas_token=éèx\r\n\r\n'.encode('utf-8'))
            self.assertIn(b' 401 ', recv_all(s, 10).split(b'\r\n', 1)[0] + b' ')
        real = canvas.hmac.compare_digest
        seen = []
        def spy(a, b):
            seen.append((type(a), type(b)))
            return real(a, b)
        with mock.patch.object(canvas.hmac, 'compare_digest', side_effect=spy):
            self.request('GET', '/', headers={'Cookie': 'canvas_token=tok_ascii_1'})
        self.assertTrue(seen)
        self.assertTrue(all(t == (bytes, bytes) for t in seen), seen)


# ── L3: --minutes range ────────────────────────────────────────────────────

class MinutesRange(TempHomeCase):
    def test_minutes_out_of_range(self):
        design = os.path.join(self.home, 'p', 'design')
        self.make_idea(design, 'demo')
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': design}]})
        for value in ('0', '241', '-5', 'abc', '1e3'):
            for prefix in ([design], []):
                r = self.run_cli('serve', *prefix, '--share', '--minutes', value, '--port', str(free_port()))
                self.assertEqual(r.returncode, 2, (value, prefix, r.stdout))
                self.assertIn('--minutes must be a whole number from 1 to 240', r.stderr)
                self.assertNotIn('Share URL', r.stdout)


# ── L4: export output folder ───────────────────────────────────────────────

class ExportSafety(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo')

    def test_refuses_overlapping_outdir(self):
        before = sorted(os.listdir(self.idea))
        for out in (self.idea, os.path.join(self.idea, 'export'), os.path.join(self.idea, 'boards'),
                    self.design, os.path.join(self.home, 'p')):
            r = self.run_cli('export', self.idea, out)
            self.assertEqual(r.returncode, 1, out)
            self.assertIn('must not be the idea folder, inside it, or contain it', r.stderr)
        self.assertEqual(sorted(os.listdir(self.idea)), before)
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'boards', 'A01-One.html')))
        # A symlinked outdir that resolves into the idea folder is refused too
        link = os.path.join(self.tmp, 'sneaky')
        os.symlink(self.idea, link)
        self.assertEqual(self.run_cli('export', self.idea, link).returncode, 1)

    def test_symlinks_outside_are_skipped(self):
        secret = os.path.join(self.home, 'secret.txt')
        with open(secret, 'w') as f:
            f.write('TOPSECRET')
        os.symlink(secret, os.path.join(self.idea, 'shared', 'leak.css'))
        os.symlink(self.home, os.path.join(self.idea, 'shared', 'homedir'))
        os.symlink('../shared/tokens.css', os.path.join(self.idea, 'boards', 'inner.css'))
        out = os.path.join(self.tmp, 'out')
        r = self.run_cli('export', self.idea, out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Skipped symlink outside the idea folder', r.stderr)
        self.assertFalse(os.path.lexists(os.path.join(out, 'shared', 'leak.css')))
        self.assertFalse(os.path.lexists(os.path.join(out, 'shared', 'homedir')))
        inner = os.path.join(out, 'boards', 'inner.css')
        self.assertTrue(os.path.islink(inner))
        self.assertEqual(os.readlink(inner), '../shared/tokens.css')
        for root, _, files in os.walk(out):
            for name in files:
                p = os.path.join(root, name)
                if os.path.isfile(p):
                    with open(p, 'rb') as f:
                        self.assertNotIn(b'TOPSECRET', f.read(), p)


# ── L5: error messages, root header, server banner ─────────────────────────

class ErrorDisclosure(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.make_idea(self.design, 'demo')
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token='', share_edit=True, read_only=False)

    def test_generic_errors_and_banner(self):
        cj = os.path.join(self.design, 'demo', 'canvas.json')
        for body in (b'{"board":"A01-One.html","x":"abc","y":1}', b'{"x":1}', b'not json', b'[1]'):
            with mock.patch('sys.stderr') as err:
                status, headers, resp = self.request('POST', '/demo/api/layout', raw_body=body,
                                                     headers=dict(self.origin(), **{'Content-Type': 'application/json'}))
            self.assertEqual(status, 400, body)
            self.assertEqual(json.loads(resp), {'ok': False, 'error': 'Invalid request'}, body)
        os.chmod(cj, 0o444)
        os.chmod(os.path.dirname(cj), 0o555)
        self.addCleanup(os.chmod, os.path.dirname(cj), 0o755)
        with mock.patch('sys.stderr') as err:
            status, _, resp = self.request('POST', '/demo/api/layout', {'board': 'A01-One.html', 'x': 1, 'y': 2},
                                           headers=self.origin())
        self.assertEqual(status, 400)
        self.assertNotIn(self.home.encode(), resp)
        self.assertTrue(err.write.called)   # details go to stderr
        self.assertEqual(headers.get('Server'), 'mockup-canvas')
        self.assertNotIn('Python', json.dumps(headers))

    def test_root_header_is_hash_and_detects_same_server(self):
        _, headers, _ = self.request('GET', '/')
        self.assertEqual(headers[canvas.HEADER_ROOT], canvas._root_id(self.design))
        self.assertNotIn('/', headers[canvas.HEADER_ROOT])
        self.assertEqual(canvas.check_existing_server(self.port), canvas._root_id(self.design))
        r = self.run_cli('serve', self.design, '--port', str(self.port))
        self.assertIn(f'Already running: http://127.0.0.1:{self.port}/', r.stdout)


# ── L6: embedded JSON ──────────────────────────────────────────────────────

class EmbeddedJson(TempHomeCase):
    def test_every_lt_is_escaped(self):
        data = {'t': '<!-- <script> </script> <  '}
        s = canvas._embed_json(data)
        self.assertNotIn('<', s)
        self.assertNotIn(' ', s)
        self.assertNotIn(' ', s)
        self.assertEqual(json.loads(s), data)

    def test_export_data_script_has_no_lt(self):
        idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo')
        cj = os.path.join(idea, 'canvas.json')
        data = self.read_json(cj)
        data['boards']['A01-One.html']['title'] = '<!--<script>'
        self.write_json(cj, data)
        out = os.path.join(self.tmp, 'out')
        self.assertEqual(self.run_cli('export', idea, out).returncode, 0)
        with open(os.path.join(out, 'index.html'), encoding='utf-8') as f:
            html = f.read()
        script = html.split('<script id="canvas-data-script">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('<', script)
        self.assertIn('\\u003c!--\\u003cscript>', script)

    def test_viewer_coerces_numbers_and_colors(self):
        with open(canvas.VIEWER_PATH, encoding='utf-8') as f:
            viewer = f.read()
        self.assertIn('canvasData = normalize(', viewer)
        self.assertIn("safeColor(grp.color,", viewer)
        self.assertIn("safeColor(grp.textColor,", viewer)
        self.assertNotIn('grp.color ||', viewer)


# ── H2: render and overview launch Chrome without file access ──────────────

class ChromeLaunchArgs(TempHomeCase):
    """DevTools launch flags. A local board never falls back to --screenshot, which could not
    stop it from showing other local files."""

    def setUp(self):
        super().setUp()
        self.idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo board')

    def run_cmd(self, fn, *args):
        calls = []

        def record(cmd):
            profile = next(a.split('=', 1)[1] for a in cmd if a.startswith('--user-data-dir='))
            calls.append((list(cmd), os.path.isdir(profile), profile))

        class FakePopen:
            # DevTools never comes up
            def __init__(self, cmd, **kw):
                record(cmd)
                self.returncode = 1

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode
        with mock.patch.object(canvas, '_get_chrome', return_value='/fake/chrome'), \
                mock.patch.object(canvas.subprocess, 'Popen', FakePopen), \
                mock.patch('sys.stdout'), mock.patch('sys.stderr') as err:
            with self.assertRaises(SystemExit):   # the render fails
                fn(list(args))
        self.assertIn('a local board is not rendered without it',
                      ''.join(str(c.args[0]) for c in err.write.call_args_list))
        return calls

    def check(self, calls):
        self.assertTrue(calls)
        profiles = set()
        for cmd, existed, profile in calls:
            self.assertNotIn('--allow-file-access-from-files', cmd)
            self.assertFalse(any('allow-file-access' in a or 'disable-web-security' in a for a in cmd), cmd)
            self.assertTrue(existed)
            self.assertFalse(os.path.exists(profile), 'profile not deleted')
            # DevTools launch: random localhost port, page loaded later over CDP; no --screenshot
            self.assertIn('--remote-debugging-port=0', cmd)
            self.assertIn('--remote-debugging-address=127.0.0.1', cmd)
            self.assertEqual(cmd[-1], 'about:blank')
            self.assertFalse(any(a.startswith('--screenshot') for a in cmd))
            profiles.add(profile)
        self.assertEqual(len(profiles), len(calls), 'profile reused')

    def test_render_args(self):
        self.check(self.run_cmd(canvas.cmd_render, self.idea))

    def test_overview_args(self):
        self.check(self.run_cmd(canvas.cmd_overview, self.idea))


# ── install.sh --dry-run ───────────────────────────────────────────────────

class InstallDryRun(TempHomeCase):
    def test_dry_run_says_would(self):
        existing = os.path.join(self.home, '.claude', 'skills', 'mockup-canvas')
        os.makedirs(existing)
        r = subprocess.run(['bash', os.path.join(REPO, 'install.sh'), '--dry-run'], env=self.env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Would back up: ' + existing, r.stdout)
        self.assertIn('Would link: ' + existing, r.stdout)
        self.assertIn('Would link: ' + os.path.join(self.home, '.codex', 'skills', 'mockup-canvas'), r.stdout)
        self.assertNotIn('Linked:', r.stdout)
        self.assertNotIn('Backup:', r.stdout)
        self.assertTrue(os.path.isdir(existing) and not os.path.islink(existing))
        self.assertFalse(os.path.exists(os.path.join(self.home, '.codex')))
        self.assertFalse(os.path.exists(os.path.join(self.data_dir, 'backup')))


if __name__ == '__main__':
    unittest.main()
