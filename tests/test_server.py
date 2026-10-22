"""HTTP server: layout API, path traversal, share token, XSS, size limits, roots API, registry."""
import json
import os
import subprocess
import sys
import time
import unittest
from unittest import mock

from helpers import CANVAS_PY, ServerCase, canvas, free_port


class SingleRoot(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'),
                                   links=[{'from': 'A01-One.html', 'to': 'A02-Two.html'}])
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.secret = os.path.join(self.home, 'secret.txt')
        with open(self.secret, 'w') as f:
            f.write('TOPSECRET')
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token='', share_edit=True, read_only=False)

    def test_serves_index_viewer_and_files(self):
        self.assertEqual(self.request('GET', '/')[0], 200)
        status, headers, body = self.request('GET', '/demo/')
        self.assertEqual(status, 200)
        self.assertIn(b'id="canvas"', body)
        self.assertEqual(self.request('GET', '/demo/canvas.json')[0], 200)
        self.assertEqual(self.request('GET', '/demo/boards/A01-One.html')[0], 200)
        self.assertEqual(self.request('GET', '/demo/shared/tokens.css')[0], 200)

    def test_head_is_get_without_a_body(self):
        for path in ('/', '/demo/', '/demo/canvas.json', '/demo/boards/A01-One.html', '/nope/'):
            g_status, g_headers, g_body = self.request('GET', path)
            h_status, h_headers, h_body = self.request('HEAD', path)
            self.assertEqual(h_status, g_status, path)
            self.assertEqual(h_body, b'', path)
            for k in ('Content-Type', 'Content-Length', 'Content-Security-Policy'):
                self.assertEqual(h_headers.get(k), g_headers.get(k), (path, k))
        # the live reload stream answers at once instead of staying open
        t = time.monotonic()
        status, headers, body = self.request('HEAD', '/demo/api/events')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(headers['Content-Type'], 'text/event-stream')
        self.assertLess(time.monotonic() - t, 5)
        status, _, body = self.request('HEAD', '/demo/', headers={'Host': 'evil.example'})
        self.assertEqual((status, body), (421, b''))
        # the connection still works for a GET afterwards
        self.assertIn(b'id="canvas"', self.request('GET', '/demo/')[2])

    def test_layout_post_merges_and_writes_atomically(self):
        data = self.read_json(self.cj)
        data['boards']['A01-One.html'].update(status='approved', note='keep me')
        data['artifact_url'] = 'https://example.com/x'
        self.write_json(self.cj, data)
        real_replace = os.replace
        calls = []

        def spy(src, dst):
            calls.append((src, dst))
            return real_replace(src, dst)
        with mock.patch.object(canvas.os, 'replace', side_effect=spy):
            status, _, body = self.request('POST', '/demo/api/layout',
                                           {'board': 'A01-One.html', 'x': 11, 'y': 22}, headers=self.origin())
        self.assertEqual(status, 200, body)
        after = self.read_json(self.cj)
        b = after['boards']['A01-One.html']
        self.assertEqual((b['x'], b['y'], b['status'], b['note']), (11, 22, 'approved', 'keep me'))
        self.assertEqual(after['artifact_url'], 'https://example.com/x')
        self.assertEqual(after['links'], data['links'])
        self.assertEqual(after['boards']['A02-Two.html'], data['boards']['A02-Two.html'])
        self.assertEqual(calls, [(self.cj + '.tmp', self.cj)])
        self.assertFalse(os.path.exists(self.cj + '.tmp'))

    def test_layout_post_unknown_board_and_bad_body(self):
        before = self.read_json(self.cj)
        status, _, _ = self.request('POST', '/demo/api/layout', {'board': 'Nope.html', 'x': 1, 'y': 2},
                                    headers=self.origin())
        self.assertEqual(status, 200)
        self.assertEqual(self.read_json(self.cj), before)
        status, _, _ = self.request('POST', '/demo/api/layout', {'board': 'A01-One.html', 'x': 'a', 'y': 2},
                                    headers=self.origin())
        self.assertEqual(status, 400)
        status, _, _ = self.request('POST', '/demo/api/layout', raw_body=b'not json',
                                    headers=dict(self.origin(), **{'Content-Type': 'application/json'}))
        self.assertEqual(status, 400)

    def test_post_size_limits(self):
        big = b'{"board":"A01-One.html","x":1,"y":2,"pad":"' + b'a' * 70000 + b'"}'
        status, _, _ = self.request('POST', '/demo/api/layout', raw_body=big,
                                    headers=dict(self.origin(), **{'Content-Type': 'application/json'}))
        self.assertEqual(status, 413)
        head = ['POST /demo/api/layout HTTP/1.0', f'Host: 127.0.0.1:{self.port}',
                f'Origin: http://127.0.0.1:{self.port}', 'Content-Type: application/json']
        self.assertEqual(self.raw_request(head), 400)
        self.assertEqual(self.raw_request(head + ['Content-Length: -5']), 400)

    def test_path_traversal(self):
        os.symlink(self.secret, os.path.join(self.idea, 'boards', 'leak.html'))
        os.symlink(self.home, os.path.join(self.design, 'homelink'))
        for path in (
            '/../secret.txt',
            '/demo/boards/../../../secret.txt',
            '/demo/boards/..%2f..%2f..%2fsecret.txt',
            '/%2e%2e/secret.txt',
            '/%2e%2e/canvas.json',
            '/demo/shared/%2e%2e%2f%2e%2e%2f%2e%2e%2fsecret.txt',
            '/demo/boards/%2fetc%2fpasswd',
            '//etc/passwd',
            '/demo/boards/leak.html',
            '/homelink/',
            '/homelink/canvas.json',
        ):
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b'TOPSECRET', body, path)

    def test_index_escapes_idea_names(self):
        evil = '"><img src=x onerror=alert(1)>'
        self.make_idea(self.design, evil)
        _, _, body = self.request('GET', '/')
        html = body.decode()
        self.assertNotIn('<img src=x', html)
        self.assertIn('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;', html)

    def test_root_header_present_in_local_mode(self):
        _, headers, _ = self.request('GET', '/')
        # A short hash of the folder, never the absolute path
        root = headers.get(canvas.HEADER_ROOT)
        self.assertEqual(root, canvas._root_id(self.design))
        self.assertRegex(root, r'^[0-9a-f]{16}$')
        self.assertNotIn(self.home, json.dumps(headers))


