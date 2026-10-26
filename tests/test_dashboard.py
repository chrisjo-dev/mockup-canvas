"""Dashboard index page and API: counts, missing roots, share mode, escaping, CSP, reveal, roots check."""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unittest
from unittest import mock

from helpers import CANVAS_PY, ServerCase, canvas, free_port


class IndexBase(ServerCase):
    def setUp(self):
        super().setUp()
        self.d_a = os.path.join(self.home, 'work', 'alpha', 'design')
        self.idea = self.make_idea(self.d_a, 'ideaA', boards=('A01-One.html', 'A02-Two.html', 'A03-Three.html', 'A04-Four.html'))
        cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(cj)
        b = data['boards']
        b['A01-One.html'].update(status='approved', impl={'route': '/', 'files': ['a.tsx']})
        b['A02-Two.html'].update(status='approved', note='Onboarding flow')
        b['A03-Three.html'].update(status='rejected', comments=[{'text': 'x'}, {'text': 'y'}])
        # A04 has no status: it needs a decision
        self.write_json(cj, data)
        self.old = time.time() - 3600
        os.utime(os.path.join(self.idea, 'boards', 'A04-Four.html'), (self.old, self.old))
        self.gone = os.path.join(self.home, 'work', 'gone', 'design')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {'roots': [{'name': 'alpha', 'path': self.d_a},
                                                    {'name': 'gone', 'path': self.gone}]})

    def index(self, headers=None):
        status, hdrs, body = self.request('GET', '/api/index', headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(hdrs.get('Cache-Control'), 'no-store')
        return json.loads(body)


class RegistryIndex(IndexBase):
    def setUp(self):
        super().setUp()
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)

    def test_counts_and_board_fields(self):
        d = self.index()
        self.assertEqual(d['mode'], 'registry')
        self.assertFalse(d['share'])
        alpha = next(p for p in d['projects'] if p['name'] == 'alpha')
        self.assertEqual((alpha['ideas'], alpha['boards'], alpha['missing']), (1, 4, False))
        self.assertEqual(alpha['path'], '~/work/alpha/design')
        (idea,) = d['ideas']
        self.assertEqual((idea['project'], idea['name'], idea['url']), ('alpha', 'ideaA', '/alpha/ideaA/'))
        boards = {b['f']: b for b in idea['boards']}
        self.assertEqual([boards[f]['s'] for f in sorted(boards)], ['approved', 'approved', 'rejected', 'draft'])
        self.assertEqual(boards['A01-One.html']['b'], 1)
        self.assertEqual(boards['A02-Two.html']['b'], 0)
        self.assertEqual(boards['A03-Three.html']['c'], 2)
        self.assertEqual(boards['A02-Two.html']['n'], 'Onboarding flow')
        self.assertEqual((boards['A01-One.html']['w'], boards['A01-One.html']['h']), (390, 844))
        self.assertAlmostEqual(boards['A04-Four.html']['m'], self.old, delta=1)
        # last edit: the newest of canvas.json and the board files
        self.assertGreater(idea['mtime'], self.old + 60)

    def test_missing_root_is_listed_without_ideas(self):
        gone = next(p for p in self.index()['projects'] if p['name'] == 'gone')
        self.assertEqual((gone['missing'], gone['ideas'], gone['boards']), (True, 0, 0))

    def test_index_follows_canvas_json_edits(self):
        cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(cj)
        data['boards']['A04-Four.html']['status'] = 'approved'
        self.write_json(cj, data)
        st = os.stat(cj)
        os.utime(cj, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))   # a new mtime even on a coarse clock
        boards = {b['f']: b for b in self.index()['ideas'][0]['boards']}
        self.assertEqual(boards['A04-Four.html']['s'], 'approved')

    def test_page_inlines_the_index_and_runs_scripts_by_hash(self):
        status, hdrs, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        html = body.decode()
        csp = hdrs['Content-Security-Policy']
        self.assertNotIn('unsafe-inline', csp.split('script-src', 1)[1].split(';')[0])
        scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
        self.assertGreaterEqual(len(scripts), 3)   # fonts and theme, core, management
        for sc in scripts:
            digest = base64.b64encode(hashlib.sha256(sc.encode()).digest()).decode()
            self.assertIn(f"'sha256-{digest}'", csp)
        self.assertEqual(len(re.findall(r"'sha256-", csp)), len(scripts))
        # the index is data, not script: the CSP does not allow it to run
        boot = re.search(r'<script type="application/json" id="boot">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn('MC_BOOT', html)
        data = json.loads(boot)
        self.assertEqual(data['ideas'][0]['name'], 'ideaA')
        self.assertIn('window.MC_MANAGE =', html)
        self.assertEqual(hdrs.get('X-Content-Type-Options'), 'nosniff')

    def test_head_matches_get(self):
        g = self.request('GET', '/')
        hd = self.request('HEAD', '/')
        self.assertEqual(hd[2], b'')
        for k in ('Content-Length', 'Content-Security-Policy'):
            self.assertEqual(hd[1].get(k), g[1].get(k), k)

    def test_names_are_escaped_in_the_page(self):
        evil = '<script>alert(1)<img src=x onerror=alert(1)>'   # folder names cannot hold a /
        self.make_idea(self.d_a, evil)
        html = self.request('GET', '/')[2].decode()
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>alert', html)
        self.assertIn('\\u003cscript>alert(1)\\u003cimg src=x onerror=alert(1)>', html)
        # the page renders names with textContent only
        dash = open(canvas.DASHBOARD_PATH, encoding='utf-8').read()
        manage = open(canvas.DASHBOARD_MANAGE_PATH, encoding='utf-8').read()
        for src in (dash, manage):
            self.assertNotIn('innerHTML', src)
            self.assertNotIn('insertAdjacentHTML', src)
            self.assertNotIn('document.write', src)

    def test_index_events_stream_answers_head(self):
        status, hdrs, body = self.request('HEAD', '/api/events')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(hdrs['Content-Type'], 'text/event-stream')

    def test_broadcast_reaches_the_dashboard_stream(self):
        class W:
            def __init__(self):
                self.data = b''
            def write(self, b):
                self.data += b
            def flush(self):
                pass
        w = W()
        self.assertTrue(canvas._add_sse(canvas.DASH_SSE_KEY, w))
        self.addCleanup(canvas._rm_sse, canvas.DASH_SSE_KEY, w)
        canvas._broadcast('alpha/ideaA', {'type': 'thumb', 'file': 'A01-One.html'})
        msg = json.loads(w.data.decode().split('data: ', 1)[1])
        self.assertEqual(msg, {'type': 'thumb', 'file': 'A01-One.html', 'key': 'alpha/ideaA'})

    # ── reveal ──
    def test_reveal_needs_same_origin(self):
        with mock.patch.object(canvas, '_reveal_path') as rv:
            body = {'project': 'alpha', 'idea': 'ideaA'}
            self.assertEqual(self.request('POST', '/api/reveal', body)[0], 403)
            self.assertEqual(self.request('POST', '/api/reveal', body, headers={'Origin': 'http://evil.example'})[0], 403)
            self.assertEqual(self.request('POST', '/api/reveal', body,
                                          headers={'Origin': 'http://127.0.0.1:4400', 'Host': f'evil.example:{self.port}'})[0], 421)
            rv.assert_not_called()

    def test_reveal_opens_registered_folders_only(self):
        with mock.patch.object(canvas, '_reveal_path') as rv:
            st, _, _ = self.request('POST', '/api/reveal', {'project': 'alpha', 'idea': 'ideaA'}, headers=self.origin())
            self.assertEqual(st, 200)
            rv.assert_called_once_with(os.path.realpath(self.idea))
            rv.reset_mock()
            st, _, _ = self.request('POST', '/api/reveal', {'project': 'alpha'}, headers=self.origin())
            self.assertEqual(st, 200)
            rv.assert_called_once_with(os.path.realpath(self.d_a))
            rv.reset_mock()
            for body in ({'project': 'alpha', 'idea': '../../..'}, {'project': 'alpha', 'idea': '..'},
                         {'project': 'alpha', 'idea': 'ideaA/../../x'}, {'project': 'nope'}, {'project': 'gone'},
                         {'project': 'alpha', 'idea': 'missing'}, {'path': self.home}):
                self.assertEqual(self.request('POST', '/api/reveal', body, headers=self.origin())[0], 404, body)
            rv.assert_not_called()

    # ── roots API additions ──
    def test_check_suggests_a_design_subfolder(self):
        outer = os.path.join(self.home, 'work', 'beta')
        self.make_idea(os.path.join(outer, 'design'), 'b1', boards=('B01-A.html', 'B02-B.html'))
        st, _, body = self.request('POST', '/api/roots/check', {'path': outer}, headers=self.origin())
        d = json.loads(body)
        self.assertEqual(st, 200)
        self.assertFalse(d['ok'])
        self.assertIn('no subfolder contains canvas.json', d['error'])
        self.assertEqual(d['suggest'], {'path': '~/work/beta/design', 'ideas': 1, 'boards': 2})
        d = json.loads(self.request('POST', '/api/roots/check', {'path': '~/work/beta/design'}, headers=self.origin())[2])
        self.assertEqual((d['ok'], d['name'], d['ideas'], d['boards']), (True, 'beta', 1, 2))
        # check never writes the registry
        self.assertEqual([r['name'] for r in self.read_json(self.roots_json)['roots']], ['alpha', 'gone'])
        self.assertEqual(self.request('POST', '/api/roots/check', {'path': outer})[0], 403)

    def test_add_with_a_missing_projects_name_relocates_it(self):
        moved = os.path.join(self.home, 'work', 'moved', 'design')
        self.make_idea(moved, 'back')
        d = json.loads(self.request('POST', '/api/roots/check', {'path': moved, 'name': 'gone'}, headers=self.origin())[2])
        self.assertTrue(d['ok'] and d['replaces'])
        st, _, _ = self.request('POST', '/api/roots/add', {'path': moved, 'name': 'gone'}, headers=self.origin())
        self.assertEqual(st, 200)
        roots = self.read_json(self.roots_json)['roots']
        self.assertEqual([r['name'] for r in roots], ['alpha', 'gone'])
        self.assertEqual(roots[1]['path'], '~/work/moved/design')
        # a project whose folder is there keeps its name
        st, _, body = self.request('POST', '/api/roots/add', {'path': moved, 'name': 'alpha'}, headers=self.origin())
        self.assertEqual(st, 409)

    def test_rename(self):
        self.assertEqual(self.request('POST', '/api/roots/rename', {'name': 'alpha', 'new_name': 'a2'})[0], 403)
        for body, code in (({'name': 'alpha', 'new_name': 'gone'}, 409), ({'name': 'alpha', 'new_name': 'a/b'}, 400),
                           ({'name': 'alpha', 'new_name': 'api'}, 400), ({'name': 'nope', 'new_name': 'x'}, 404),
                           ({'name': 'alpha'}, 400)):
            self.assertEqual(self.request('POST', '/api/roots/rename', body, headers=self.origin())[0], code, body)
        st, _, _ = self.request('POST', '/api/roots/rename', {'name': 'alpha', 'new_name': 'a2'}, headers=self.origin())
        self.assertEqual(st, 200)
        self.assertEqual(self.read_json(self.roots_json)['roots'][0]['name'], 'a2')
        self.assertEqual(self.request('GET', '/a2/ideaA/')[0], 200)

    def test_thumb_cached_only_never_queues(self):
        with mock.patch.object(canvas._THUMBS, 'request') as req:
            st, _, body = self.request('GET', '/alpha/ideaA/thumbs/A01-One.png?s=0.4&cached=1')
            self.assertEqual((st, body), (204, b''))
            req.assert_not_called()

    def test_thumb_retry_forgets_only_an_old_failure(self):
        target = canvas._thumb_target(self.idea, 'A01-One.html', 0.4)
        out = target[3]
        self.addCleanup(canvas._THUMBS.failed.pop, out, None)
        url = '/alpha/ideaA/thumbs/A01-One.png?s=0.4'
        with mock.patch.object(canvas._THUMBS, 'request', side_effect=lambda *a, **k: out not in canvas._THUMBS.failed) as req:
            canvas._THUMBS.failed[out] = time.time()   # just failed: Retry waits RETRY_AFTER seconds
            self.assertEqual(self.request('GET', url + '&retry=1')[0], 404)
            self.assertIn(out, canvas._THUMBS.failed)
            canvas._THUMBS.failed[out] = time.time() - canvas._THUMBS.RETRY_AFTER - 1
            self.assertEqual(self.request('GET', url)[0], 404)   # no retry asked: still failed
            self.assertEqual(self.request('GET', url + '&retry=1')[0], 202)
            self.assertNotIn(out, canvas._THUMBS.failed)
            self.assertEqual(req.call_count, 3)

    # ── project names ──
    def test_add_and_check_reject_unusable_names(self):
        api = os.path.join(self.home, 'work', 'api', 'design')   # the default name would be "api"
        self.make_idea(api, 'i1')
        for body in ({'path': api}, {'path': api, 'name': 'a/b'}, {'path': api, 'name': 'a\\b'}, {'path': api, 'name': '_k'},
                     {'path': api, 'name': '..'}, {'path': api, 'name': 'x\x01'}, {'path': api, 'name': 'n' * 101}):
            st, _, raw = self.request('POST', '/api/roots/add', body, headers=self.origin())
            self.assertEqual(st, 400, body)
            d = json.loads(self.request('POST', '/api/roots/check', body, headers=self.origin())[2])
            self.assertFalse(d['ok'], body)
            self.assertEqual(json.loads(raw)['error'], d['error'])
        self.assertEqual([r['name'] for r in self.read_json(self.roots_json)['roots']], ['alpha', 'gone'])
        st, _, _ = self.request('POST', '/api/roots/add', {'path': api, 'name': 'apis'}, headers=self.origin())
        self.assertEqual(st, 200)

    def test_rename_uses_the_same_rules(self):
        for bad in ('_k', 'api', '.', 'a\\b', 'tab\there', 'n' * 101):
            st, _, raw = self.request('POST', '/api/roots/rename', {'name': 'alpha', 'new_name': bad}, headers=self.origin())
            self.assertEqual(st, 400, bad)
            self.assertEqual(json.loads(raw)['error'], canvas._validate_project_name(bad))

    def test_cli_roots_add_rejects_unusable_names(self):
        api = os.path.join(self.home, 'work', 'api', 'design')
        self.make_idea(api, 'i1')
        r = self.run_cli('roots', 'add', api)
        self.assertEqual(r.returncode, 2)
        self.assertIn('reserved', r.stderr)
        r = self.run_cli('roots', 'add', api, '--name', 'x/y')
        self.assertEqual(r.returncode, 2)
        r = self.run_cli('roots', 'add', api, '--name', 'apiproj')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('apiproj', [x['name'] for x in self.read_json(self.roots_json)['roots']])

    # ── page cache and live reload stream ──
    def test_page_scripts_are_hashed_once_per_file_version(self):
        a = canvas._dashboard_page(True)
        b = canvas._dashboard_page(True)
        self.assertIs(a[0], b[0])
        self.assertNotEqual(canvas._dashboard_page(False)[1], a[1])   # without the management script

    def test_a_stalled_live_reload_client_is_dropped(self):
        import socket
        s = socket.create_connection(('127.0.0.1', self.port))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        self.addCleanup(s.close)
        s.sendall(f'GET /api/events HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n\r\n'.encode())
        deadline = time.time() + 5
        while not canvas._sse_clients.get(canvas.DASH_SSE_KEY) and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(canvas._sse_clients.get(canvas.DASH_SSE_KEY))
        big = {'type': 'board', 'file': 'x' * 200_000}
        t = time.time()
        for _ in range(200):   # the client never reads: its socket buffers fill, then a write times out
            canvas._broadcast('alpha/ideaA', big)
            if not canvas._sse_clients.get(canvas.DASH_SSE_KEY):
                break
        self.assertFalse(canvas._sse_clients.get(canvas.DASH_SSE_KEY))
        self.assertLess(time.time() - t, canvas.SSE_SEND_TIMEOUT * 3)


class RevealCommand(unittest.TestCase):
    def run_reveal(self, platform, osname, path):
        with mock.patch.object(canvas.sys, 'platform', platform), mock.patch.object(canvas.os, 'name', osname), \
                mock.patch.object(canvas.subprocess, 'Popen') as po:
            canvas._reveal_path(path)
        return po.call_args[0][0]

    def test_each_platform(self):
        self.assertEqual(self.run_reveal('darwin', 'posix', '/Users/a/x,y'), ['open', '-R', '/Users/a/x,y'])
        # Explorer splits /select at commas: one command line with the path in quotes
        self.assertEqual(self.run_reveal('win32', 'nt', r'C:\a,b\c d'), r'explorer /select,"C:\a,b\c d"')
        self.assertEqual(self.run_reveal('linux', 'posix', '/home/a/p/idea'), ['xdg-open', '/home/a/p'])
        with self.assertRaises(OSError):
            self.run_reveal('win32', 'nt', 'C:\\a"b')


class ShareIndex(IndexBase):
    def setUp(self):
        super().setUp()
        self.token = 'tok_dash_1'
        self.cookie = {'Cookie': 'canvas_token=' + self.token}
        self.start_server(canvas.RegistryHandler, share_token=self.token, share_edit=False, read_only=False,
                          share_until=1_900_000_000.0,
                          frozen_roots=[{'name': 'alpha', 'path': self.d_a}, {'name': 'gone', 'path': self.gone}])

    def test_index_needs_the_token(self):
        self.assertEqual(self.request('GET', '/api/index')[0], 401)
        self.assertEqual(self.request('GET', '/api/events')[0], 401)

    def test_share_index_hides_paths_missing_roots_and_management(self):
        d = self.index(self.cookie)
        self.assertTrue(d['share'] and d['readOnly'])
        self.assertEqual(d['closesAt'], 1_900_000_000)
        self.assertEqual([p['name'] for p in d['projects']], ['alpha'])
        self.assertNotIn('path', d['projects'][0])
        raw = self.request('GET', '/api/index', headers=self.cookie)[2].decode()
        page = self.request('GET', '/', headers=self.cookie)[2].decode()
        for text in (raw, page):
            self.assertNotIn(self.home, text)
            self.assertNotIn('~/work', text)
            self.assertNotIn('gone', text)
        for hidden in ('window.MC_MANAGE =', '/api/roots', '/api/reveal', 'Add project', 'Find in folders', 'Reveal in Finder'):
            self.assertNotIn(hidden, page, hidden)

    def test_share_cannot_retry_failed_renders(self):
        target = canvas._thumb_target(self.idea, 'A01-One.html', 0.4)
        canvas._THUMBS.failed[target[3]] = time.time() - 3600
        self.addCleanup(canvas._THUMBS.failed.pop, target[3], None)
        with mock.patch.object(canvas._THUMBS, 'request', return_value=False) as req:
            st, _, _ = self.request('GET', '/alpha/ideaA/thumbs/A01-One.png?s=0.4&retry=1', headers=self.cookie)
        self.assertEqual(st, 404)
        self.assertIn(target[3], canvas._THUMBS.failed)

    def test_share_refuses_reveal_and_roots(self):
        with mock.patch.object(canvas, '_reveal_path') as rv:
            hdrs = dict(self.cookie, **self.origin())
            self.assertEqual(self.request('POST', '/api/reveal', {'project': 'alpha'}, headers=hdrs)[0], 403)
            for a in ('check', 'rename', 'add', 'remove'):
                self.assertEqual(self.request('POST', '/api/roots/' + a, {'path': self.d_a, 'name': 'alpha'}, headers=hdrs)[0], 403, a)
            rv.assert_not_called()


class EditableShareIndex(IndexBase):
    def test_editable_share_still_refuses_reveal(self):
        token = 'tok_dash_2'
        self.start_server(canvas.RegistryHandler, share_token=token, share_edit=True, read_only=False,
                          frozen_roots=[{'name': 'alpha', 'path': self.d_a}])
        hdrs = dict({'Cookie': 'canvas_token=' + token}, **self.origin())
        with mock.patch.object(canvas, '_reveal_path') as rv:
            self.assertEqual(self.request('POST', '/api/reveal', {'project': 'alpha'}, headers=hdrs)[0], 403)
            rv.assert_not_called()
        page = self.request('GET', '/', headers=hdrs)[2].decode()
        self.assertNotIn('window.MC_MANAGE =', page)


class SingleRootIndex(IndexBase):
    def setUp(self):
        super().setUp()
        self.start_server(canvas.CanvasHandler, design_dir=self.d_a, share_token='', share_edit=True, read_only=False)

    def test_single_root_index_and_reveal(self):
        d = self.index()
        self.assertEqual(d['mode'], 'single')
        self.assertEqual([(p['name'], p['ideas']) for p in d['projects']], [('alpha', 1)])
        self.assertEqual(d['ideas'][0]['url'], '/ideaA/')
        self.assertEqual(self.request('GET', '/')[0], 200)
        with mock.patch.object(canvas, '_reveal_path') as rv:
            self.assertEqual(self.request('POST', '/api/reveal', {'idea': 'ideaA'})[0], 403)
            self.assertEqual(self.request('POST', '/api/reveal', {'idea': 'ideaA'}, headers=self.origin())[0], 200)
            rv.assert_called_once_with(os.path.realpath(self.idea))
            self.assertEqual(self.request('POST', '/api/reveal', {'idea': '../..'}, headers=self.origin())[0], 404)


class EmptyRegistryServe(IndexBase):
    def test_serve_starts_with_no_projects(self):
        self.write_json(self.roots_json, {'roots': []})
        port = free_port()
        proc = subprocess.Popen([sys.executable, CANVAS_PY, 'serve', '--port', str(port)], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (proc.poll() is None and proc.kill(), proc.wait(5),
                                 proc.stdout.close(), proc.stderr.close()))
        self.assertIn(f'Server started (registry mode): http://127.0.0.1:{port}/', proc.stdout.readline())
        self.port = port
        deadline = time.time() + 5
        while True:
            try:
                d = json.loads(self.request('GET', '/api/index')[2])
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.1)
        self.assertEqual((d['projects'], d['ideas']), ([], []))
        proc.terminate()
        proc.wait(5)


if __name__ == '__main__':
    unittest.main()
