"""A board cannot bake local files outside its idea folder, or a page from a local server, into a
PNG (real Chrome).

The secret file and the local server's page paint the whole page red; boards put them in
full-size iframes. A control board loads a green page from its own assets/ folder, which must
still work. The local server also counts requests: a blocked request never reaches it."""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from helpers import CANVAS_PY, ServerCase, TempHomeCase, canvas

RED, GREEN = (255, 0, 0), (0, 128, 0)


def colored(path, rgb):
    """Pixels of path within 30 of rgb on every channel."""
    w, h, ch, rows = canvas.png_read(path)
    n = 0
    for row in rows:
        for i in range(0, len(row), ch):
            if all(abs(row[i + k] - rgb[k]) <= 30 for k in range(3)):
                n += 1
    return n


def frame(src):
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<style>html,body{margin:0;background:#fff}iframe{border:0;width:100vw;height:100vh;display:block}</style>'
            f'</head><body><iframe src="{src}"></iframe></body></html>')


class _Secret(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        _Secret.hits.append(self.path)
        body = b'<!doctype html><body style="margin:0;background:#f00;height:100vh">server secret</body>'
        ctype = 'text/html'
        local = f'http://localhost:{self.server.server_address[1]}'
        if self.path == '/sw-page':
            # A page on an allowed origin installs a service worker that reaches for localhost
            body = b'<!doctype html><body><script>navigator.serviceWorker.register("/sw.js")</script></body>'
        elif self.path == '/sw.js':
            ctype = 'text/javascript'
            body = (f'self.addEventListener("install", e => e.waitUntil(fetch("{local}/from-sw").catch(() => 0)));'
                    f'fetch("{local}/from-sw-top").catch(() => 0);').encode()
        if self.path == '/outer':
            # Stands in for an allowed public page that reaches for localhost from its own process
            local = f'http://localhost:{self.server.server_address[1]}'
            body = (f'<!doctype html><body style="margin:0"><iframe src="{local}/inner"></iframe>'
                    f'<img src="{local}/img"><script>fetch("{local}/fetch").catch(() => 0);'
                    f'new Worker(URL.createObjectURL(new Blob([`fetch("{local}/worker")`])))'
                    '</script></body>').encode()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class LocalFiles(TempHomeCase):
    BOARDS = ('A01-Leak', 'A02-Ok', 'A03-Server')

    def setUp(self):
        super().setUp()
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Secret)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        _Secret.hits = []
        port = self.server_port = srv.server_address[1]
        secret_dir = os.path.join(self.tmp, 'outside')
        os.makedirs(secret_dir)
        self.secret = os.path.join(secret_dir, 'secret.html')
        with open(self.secret, 'w') as f:
            f.write('<!doctype html><body style="margin:0;background:#f00;height:100vh">secret</body>')
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=tuple(b + '.html' for b in self.BOARDS))
        os.makedirs(os.path.join(self.idea, 'assets'))
        with open(os.path.join(self.idea, 'assets', 'ok.html'), 'w') as f:
            f.write('<!doctype html><body style="margin:0;background:#008000;height:100vh">ok</body>')
        with open(os.path.join(self.idea, 'boards', 'A01-Leak.html'), 'w') as f:
            f.write(frame('file://' + self.secret))
        with open(os.path.join(self.idea, 'boards', 'A02-Ok.html'), 'w') as f:
            f.write(frame('../assets/ok.html'))
        with open(os.path.join(self.idea, 'boards', 'A03-Server.html'), 'w') as f:
            f.write(frame(f'http://127.0.0.1:{port}/a').replace(
                '</body>', f'<iframe src="http://localhost:{port}/b"></iframe>'
                           f'<img src="http://[::1]:{port}/c"></body>'))
        cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(cj)
        for b in data['boards'].values():
            b.update(w=400, h=300)
        self.write_json(cj, data)


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class CliCaptures(LocalFiles):
    def test_render_blocks_files_outside_the_idea(self):
        r = self.run_cli('render', self.idea)
        self.assertEqual(r.returncode, 0, r.stderr)
        leak = os.path.join(self.idea, 'render', 'A01-Leak.png')
        ok = os.path.join(self.idea, 'render', 'A02-Ok.png')
        server = os.path.join(self.idea, 'render', 'A03-Server.png')
        self.assertEqual(colored(leak, RED), 0, 'local file baked into the render')
        self.assertGreater(colored(ok, GREEN), 400 * 300 // 2, 'files inside the idea must still load')
        self.assertEqual(colored(server, RED), 0, 'local server page baked into the render')
        self.assertEqual(_Secret.hits, [])

    def test_compare_board_render_blocks_files_outside_the_idea(self):
        app = os.path.join(self.tmp, 'app.png')
        canvas.png_write(app, 400, 300, [bytes(400 * 3)] * 300)
        out = os.path.join(self.tmp, 'cmp')
        r = self.run_cli('compare', self.idea, 'A01-Leak', '--png', app, '--out', out)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertEqual(colored(os.path.join(out, 'board.png'), RED), 0)
        r = self.run_cli('compare', self.idea, 'A03-Server', '--png', app, '--out', out)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertEqual(colored(os.path.join(out, 'board.png'), RED), 0)
        self.assertEqual(_Secret.hits, [])

    def test_snap_still_opens_a_local_dev_server(self):
        # snap is for the user's own running app, so localhost stays reachable there
        port = self.server_port
        out = os.path.join(self.tmp, 'snap.png')
        r = self.run_cli('snap', f'http://127.0.0.1:{port}/app', '--size', '400x300', '--out', out,
                         '--wait', '0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(colored(out, RED), 400 * 300 // 2)
        self.assertIn('/app', _Secret.hits)

    def test_cross_origin_frame_cannot_reach_private_hosts(self):
        # Pretend 127.0.0.1 is a public host: its page runs as a separate (out-of-process) frame
        # whose requests the board page's own Fetch does not see; child targets are guarded too
        board = os.path.join(self.idea, 'boards', 'A04-Nested.html')
        with open(board, 'w') as f:
            f.write(frame(f'http://127.0.0.1:{self.server_port}/outer'))
        out = os.path.join(self.tmp, 'nested.png')
        with mock.patch.object(canvas, '_host_blocked', lambda h: h != '127.0.0.1'):
            self.assertTrue(canvas._capture(pathlib.Path(board).as_uri(), 400, 300, 1000, out,
                                            file_roots=[self.idea]))
        self.assertEqual(set(_Secret.hits), {'/outer'})
        self.assertEqual(colored(out, RED), 0)

    def test_websockets_cannot_reach_private_hosts(self):
        # Request interception never sees a WebSocket handshake; the guard proxy does
        import socket
        lst = socket.socket()
        lst.bind(('127.0.0.1', 0))
        lst.listen(8)
        lst.settimeout(0.2)
        self.addCleanup(lst.close)
        port = lst.getsockname()[1]
        board = os.path.join(self.idea, 'boards', 'A05-Ws.html')
        with open(board, 'w') as f:
            f.write('<!doctype html><body><script>'
                    f'for (const h of ["127.0.0.1", "localhost", "[::ffff:127.0.0.1]"]) '
                    f'{{ try {{ new WebSocket("ws://" + h + ":{port}/"); }} catch (e) {{}} }}'
                    '</script></body>')
        out = os.path.join(self.tmp, 'ws.png')
        self.assertTrue(canvas._capture(pathlib.Path(board).as_uri(), 400, 300, 1500, out,
                                        file_roots=[self.idea]))
        try:
            conn, _ = lst.accept()
            conn.close()
            self.fail('a board render opened a WebSocket to 127.0.0.1')
        except socket.timeout:
            pass

    def test_service_workers_cannot_reach_private_hosts(self):
        # Pretend 127.0.0.1 is public: its page installs a service worker, which runs outside the
        # board's DevTools targets and fetches localhost
        board = os.path.join(self.idea, 'boards', 'A06-Sw.html')
        with open(board, 'w') as f:
            f.write(frame(f'http://127.0.0.1:{self.server_port}/sw-page'))
        out = os.path.join(self.tmp, 'sw.png')
        with mock.patch.object(canvas, '_host_blocked', lambda h: h != '127.0.0.1'):
            self.assertTrue(canvas._capture(pathlib.Path(board).as_uri(), 400, 300, 2500, out,
                                            file_roots=[self.idea]))
        self.assertIn('/sw.js', _Secret.hits)   # the worker did install
        self.assertNotIn('/from-sw', _Secret.hits)
        self.assertNotIn('/from-sw-top', _Secret.hits)

    def test_overview_blocks_files_outside_the_idea(self):
        r = self.run_cli('overview', self.idea)
        self.assertEqual(r.returncode, 0, r.stderr)
        png = os.path.join(self.idea, 'render', '_overview.png')
        self.assertEqual(colored(png, RED), 0)
        self.assertGreater(colored(png, GREEN), 0)
        self.assertEqual(_Secret.hits, [])


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class Thumbnails(LocalFiles, ServerCase):
    def render_thumbs(self, **attrs):
        q = canvas._ThumbQueue()
        self.addCleanup(q.close_all)
        p = mock.patch.object(canvas, '_THUMBS', q)
        p.start()
        self.addCleanup(p.stop)
        self.start_server(canvas.CanvasHandler, **dict(dict(design_dir=self.design, share_token='',
                                                           share_edit=True, read_only=False), **attrs))
        headers = {'Cookie': 'canvas_token=' + attrs['share_token']} if attrs.get('share_token') else {}
        outs = {}
        for name in self.BOARDS:
            self.assertEqual(self.request('GET', f'/demo/thumbs/{name}.png', headers=headers)[0], 202)
            outs[name] = canvas._thumb_target(self.idea, name + '.html')[3]
        end = time.monotonic() + 60
        while not all(os.path.isfile(o) for o in outs.values()):
            self.assertLess(time.monotonic(), end, 'thumbnails not rendered')
            time.sleep(0.2)
        return outs

    def check(self, outs):
        self.assertEqual(colored(outs['A01-Leak'], RED), 0, 'local file baked into the thumbnail')
        self.assertEqual(colored(outs['A03-Server'], RED), 0, 'local server page baked into the thumbnail')
        self.assertEqual(_Secret.hits, [])
        w, h, _, _ = canvas.png_read(outs['A02-Ok'])
        self.assertGreater(colored(outs['A02-Ok'], GREEN), w * h // 2)

    def test_thumbnail_blocks_local_files(self):
        self.check(self.render_thumbs())

    def test_thumbnail_in_share_mode(self):
        self.check(self.render_thumbs(share_token='tok_ABCdef123456', share_edit=False))


class PrivateHosts(unittest.TestCase):
    def setUp(self):
        canvas._DNS_CACHE.clear()
        self.addCleanup(canvas._DNS_CACHE.clear)

    def test_names_and_ip_literals(self):
        for host in ('localhost', 'LOCALHOST.', 'app.localhost', 'printer.local', '', None,
                     '127.0.0.1', '127.8.9.1', '10.1.2.3', '172.16.0.1', '172.31.255.255',
                     '192.168.1.1', '169.254.169.254', '0.0.0.0', '::1', '::', 'fc00::1',
                     'fd12:3456::1', 'fe80::1', '::ffff:127.0.0.1', '::ffff:10.0.0.1',
                     # IPv4 inside IPv6: NAT64, local-use NAT64, 6to4, IPv4-compatible, Teredo
                     '64:ff9b::7f00:1', '64:ff9b::a00:1', '64:ff9b:1::a00:1', '3fff::1', '5f00::1', '2002:7f00:1::1',
                     '2002:c0a8:101::', '::127.0.0.1', '::10.0.0.1', '2001:0:4136:e378:8000:63bf:3fff:fdd2',
                     # shared (CGNAT), multicast, reserved, broadcast
                     '100.64.0.1', '224.0.0.1', '240.0.0.1', '255.255.255.255', 'ff02::1'):
            self.assertTrue(canvas._host_blocked(host), host)
        for host in ('8.8.8.8', '172.32.0.1', '192.169.0.1', '2001:4860:4860::8888',
                     '64:ff9b::808:808', '2002:808:808::1'):
            self.assertFalse(canvas._host_blocked(host), host)

    def addr(self, *ips):
        return [(0, 0, 0, '', (ip, 0)) for ip in ips]

    def test_dns_names_are_resolved_and_cached(self):
        with mock.patch.object(canvas.socket, 'getaddrinfo',
                               return_value=self.addr('142.250.1.1', '2a00:1450::1')) as gai:
            self.assertFalse(canvas._host_blocked('fonts.example'))
            self.assertFalse(canvas._host_blocked('fonts.example'))
            self.assertEqual(gai.call_count, 1)
        # one private address among public ones is enough to block (DNS pointing inward)
        with mock.patch.object(canvas.socket, 'getaddrinfo',
                               return_value=self.addr('142.250.1.1', '127.0.0.1')):
            self.assertTrue(canvas._host_blocked('rebind.example'))
        with mock.patch.object(canvas.socket, 'getaddrinfo', side_effect=OSError('no such host')):
            self.assertTrue(canvas._host_blocked('nowhere.example'))

    def test_slow_dns_times_out_and_blocks(self):
        def slow(*a, **kw):
            time.sleep(1)
            return self.addr('142.250.1.1')
        with mock.patch.object(canvas, '_DNS_TIMEOUT', 0.1), \
                mock.patch.object(canvas.socket, 'getaddrinfo', side_effect=slow):
            t = time.monotonic()
            self.assertTrue(canvas._host_blocked('slow.example'))
            self.assertLess(time.monotonic() - t, 0.8)


class GuardProxy(unittest.TestCase):
    """The SOCKS5 proxy board renders use: one lookup per connection, private answers refused."""

    def socks(self, host, port):
        import socket
        c = socket.create_connection(('127.0.0.1', canvas._guard_proxy_port()), timeout=5)
        self.addCleanup(c.close)
        c.sendall(b'\x05\x01\x00')
        self.assertEqual(c.recv(2), b'\x05\x00')
        name = host.encode()
        c.sendall(b'\x05\x01\x00\x03' + bytes([len(name)]) + name + port.to_bytes(2, 'big'))
        return c, c.recv(10)[1]

    def test_names_are_resolved_once_and_private_answers_refused(self):
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Secret)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        port = srv.server_address[1]
        _Secret.hits = []
        real = canvas.socket.getaddrinfo
        calls = []

        def gai(host, *a, **kw):
            calls.append(host)
            if host == 'rebind.test':   # the name now points inward
                return real('127.0.0.1', *a, **kw)
            return real(host, *a, **kw)
        with mock.patch.object(canvas.socket, 'getaddrinfo', gai):
            for host in ('rebind.test', 'localhost', '127.0.0.1', 'app.localhost'):
                calls.clear()
                c, code = self.socks(host, port)
                self.assertEqual(code, 2, host)   # not allowed by ruleset
                self.assertLessEqual(calls.count(host), 1, host)   # one lookup, never a second
        # An allowed literal connects to exactly that address
        with mock.patch.object(canvas, '_host_blocked', lambda h: h != '127.0.0.1'):
            c, code = self.socks('127.0.0.1', port)
            self.assertEqual(code, 0)
            c.sendall(b'GET /via-proxy HTTP/1.0\r\nHost: x\r\n\r\n')
            self.assertIn(b'200', c.recv(100))
        self.assertEqual(_Secret.hits, ['/via-proxy'])

    def test_render_args_route_through_the_proxy(self):
        args = canvas._cdp_launch_args('/p', pipe=True, proxy_port=1234)
        self.assertIn('--proxy-server=socks5://127.0.0.1:1234', args)
        self.assertIn('--proxy-bypass-list=<-loopback>', args)
        self.assertEqual(args[-1], 'about:blank')
        self.assertFalse(any('proxy' in a for a in canvas._cdp_launch_args('/p', pipe=True)))


if __name__ == '__main__':
    unittest.main()