class ShareMode(ServerCase):
    TOKEN = 'tok_ABCdef123456'

    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo')
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token=self.TOKEN, share_edit=False, read_only=False)

    def test_head_needs_the_token_too(self):
        status, _, body = self.request('HEAD', '/demo/canvas.json')
        self.assertEqual((status, body), (401, b''))
        status, _, body = self.request('HEAD', '/demo/canvas.json',
                                       headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertEqual((status, body), (200, b''))

    def test_requires_token_and_401_hides_it(self):
        for path in ('/', '/demo/', '/demo/canvas.json'):
            status, headers, body = self.request('GET', path)
            self.assertEqual(status, 401)
            self.assertNotIn(self.TOKEN.encode(), body)
            self.assertNotIn(self.TOKEN, json.dumps(headers))
            self.assertNotIn(canvas.HEADER_ROOT, headers)
        status, _, _ = self.request('GET', '/', headers={'Cookie': 'canvas_token=wrong'})
        self.assertEqual(status, 401)
        status, _, _ = self.request('GET', '/?t=wrong')
        self.assertEqual(status, 401)

    def test_token_sets_strict_cookie_and_redirects(self):
        status, headers, _ = self.request('GET', '/demo/?t=' + self.TOKEN)
        self.assertEqual(status, 302)
        self.assertEqual(headers['Location'], '/demo/')
        self.assertNotIn(self.TOKEN, headers['Location'])
        cookie = headers['Set-Cookie']
        self.assertTrue(cookie.startswith('canvas_token=' + self.TOKEN + ';'))
        for flag in ('HttpOnly', 'SameSite=Strict', 'Path=/', 'Max-Age='):
            self.assertIn(flag, cookie)
        status, _, _ = self.request('GET', '/demo/', headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertEqual(status, 200)

    def test_uses_constant_time_compare(self):
        real = canvas.hmac.compare_digest
        with mock.patch.object(canvas.hmac, 'compare_digest', side_effect=real) as cd:
            self.request('GET', '/', headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertTrue(cd.called)

    def test_read_only_share_refuses_layout(self):
        status, _, _ = self.request('POST', '/demo/api/layout', {'board': 'A01-One.html', 'x': 1, 'y': 1},
                                    headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertEqual(status, 403)


class RegistryBase(ServerCase):
    def setUp(self):
        super().setUp()
        self.d_a = os.path.join(self.home, 'work', 'alpha', 'design')
        self.d_b = os.path.join(self.home, 'work', 'beta', 'design')
        self.make_idea(self.d_a, 'ideaA')
        self.make_idea(self.d_b, 'ideaB')
        with open(os.path.join(self.home, 'secret.txt'), 'w') as f:
            f.write('TOPSECRET')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {'roots': [{'name': 'alpha', 'path': self.d_a},
                                                    {'name': 'beta', 'path': self.d_b}]})



class Registry(RegistryBase):
    def setUp(self):
        super().setUp()
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)

    def test_serves_both_projects(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get(canvas.HEADER_ROOT), canvas.REGISTRY_SENTINEL)
        self.assertIn(b'/alpha/ideaA/', body)
        self.assertIn(b'/beta/ideaB/', body)
        self.assertEqual(self.request('GET', '/alpha/ideaA/')[0], 200)
        self.assertEqual(self.request('GET', '/beta/ideaB/boards/A01-One.html')[0], 200)
        status, _, _ = self.request('POST', '/beta/ideaB/api/layout', {'board': 'A01-One.html', 'x': 5, 'y': 6},
                                    headers=self.origin())
        self.assertEqual(status, 200)
        b = self.read_json(os.path.join(self.d_b, 'ideaB', 'canvas.json'))['boards']['A01-One.html']
        self.assertEqual((b['x'], b['y']), (5, 6))

    def test_multi_root_traversal(self):
        for path in (
            '/alpha/../beta/ideaB/canvas.json',
            '/alpha/%2e%2e/beta/ideaB/',
            '/alpha/ideaB/',
            '/alpha/ideaA/boards/..%2f..%2f..%2f..%2fbeta%2fdesign%2fideaB%2fcanvas.json',
            '/alpha/ideaA/../../../../secret.txt',
            '/alpha/%2e%2e/%2e%2e/%2e%2e/secret.txt',
            '/gamma/ideaA/',
            '/alpha/ideaA/assets/%2fetc%2fpasswd',
        ):
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b'TOPSECRET', body, path)

    def test_index_escapes_project_names(self):
        evil = "x');alert(1);//<script>"
        data = self.read_json(self.roots_json)
        data['roots'].append({'name': evil, 'path': os.path.join(self.home, 'nowhere')})
        self.write_json(self.roots_json, data)
        _, _, body = self.request('GET', '/')
        html = body.decode()
        self.assertNotIn('<script>"', html)
        self.assertNotIn("alert(1);//<script>", html)
        self.assertNotIn("removeProject('", html)
        self.assertIn('data-name="x&#x27;);alert(1);//&lt;script&gt;"', html)

    def test_roots_api_csrf(self):
        body = {'name': 'alpha'}
        self.assertEqual(self.request('POST', '/api/roots/remove', body)[0], 403)
        self.assertEqual(self.request('POST', '/api/roots/remove', body,
                                      headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/roots/remove', body,
                                      headers={'Referer': 'http://evil.example/'})[0], 403)
        self.assertEqual(self.request('POST', '/api/roots/remove', body,
                                      headers={'Origin': f'http://127.0.0.1:{self.port + 1}'})[0], 403)
        self.assertEqual(len(self.read_json(self.roots_json)['roots']), 2)
        status, _, _ = self.request('POST', '/api/roots/remove', body,
                                    headers={'Referer': f'http://localhost:{self.port}/'})
        self.assertEqual(status, 200)
        self.assertEqual([r['name'] for r in self.read_json(self.roots_json)['roots']], ['beta'])

    def test_roots_api_requires_json_and_size_limit(self):
        status, _, _ = self.request('POST', '/api/roots/add', raw_body=b'{}',
                                    headers=dict(self.origin(), **{'Content-Type': 'text/plain'}))
        self.assertEqual(status, 400)
        big = json.dumps({'path': 'a' * 70000}).encode()
        status, _, _ = self.request('POST', '/api/roots/add', raw_body=big,
                                    headers=dict(self.origin(), **{'Content-Type': 'application/json'}))
        self.assertEqual(status, 413)

    def test_roots_add_validation(self):
        ssh = os.path.join(self.home, '.ssh')
        self.make_idea(ssh, 'x')
        empty = os.path.join(self.home, 'empty', 'design')
        os.makedirs(os.path.join(empty, 'notanidea'))
        outside = os.path.join(self.tmp, 'outside', 'design')
        self.make_idea(outside, 'x')
        cases = {
            '': 'Path is empty',
            self.home: 'home directory itself',
            '~': 'home directory itself',
            ssh: 'System or hidden directories',
            '~/Library': 'System or hidden directories',
            empty: 'Not a mockup-canvas design folder',
            outside: 'outside the home directory',
            '/': 'filesystem root',
            os.path.join(self.home, 'missing'): 'does not exist',
        }
        for path, msg in cases.items():
            status, _, body = self.request('POST', '/api/roots/add', {'path': path}, headers=self.origin())
            self.assertEqual(status, 400, path)
            self.assertIn(msg, json.loads(body)['error'], path)
        self.assertEqual(len(self.read_json(self.roots_json)['roots']), 2)

        good = os.path.join(self.home, 'work', 'gamma', 'design')
        self.make_idea(good, 'g')
        status, _, body = self.request('POST', '/api/roots/add', {'path': good}, headers=self.origin())
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['name'], 'gamma')
        self.assertEqual(self.read_json(self.roots_json)['roots'][-1],
                         {'name': 'gamma', 'path': '~/work/gamma/design'})
        status, _, _ = self.request('POST', '/api/roots/add', {'path': good, 'name': 'other'},
                                    headers=self.origin())
        self.assertEqual(status, 409)

    def test_roots_scan_stays_in_home(self):
        outside = os.path.join(self.tmp, 'outside', 'proj', 'design')
        self.make_idea(outside, 'x')
        status, _, body = self.request('POST', '/api/roots/scan',
                                       {'dirs': [os.path.join(self.tmp, 'outside'), os.path.join(self.home, 'work')]},
                                       headers=self.origin())
        self.assertEqual(status, 200)
        found = json.loads(body)['found']
        self.assertEqual(sorted(f['name'] for f in found), ['alpha', 'beta'])
        self.assertTrue(all(f['already_registered'] for f in found))


