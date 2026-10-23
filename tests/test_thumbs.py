"""Board thumbnails for the viewer's low-zoom level of detail: route, auth, cache key, queue."""
import os
import pathlib
import threading
import time
import unittest
from unittest import mock

from helpers import ServerCase, TempHomeCase, canvas

PNG = b'\x89PNG\r\n\x1a\nfake'


class FakeQueue:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def request(self, *args, **kw):
        self.calls.append((args, kw))
        return self.ok


class ThumbRoute(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        self.queue = FakeQueue()
        patcher = mock.patch.object(canvas, '_THUMBS', self.queue)
        patcher.start()
        self.addCleanup(patcher.stop)

    def serve(self, **kw):
        attrs = dict(design_dir=self.design, share_token='', share_edit=True, read_only=False)
        attrs.update(kw)
        self.start_server(canvas.CanvasHandler, **attrs)

    def target(self, name='A01-One.html'):
        return canvas._thumb_target(self.idea, name)

    def test_missing_thumbnail_is_queued_then_served_with_etag(self):
        self.serve()
        status, _, body = self.request('GET', '/demo/thumbs/A01-One.png')
        self.assertEqual(status, 202)
        (url, w, h, out, key, fname), = [c[0] for c in self.queue.calls]
        self.assertEqual((url, w, h, key, fname),
                         (pathlib.Path(self.idea, 'boards', 'A01-One.html').as_uri(), 390, 844, 'demo', 'A01-One.html'))
        # file:// requests are allowed only inside the idea folder (see test_file_access)
        self.assertEqual(self.queue.calls[0][1], {'file_roots': [self.idea], 'scale': canvas.THUMB_SCALE})
        self.assertEqual(os.path.dirname(out), os.path.join(self.idea, 'render', '.thumbs'))
        self.assertRegex(os.path.basename(out), r'^A01-One-390x844-3-8-[0-9a-f]+-[0-9a-f]+\.png$')
        os.makedirs(os.path.dirname(out))
        with open(out, 'wb') as f:
            f.write(PNG)
        status, headers, body = self.request('GET', '/demo/thumbs/A01-One.png?v=1.2')
        self.assertEqual((status, body), (200, PNG))
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Cache-Control'], 'no-cache')
        status, _, body = self.request('GET', '/demo/thumbs/A01-One.png', headers={'If-None-Match': headers['ETag']})
        self.assertEqual((status, body), (304, b''))
        self.assertEqual(len(self.queue.calls), 1)

    def test_scale_from_the_query_is_in_the_key(self):
        self.serve()
        for q, scale in (('?s=0.4', 0.4), ('?v=3.1&s=1', 1.0), ('?s=0.8', 0.8), ('?s=7', 0.8), ('?s=0.45', 0.8), ('', 0.8)):
            self.queue.calls.clear()
            self.assertEqual(self.request('GET', '/demo/thumbs/A01-One.png' + q)[0], 202)
            (args, kw), = self.queue.calls
            self.assertEqual(kw['scale'], scale, q)
            self.assertEqual(args[3], canvas._thumb_target(self.idea, 'A01-One.html', scale)[3])
        self.assertNotEqual(canvas._thumb_target(self.idea, 'A01-One.html', 0.4)[3],
                            canvas._thumb_target(self.idea, 'A01-One.html', 0.8)[3])

    def test_key_follows_board_tokens_and_size(self):
        first = self.target()[3]
        board = os.path.join(self.idea, 'boards', 'A01-One.html')
        st = os.stat(board)
        os.utime(board, ns=(st.st_atime_ns, st.st_mtime_ns + 1000))
        second = self.target()[3]
        self.assertNotEqual(first, second)
        tok = os.path.join(self.idea, 'shared', 'tokens.css')
        st = os.stat(tok)
        os.utime(tok, ns=(st.st_atime_ns, st.st_mtime_ns + 1000))
        third = self.target()[3]
        self.assertNotEqual(second, third)
        cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(cj)
        data['boards']['A01-One.html']['h'] = 900
        self.write_json(cj, data)
        self.assertIn('-390x900-', self.target()[3])

    def test_only_registered_boards_inside_the_idea(self):
        self.serve()
        with open(os.path.join(self.idea, 'boards', 'Z99-Loose.html'), 'w') as f:
            f.write('<p>not registered</p>')
        for path in ('/demo/thumbs/Z99-Loose.png', '/demo/thumbs/A01-One.html', '/demo/thumbs/A01-One',
                     '/demo/thumbs/..%2Fcanvas.png', '/demo/thumbs/%2e%2e%2F%2e%2e%2Fsecret.png',
                     '/nope/thumbs/A01-One.png', '/demo/thumbs/x/A01-One.png'):
            self.assertEqual(self.request('GET', path)[0], 404, path)
        self.assertEqual(self.queue.calls, [])
        self.assertIsNone(canvas._thumb_target(self.idea, '../canvas.json'))

    def test_failed_thumbnail_is_404(self):
        self.queue.ok = False
        self.serve()
        self.assertEqual(self.request('GET', '/demo/thumbs/A01-One.png')[0], 404)

    def test_share_mode_needs_the_token_and_read_only_can_read(self):
        token = 'tok_ABCdef123456'
        self.serve(share_token=token, share_edit=False)
        self.assertEqual(self.request('GET', '/demo/thumbs/A01-One.png')[0], 401)
        cookie = {'Cookie': 'canvas_token=' + token}
        self.assertEqual(self.request('GET', '/demo/thumbs/A01-One.png', headers=cookie)[0], 202)
        h = canvas.CanvasHandler.__new__(canvas.CanvasHandler)
        h.share_token = token
        key = h._asset_key(['demo'])
        # The keyed asset prefix for sandboxed boards does not reach thumbnails
        self.assertEqual(self.request('GET', f'/_k/{key}/demo/thumbs/A01-One.png')[0], 404)
        status, _, _ = self.request('GET', '/demo/thumbs/A01-One.png',
                                    headers=dict(cookie, Host='evil.example:%d' % self.port))
        self.assertEqual(status, 421)

    def test_registry_route_uses_project_key(self):
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        self.assertEqual(self.request('GET', '/p/demo/thumbs/A02-Two.png')[0], 202)
        self.assertEqual(self.queue.calls[0][0][4:], ('p/demo', 'A02-Two.html'))
        self.assertEqual(self.request('GET', '/p/demo/thumbs/..%2F..%2Fx.png')[0], 404)


class FakeSession:
    instances = []

    def __init__(self, *a, **kw):
        self.closed = False
        self.captured = []
        FakeSession.instances.append(self)

    def capture(self, url, w, h, wait_ms, out, full_page=False, timeout=60, scale=1, file_roots=()):
        self.captured.append((url, w, h, scale))
        if 'Broken' in url:
            raise canvas.CdpError('boom')
        with open(out, 'wb') as f:
            f.write(PNG)

    def close(self):
        self.closed = True


class ThumbQueue(TempHomeCase):
    def setUp(self):
        super().setUp()
        FakeSession.instances = []
        self.idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo',
                                   boards=('A01-One.html', 'A01-One-Two.html', 'B02-Broken.html'))
        self.events = []
        self.done = threading.Event()

        def broadcast(key, data):
            self.events.append((key, data))
            self.done.set()
        for target, value in (('_CdpSession', FakeSession), ('_broadcast', broadcast), ('THUMB_IDLE_SECS', 0.2)):
            p = mock.patch.object(canvas, target, value)
            p.start()
            self.addCleanup(p.stop)
        self.q = canvas._ThumbQueue(workers=2)
        self.addCleanup(self.q.close_all)

    def wait_until(self, cond, secs=5):
        end = time.monotonic() + secs
        while not cond() and time.monotonic() < end:
            time.sleep(0.02)
        self.assertTrue(cond())

    def test_renders_once_broadcasts_and_drops_stale_versions(self):
        src, w, h, out = canvas._thumb_target(self.idea, 'A01-One.html')
        folder = os.path.dirname(out)
        os.makedirs(folder)
        for stale in ('A01-One-390x844-1-2.png', 'A01-One-200x100-ab.png', 'A01-One-390x844-3-8-1-2.png'):
            open(os.path.join(folder, stale), 'wb').close()
        keep = os.path.join(folder, 'A01-One-Two-390x844-1-2.png')   # another board with a longer id
        open(keep, 'wb').close()
        other_scale = os.path.join(folder, 'A01-One-390x844-3-4-1-2.png')   # a 1x viewer's thumbnail
        open(other_scale, 'wb').close()
        self.assertTrue(self.q.request(src, w, h, out, 'demo', 'A01-One.html'))
        self.assertTrue(self.q.request(src, w, h, out, 'demo', 'A01-One.html'))   # deduped while queued
        self.assertTrue(self.done.wait(5))
        self.assertEqual(self.events, [('demo', {'type': 'thumb', 'file': 'A01-One.html'})])
        self.assertEqual(sorted(os.listdir(folder)),
                         sorted([os.path.basename(out), os.path.basename(keep), os.path.basename(other_scale)]))
        captured = [c for s in FakeSession.instances for c in s.captured]
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], src)   # the URL the caller passed in
        self.assertEqual(captured[0][1:], (390, 844, canvas.THUMB_SCALE))
        # idle workers stop and close their Chrome
        self.wait_until(lambda: all(s.closed for s in FakeSession.instances) and self.q.started == 0)

    def test_failure_is_not_retried(self):
        src, w, h, out = canvas._thumb_target(self.idea, 'B02-Broken.html')
        with mock.patch('sys.stderr'):
            self.assertTrue(self.q.request(src, w, h, out, 'demo', 'B02-Broken.html'))
            self.wait_until(lambda: out in self.q.failed)
        self.assertFalse(self.q.request(src, w, h, out, 'demo', 'B02-Broken.html'))
        self.assertEqual(self.events, [])
        self.assertFalse(os.path.exists(out))
        self.wait_until(lambda: self.q.started == 0)
        self.assertTrue(all(s.closed for s in FakeSession.instances))

    def test_a_moved_idea_folder_is_not_recreated(self):
        src, w, h, out = canvas._thumb_target(self.idea, 'A01-One.html')
        moved = self.idea + '-moved'
        os.rename(self.idea, moved)   # the folder moves while the job waits in the queue
        self.assertTrue(self.q.request(src, w, h, out, 'demo', 'A01-One.html'))
        self.wait_until(lambda: out in self.q.failed)
        self.assertFalse(os.path.exists(self.idea))
        self.assertEqual([c for s in FakeSession.instances for c in s.captured], [])
        self.assertEqual(self.events, [])

    def test_at_most_two_workers(self):
        gate = threading.Event()
        orig = FakeSession.capture

        def slow(self_, *a, **kw):
            gate.wait(5)
            return orig(self_, *a, **kw)
        with mock.patch.object(FakeSession, 'capture', slow):
            for name in ('A01-One.html', 'A01-One-Two.html'):
                t = canvas._thumb_target(self.idea, name)
                self.q.request(*t, 'demo', name)
            for i in range(5):
                self.q.request(t[0], 390, 844, t[3] + f'.{i}.png', 'demo', 'A01-One-Two.html')
            time.sleep(0.2)
            self.assertLessEqual(self.q.started, 2)
            self.assertLessEqual(len(FakeSession.instances), 2)
            gate.set()
            self.wait_until(lambda: not self.q.pending)

    def test_most_recent_request_renders_first(self):
        gate, started = threading.Event(), threading.Event()
        orig = FakeSession.capture

        def slow(self_, url, *a, **kw):
            if not started.is_set():
                started.set()
                gate.wait(5)
            return orig(self_, url, *a, **kw)
        q = canvas._ThumbQueue(workers=1)
        self.addCleanup(q.close_all)
        t = canvas._thumb_target(self.idea, 'A01-One.html')
        with mock.patch.object(FakeSession, 'capture', slow):
            q.request(t[0], 390, 844, t[3] + '.busy.png', 'demo', 'A01-One.html')
            self.assertTrue(started.wait(5))
            for i in range(3):
                q.request(t[0], 390, 844, t[3] + f'.{i}.png', 'demo', f'A0{i}.html')
            q.request(t[0], 390, 844, t[3] + '.0.png', 'demo', 'A00.html')   # asked again: to the front
            gate.set()
            self.wait_until(lambda: not q.pending)
        order = [d['file'] for _, d in self.events]
        self.assertEqual(order, ['A01-One.html', 'A00.html', 'A02.html', 'A01.html'])

    def test_one_worker_by_default_with_a_background_chrome(self):
        self.assertEqual(canvas._ThumbQueue().workers, 1)
        t = canvas._thumb_target(self.idea, 'A01-One.html')
        with mock.patch.object(canvas, '_CdpSession', mock.MagicMock(wraps=FakeSession)) as cls:
            self.q.request(*t, 'demo', 'A01-One.html')
            self.wait_until(lambda: not self.q.pending)
        cls.assert_called_once_with(background=True, block_private=True)
        with mock.patch.object(canvas, '_get_chrome', return_value='chrome'):
            fg = canvas._cdp_launch_args('/p')
            bg = canvas._cdp_launch_args('/p', background=True)
        self.assertNotIn('--disable-gpu', fg)
        self.assertEqual(fg[0], 'chrome')
        self.assertIn('--disable-gpu', bg)
        self.assertIn('--renderer-process-limit=1', bg)
        if bg[0] != 'chrome':
            self.assertEqual(bg[1:4], ['-n', '10', 'chrome'])

    def test_close_all_kills_sessions_and_stops_for_good(self):
        s = FakeSession()
        self.q.sessions.append(s)
        gate = threading.Event()
        orig = FakeSession.capture

        def slow(self_, *a, **kw):
            gate.wait(5)
            return orig(self_, *a, **kw)
        with mock.patch.object(FakeSession, 'capture', slow):
            t = canvas._thumb_target(self.idea, 'A01-One.html')
            self.q.request(*t, 'demo', 'A01-One.html')
            self.q.request(t[0], 390, 844, t[3] + '.2.png', 'demo', 'A01-One.html')
            self.wait_until(lambda: len(FakeSession.instances) == 3)   # mine + two workers
            self.q.close_all()
            gate.set()
            self.wait_until(lambda: self.q.started == 0)
        self.assertTrue(all(x.closed for x in FakeSession.instances))
        self.assertEqual((self.q.sessions, self.q.jobs), ([], []))
        self.assertFalse(self.q.request(*t, 'demo', 'A01-One.html'))   # no new work after close
        self.assertEqual(len(FakeSession.instances), 3)


if __name__ == '__main__':
    unittest.main()
