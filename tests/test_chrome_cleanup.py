"""Every Chrome canvas.py starts is killed, with its helpers and profile, however the command stops."""
import http.client
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from helpers import CANVAS_PY, TempHomeCase, canvas, free_port

# Never opens DevTools, so canvas.py stays in _CdpSession start until it gives up (20 s).
# Starts a helper process like Chrome's renderer, then logs both pids.
SLOW_CHROME = r"""#!/usr/bin/env python3
import json, os, subprocess, sys, time
profile = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--user-data-dir='))
helper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)', '--type=renderer',
                           '--user-data-dir=' + profile])
with open(os.environ['SLOW_CHROME_LOG'], 'a') as f:
    f.write(json.dumps({'pid': os.getpid(), 'helper': helper.pid, 'pgid': os.getpgid(0),
                        'profile': profile}) + '\n')
time.sleep(120)
"""


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ChromeCleanupOnSignal(TempHomeCase):
    def setUp(self):
        super().setUp()
        fake = os.path.join(self.tmp, 'slow-chrome')
        with open(fake, 'w') as f:
            f.write(SLOW_CHROME.replace('/usr/bin/env python3', sys.executable, 1))
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        self.log = os.path.join(self.tmp, 'chrome.log')
        self.tmpdir = os.path.join(self.tmp, 'tmp')
        os.makedirs(self.tmpdir)
        self.env.update(MOCKUP_CANVAS_CHROME=fake, SLOW_CHROME_LOG=self.log, TMPDIR=self.tmpdir)
        self.pids = []
        self.addCleanup(self.kill_leftovers)

    def kill_leftovers(self):
        for pid in self.pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def wait_for_chrome(self, proc, secs=15):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if os.path.exists(self.log):
                with open(self.log) as f:
                    rows = [json.loads(l) for l in f if l.strip()]
                if rows:
                    self.pids += [rows[0]['pid'], rows[0]['helper']]
                    return rows[0]
            self.assertIsNone(proc.poll(), 'canvas.py exited before Chrome started')
            time.sleep(0.05)
        self.fail('fake Chrome never started')

    def assert_cleaned(self, proc, chrome):
        try:
            # Generous: a healthy exit takes well under a second, but a loaded machine (e.g. the
            # e2e suite running in parallel) once needed more than 15 s. Only a failure waits it out.
            proc.wait(45)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail('canvas.py did not exit')
        end = time.monotonic() + 5
        while (alive(chrome['pid']) or alive(chrome['helper'])) and time.monotonic() < end:
            time.sleep(0.05)
        self.assertFalse(alive(chrome['pid']), 'Chrome left running')
        self.assertFalse(alive(chrome['helper']), 'Chrome helper left running')
        self.assertEqual([n for n in os.listdir(self.tmpdir) if n.startswith('mockup-canvas-chrome-')], [])

    def test_sigterm_to_serve_while_thumbnail_chrome_starts(self):
        design = os.path.join(self.home, 'p', 'design')
        self.make_idea(design, 'demo')
        port = free_port()
        proc = subprocess.Popen([sys.executable, CANVAS_PY, 'serve', design, '--port', str(port)],
                                env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        end = time.monotonic() + 15
        while True:
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('GET', '/demo/thumbs/A01-One.png')
                status = conn.getresponse().status
                conn.close()
                break
            except OSError:
                self.assertLess(time.monotonic(), end, 'server did not start')
                time.sleep(0.1)
        self.assertEqual(status, 202)
        chrome = self.wait_for_chrome(proc)
        self.assertEqual(chrome['pgid'], chrome['pid'], 'Chrome not in its own process group')
        self.assertTrue(alive(chrome['helper']))
        proc.send_signal(signal.SIGTERM)
        self.assert_cleaned(proc, chrome)

    def test_signals_to_snap_while_chrome_starts(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(sig=sig):
                if os.path.exists(self.log):
                    os.remove(self.log)
                proc = subprocess.Popen([sys.executable, CANVAS_PY, 'snap', 'http://127.0.0.1:5999/',
                                         '--out', os.path.join(self.tmp, 'x.png')],
                                        env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.addCleanup(lambda p=proc: p.poll() is None and p.kill())
                chrome = self.wait_for_chrome(proc)
                proc.send_signal(sig)
                self.assert_cleaned(proc, chrome)


def processes_using(prefix):
    """-> [(pid, command)] of processes whose command line mentions prefix."""
    return [(pid, cmd) for pid, cmd in canvas._ps_commands() or () if prefix in cmd]


@unittest.skipUnless(canvas.CHROME, 'Chrome not found')
class ChromeDiesWithKilledServer(TempHomeCase):
    """kill -9 skips atexit. DevTools runs over pipes, so Chrome sees them close and exits."""

    def test_sigkill_during_thumbnail_rendering_leaves_no_chrome(self):
        tmpdir = os.path.join(self.tmp, 'tmp')
        os.makedirs(tmpdir)
        self.env['TMPDIR'] = tmpdir
        design = os.path.join(self.home, 'p', 'design')
        boards = tuple(f'A{i:02d}-B.html' for i in range(1, 9))
        self.make_idea(design, 'demo', boards=boards)
        port = free_port()
        proc = subprocess.Popen([sys.executable, CANVAS_PY, 'serve', design, '--port', str(port)],
                                env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())

        def leftovers():
            for pid, _ in processes_using(os.path.join(tmpdir, 'mockup-canvas-chrome-')):
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        self.addCleanup(leftovers)
        end = time.monotonic() + 15
        while True:
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('GET', '/demo/thumbs/A01-B.png')
                conn.getresponse().read()
                conn.close()
                break
            except OSError:
                self.assertLess(time.monotonic(), end, 'server did not start')
                time.sleep(0.1)
        for b in boards[1:]:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            conn.request('GET', f'/demo/thumbs/{b[:-5]}.png')
            conn.getresponse().read()
            conn.close()
        profile = os.path.join(tmpdir, 'mockup-canvas-chrome-')
        end = time.monotonic() + 20
        while not any('--type=renderer' in c for _, c in processes_using(profile)):
            self.assertLess(time.monotonic(), end, 'Chrome did not start rendering')
            time.sleep(0.05)
        self.assertGreater(len(processes_using(profile)), 1)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(5)
        # Chrome shuts down once it sees the pipes close: under 1 s idle, up to about 4 s on a
        # busy CI runner (measured), so 15 s only matters when it never exits
        end = time.monotonic() + 15
        while processes_using(profile) and time.monotonic() < end:
            time.sleep(0.1)
        self.assertEqual(processes_using(profile), [], 'Chrome outlived the killed server')


class InFlightStarts(TempHomeCase):
    def test_close_all_waits_for_a_starting_chrome_and_closes_it(self):
        entered, release = threading.Event(), threading.Event()
        made = []

        class SlowSession:
            def __init__(self, **kw):
                entered.set()
                release.wait(5)
                self.closed = False
                made.append(self)

            def capture(self, *a, **kw):
                pass

            def close(self):
                self.closed = True
        idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo')
        q = canvas._ThumbQueue(workers=1)
        with mock.patch.object(canvas, '_CdpSession', SlowSession), mock.patch('sys.stderr'):
            src, w, h, out = canvas._thumb_target(idea, 'A01-One.html')
            q.request(src, w, h, out, 'demo', 'A01-One.html')
            self.assertTrue(entered.wait(5))
            threading.Timer(0.3, release.set).start()
            q.close_all()
            self.assertEqual(len(made), 1)
            end = time.monotonic() + 5
            while not made[0].closed and time.monotonic() < end:
                time.sleep(0.02)
        self.assertTrue(made[0].closed)
        self.assertEqual(q.sessions, [])

    def test_kill_all_stops_a_chrome_that_is_starting(self):
        fake = os.path.join(self.tmp, 'sleepy')
        with open(fake, 'w') as f:
            f.write(f'#!{sys.executable}\nimport time\ntime.sleep(60)\n')
        os.chmod(fake, 0o755)
        errors = []

        def start():
            try:
                canvas._CdpSession(connect_timeout=20)
            except canvas.CdpConnectError as e:
                errors.append(e)
        with mock.patch.object(canvas, '_get_chrome', return_value=fake), \
                mock.patch.object(canvas, '_CHROMES', set()), \
                mock.patch.object(canvas, '_CHROME_SHUTDOWN', False):
            t = threading.Thread(target=start)
            t.start()
            end = time.monotonic() + 5
            while not any(c.proc for c in canvas._CHROMES) and time.monotonic() < end:
                time.sleep(0.02)
            chrome = next(iter(canvas._CHROMES))
            t0 = time.monotonic()
            canvas._kill_all_chrome()
            t.join(10)
            self.assertLess(time.monotonic() - t0, 5, 'start did not fail fast')
            self.assertEqual(len(errors), 1)
            self.assertIsNotNone(chrome.proc.returncode)
            self.assertFalse(os.path.exists(chrome.profile))
            late = canvas._Chrome()
            with self.assertRaises(canvas.CdpConnectError):   # no new Chrome after shutdown
                late.spawn([fake])
            late.kill()
            self.assertFalse(os.path.exists(late.profile))


class StaleProfiles(TempHomeCase):
    def test_removes_only_old_unused_profiles(self):
        base = os.path.join(self.tmp, 'tmp')
        os.makedirs(base)
        old = time.time() - 7200
        paths = {}
        for name in ('old', 'young', 'busy'):
            paths[name] = tempfile.mkdtemp(prefix='mockup-canvas-chrome-', dir=base)
            open(os.path.join(paths[name], 'Local State'), 'w').close()
            if name != 'young':
                os.utime(paths[name], (old, old))
        other = os.path.join(base, 'something-else')
        os.makedirs(other)
        os.utime(other, (old, old))
        busy = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)',
                                 '--user-data-dir=' + paths['busy']])
        self.addCleanup(busy.wait)
        self.addCleanup(busy.kill)
        with mock.patch.object(canvas.tempfile, 'tempdir', base):
            self.assertEqual(canvas._clean_stale_profiles(), 1)
        self.assertFalse(os.path.exists(paths['old']))
        for keep in (paths['young'], paths['busy'], other):
            self.assertTrue(os.path.isdir(keep), keep)

    def test_skips_folders_of_other_users(self):
        base = os.path.join(self.tmp, 'tmp')
        os.makedirs(base)
        p = tempfile.mkdtemp(prefix='mockup-canvas-chrome-', dir=base)
        os.utime(p, (0, 0))
        # Seen as another user's folder (a shared /tmp): never deleted
        with mock.patch.object(canvas.tempfile, 'tempdir', base), \
                mock.patch.object(canvas.os, 'getuid', return_value=os.getuid() + 1):
            self.assertEqual(canvas._clean_stale_profiles(), 0)
        self.assertTrue(os.path.isdir(p))
        # A link planted under the prefix is not followed or deleted
        target = os.path.join(self.tmp, 'victim')
        os.makedirs(target)
        link = os.path.join(base, 'mockup-canvas-chrome-link')
        os.symlink(target, link)
        os.utime(link, (0, 0), follow_symlinks=False)
        with mock.patch.object(canvas.tempfile, 'tempdir', base):
            self.assertEqual(canvas._clean_stale_profiles(), 1)   # only the user's own folder
        self.assertFalse(os.path.exists(p))
        self.assertTrue(os.path.islink(link) and os.path.isdir(target))

    def test_keeps_everything_when_ps_fails(self):
        base = os.path.join(self.tmp, 'tmp')
        os.makedirs(base)
        p = tempfile.mkdtemp(prefix='mockup-canvas-chrome-', dir=base)
        os.utime(p, (0, 0))
        with mock.patch.object(canvas.tempfile, 'tempdir', base), \
                mock.patch.object(canvas, '_ps_commands', return_value=None):
            self.assertEqual(canvas._clean_stale_profiles(), 0)
        self.assertTrue(os.path.isdir(p))


if __name__ == '__main__':
    unittest.main()