class ReadOnlyViewerFlag(ServerCase):
    """Viewer HTML must carry CANVAS_READ_ONLY when the session is share-read-only."""

    TOKEN = 'tok_ro_test_1'

    def setUp(self):
        super().setUp()
        design = os.path.join(self.home, 'p', 'design')
        self.make_idea(design, 'demo')
        # share_edit=False -> read-only share mode
        self.start_server(canvas.CanvasHandler, design_dir=design,
                          share_token=self.TOKEN, share_edit=False, read_only=False)

    def test_viewer_injects_read_only_flag(self):
        status, _, body = self.request('GET', '/demo/',
                                       headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertEqual(status, 200)
        self.assertIn(b'<script>var CANVAS_READ_ONLY=true;</script>', body)

    def test_viewer_no_flag_in_editable_share(self):
        """An editable share must NOT inject the flag."""
        design = os.path.join(self.home, 'q', 'design')
        self.make_idea(design, 'demo2')
        self.start_server(canvas.CanvasHandler, design_dir=design,
                          share_token=self.TOKEN, share_edit=True, read_only=False)
        status, _, body = self.request('GET', '/demo2/',
                                       headers={'Cookie': 'canvas_token=' + self.TOKEN})
        self.assertEqual(status, 200)
        self.assertNotIn(b'<script>var CANVAS_READ_ONLY=true;</script>', body)

    def test_viewer_no_flag_in_local_mode(self):
        """Local (no token) mode must NOT inject the flag."""
        design = os.path.join(self.home, 'r', 'design')
        self.make_idea(design, 'demo3')
        self.start_server(canvas.CanvasHandler, design_dir=design,
                          share_token='', share_edit=True, read_only=False)
        status, _, body = self.request('GET', '/demo3/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'<script>var CANVAS_READ_ONLY=true;</script>', body)


class RegistryShareMode(RegistryBase):
    def test_share_mode_refuses_roots_api(self):
        token = 'tok_registry_1'
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=True, read_only=False)
        headers = dict(self.origin(), Cookie='canvas_token=' + token)
        for action, body in (('add', {'path': self.d_a}), ('remove', {'name': 'alpha'}), ('scan', {'dirs': ['~']})):
            status, _, resp = self.request('POST', '/api/roots/' + action, body, headers=headers)
            self.assertEqual(status, 403, action)
            self.assertIn('share mode', json.loads(resp)['error'])
        self.assertEqual(len(self.read_json(self.roots_json)['roots']), 2)

    def test_registry_viewer_injects_read_only_flag_in_ro_share(self):
        token = 'tok_registry_ro'
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=False, read_only=False)
        status, _, body = self.request('GET', '/alpha/ideaA/',
                                       headers={'Cookie': 'canvas_token=' + token})
        self.assertEqual(status, 200)
        self.assertIn(b'<script>var CANVAS_READ_ONLY=true;</script>', body)


class ServeCommand(RegistryBase):
    """Starts the real CLI server on a random free port and always stops it."""

    def test_registry_share_cli_prints_share_url(self):
        """serve --share in registry mode must print 'Share URL:' and serve the content."""
        port = free_port()
        proc = subprocess.Popen(
            [sys.executable, CANVAS_PY, 'serve', '--port', str(port), '--share'],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(lambda: (proc.poll() is None and proc.kill(),
                                 proc.wait(5), proc.stdout.close(), proc.stderr.close()))
        line = proc.stdout.readline()
        self.assertIn('Share URL:', line)

    def test_registry_serve_cli(self):
        port = free_port()
        proc = subprocess.Popen([sys.executable, CANVAS_PY, 'serve', '--port', str(port)], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (proc.poll() is None and proc.kill(), proc.wait(5),
                                 proc.stdout.close(), proc.stderr.close()))
        line = proc.stdout.readline()
        self.assertIn(f'Server started (registry mode): http://127.0.0.1:{port}/', line)
        self.port = port
        deadline = time.time() + 5
        while True:
            try:
                status, _, body = self.request('GET', '/')
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.1)
        self.assertEqual(status, 200)
        self.assertIn(b'alpha', body)
        self.assertEqual(self.request('GET', '/alpha/ideaA/')[0], 200)
        # A second serve on the same port detects the running registry server and exits
        r = subprocess.run([sys.executable, CANVAS_PY, 'serve', '--port', str(port)], env=self.env,
                           capture_output=True, text=True, timeout=20)
        self.assertIn('Already running (registry mode)', r.stdout)
        proc.terminate()
        proc.wait(5)


if __name__ == '__main__':
    unittest.main()
