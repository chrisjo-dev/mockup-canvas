"""Viewer behavior in real headless Chrome: level of detail, virtualization, drag save, undo/redo,
arrows, badges, touch, read-only, export and overview. Skipped when Chrome is not installed."""
import json
import os
import pathlib
import time
import unittest
from unittest import mock

from helpers import ServerCase, canvas

W, H = 1200, 800
COLORS = ('#e53935', '#8e24aa', '#3949ab', '#039be5', '#00897b', '#7cb342', '#fdd835', '#fb8c00')


def board(color):
    return ('<!doctype html><html><head><meta charset="utf-8"></head>'
            f'<body style="margin:0;background:{color}"><h1>Board</h1></body></html>')


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class ViewerCase(ServerCase):
    def setUp(self):
        super().setUp()
        # A queue of its own, so no thumbnail job outlives this test's temp folder
        q = canvas._ThumbQueue()
        patcher = mock.patch.object(canvas, '_THUMBS', q)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(q.close_all)
        self.design = os.path.join(self.home, 'p', 'design')
        names = [f'A0{i + 1}-B{i + 1}.html' for i in range(8)]
        self.idea = self.make_idea(self.design, 'demo', boards=names,
                                   links=[{'from': names[0], 'to': names[1], 'label': 'Next'},
                                          {'from': names[5], 'to': names[6]}])
        for n, c in zip(names, COLORS):
            with open(os.path.join(self.idea, 'boards', n), 'w') as f:
                f.write(board(c))
        self.cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(self.cj)
        for i, n in enumerate(names):
            data['boards'][n]['x'] = i * 430
        data['boards'][names[0]]['comments'] = [{'text': 'a', 'by': 'r', 'created': 't'},
                                                 {'text': 'b', 'by': 'r', 'created': 't'}]
        data['boards'][names[1]]['impl'] = {'route': '/b2', 'files': []}
        self.write_json(self.cj, data)
        self.names = names
        self.s = canvas._CdpSession()
        self.addCleanup(self.s.close)

    # ── helpers ──
    def open(self, url):
        s = self.s
        s.cdp.deadline = time.monotonic() + 60
        s.call('Emulation.setDeviceMetricsOverride', width=W, height=H, deviceScaleFactor=1, mobile=False)
        s.call('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=5)
        s.cdp.events.clear()
        s.call('Page.navigate', url=url)
        s.cdp.wait_event('Page.loadEventFired')
        self.until('document.getElementById("loading").classList.contains("gone")')

    def js(self, expr):
        self.s.cdp.deadline = time.monotonic() + 30
        r = self.s.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in r:
            raise AssertionError(f'{expr}: {r["exceptionDetails"]}')
        return r['result'].get('value')

    def until(self, expr, secs=30):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            v = self.js(expr)
            if v:
                return v
            time.sleep(0.05)
        raise AssertionError(f'timed out waiting for: {expr} (last: {self.js(expr)!r})')

    def input(self, method, **kw):
        self.s.cdp.deadline = time.monotonic() + 30
        self.s.call(method, **kw)

    def mouse(self, kind, x, y, buttons=1, **kw):
        self.input('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left', buttons=buttons, **kw)

    def key(self, key, code, mods):
        for kind in ('rawKeyDown', 'keyUp'):
            self.input('Input.dispatchKeyEvent', type=kind, key=key, code=code, modifiers=mods,
                       windowsVirtualKeyCode=ord(key.upper()))

    def zoom(self):
        return self.js('+/scale\\(([\\d.e-]+)\\)/.exec(document.getElementById("canvas").style.transform)[1]')

    def wheel_to(self, target, x, y):
        for _ in range(80):
            z = self.zoom()
            if abs(z - target) / target < 0.08:
                return z
            self.input('Input.dispatchMouseEvent', type='mouseWheel', x=x, y=y, deltaX=0,
                       deltaY=-40 if z < target else 40)
        return self.zoom()

    def bar_center(self, name):
        return self.js(f'(() => {{ const r = document.querySelector(\'.board[data-file="{name}"] .board-bar\')'
                       '.getBoundingClientRect(); return [Math.max(r.left, 8) + 40, r.top + r.height / 2]; })()')

    def board_x(self, name):
        return self.read_json(self.cj)['boards'][name]['x']

    def count(self, sel):
        return self.js(f'document.querySelectorAll({json.dumps(sel)}).length')


class LiveViewer(ViewerCase):
    def test_lod_virtualization_drag_undo_arrows_badges_touch(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True,
                          read_only=False)
        self.open(f'http://127.0.0.1:{self.port}/demo/')
        a01, a02 = self.names[0], self.names[1]

        # Badges
        self.assertEqual(self.count('.built-badge'), 1)
        self.assertEqual(self.js('document.querySelector(".cmt-badge").textContent'), '2')

        # Fit view of 8 boards is below 35%: thumbnails, no live iframes; they render in the background
        self.assertLess(self.zoom(), 0.35)
        self.assertEqual(self.count('iframe'), 0)
        self.until('document.querySelectorAll("img.thumb.ok").length === 8', 90)
        thumbs = os.listdir(os.path.join(self.idea, 'render', '.thumbs'))
        self.assertEqual(len(thumbs), 8, thumbs)

        # Zoom in on the first board: live iframes only near the viewport
        x, y = self.bar_center(a01)
        z = self.wheel_to(1.0, x, y)   # around the title bar, so it stays on screen
        self.assertGreater(z, 0.35)
        self.until(f'!!document.querySelector(\'.board[data-file="{a01}"] iframe\')', 10)
        live = self.count('iframe')
        self.assertGreater(live, 0)
        self.assertLess(live, 8)
        self.assertEqual(self.count(f'.board[data-file="{self.names[7]}"] iframe'), 0)

        # Drag the first board by its title bar: arrow follows, position is saved, iframe is not rebuilt
        self.js(f'document.querySelector(\'.board[data-file="{a01}"] iframe\').__mark = 1')
        d0 = self.js('document.querySelector("#arrow-svg > path").getAttribute("d")')
        x0 = self.board_x(a01)
        x, y = self.bar_center(a01)
        self.mouse('mousePressed', x, y, clickCount=1)
        for i in range(1, 11):
            self.mouse('mouseMoved', x + 10 * i, y + 10 * i)
        time.sleep(0.1)
        self.assertNotEqual(self.js('document.querySelector("#arrow-svg > path").getAttribute("d")'), d0)
        self.mouse('mouseReleased', x + 100, y + 100, buttons=0, clickCount=1)
        z = self.zoom()
        moved = round(x0 + 100 / z)
        end = time.monotonic() + 10
        while self.board_x(a01) != moved and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(self.board_x(a01), moved)
        # The saved canvas.json comes back as a 'canvas' event (the watcher is not running here)
        self.js('window.__fetches = 0; const f0 = window.fetch; '
                'window.fetch = (...a) => { if (String(a[0]).includes("canvas.json")) window.__fetches++; return f0(...a); }; 1')
        canvas._broadcast('demo', {'type': 'canvas'})
        self.until('window.__fetches === 1', 5)
        time.sleep(0.5)
        self.assertEqual(self.js(f'document.querySelector(\'.board[data-file="{a01}"] iframe\').__mark'), 1)
        self.assertEqual(self.js(f'document.querySelector(\'.board[data-file="{a01}"]\').style.left'),
                         f'{moved}px')

        # Undo and redo (Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z)
        mod = 4 if os.uname().sysname == 'Darwin' else 2
        self.key('z', 'KeyZ', mod)
        self.until(f'document.querySelector(\'.board[data-file="{a01}"]\').style.left === "{x0}px"', 5)
        end = time.monotonic() + 5
        while self.board_x(a01) != x0 and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(self.board_x(a01), x0)
        self.key('z', 'KeyZ', mod | 8)
        end = time.monotonic() + 5
        while self.board_x(a01) != moved and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(self.board_x(a01), moved)

        # Touch pan and pinch
        t0 = self.js('document.getElementById("canvas").style.transform')
        sx, sy = 600, 650   # inside the stage, above the toolbar
        self.input('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x': sx, 'y': sy}])
        for i in range(1, 6):
            self.input('Input.dispatchTouchEvent', type='touchMove', touchPoints=[{'x': sx - 20 * i, 'y': sy}])
        self.input('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
        time.sleep(0.1)
        self.assertNotEqual(self.js('document.getElementById("canvas").style.transform'), t0)
        z0 = self.zoom()
        self.input('Input.dispatchTouchEvent', type='touchStart',
                   touchPoints=[{'x': 500, 'y': 650, 'id': 1}, {'x': 700, 'y': 650, 'id': 2}])
        for i in range(1, 6):
            self.input('Input.dispatchTouchEvent', type='touchMove',
                       touchPoints=[{'x': 500 - 20 * i, 'y': 650, 'id': 1}, {'x': 700 + 20 * i, 'y': 650, 'id': 2}])
        self.input('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
        time.sleep(0.1)
        self.assertGreater(self.zoom(), z0 * 1.5)

        # A burst of watcher events for one board reloads it once (debounced); other boards stay
        self.until(f'!!document.querySelector(\'.board[data-file="{a01}"] iframe\')', 10)
        for _ in range(5):
            canvas._broadcast('demo', {'type': 'board', 'file': a01})
        self.until(f'/[?]_=1$/.test(document.querySelector(\'.board[data-file="{a01}"] iframe\').src)', 10)
        time.sleep(0.5)
        self.assertTrue(self.js(f'/[?]_=1$/.test(document.querySelector(\'.board[data-file="{a01}"] iframe\').src)'))
        self.assertEqual(self.js('[...document.querySelectorAll("iframe")].filter(f => !f.src.includes("A01") '
                                 '&& f.src.includes("?_=")).length'), 0)

    def test_read_only_share_cannot_drag(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True,
                          read_only=True)
        self.open(f'http://127.0.0.1:{self.port}/demo/')
        self.assertNotEqual(self.js('getComputedStyle(document.getElementById("ro-badge")).display'), 'none')
        a01 = self.names[0]
        x0 = self.board_x(a01)
        x, y = self.bar_center(a01)
        self.mouse('mousePressed', x, y, clickCount=1)
        for i in range(1, 6):
            self.mouse('mouseMoved', x + 20 * i, y)
        self.mouse('mouseReleased', x + 100, y, buttons=0, clickCount=1)
        time.sleep(0.5)
        self.assertEqual(self.board_x(a01), x0)


class StaticViewer(ViewerCase):
    def test_export_and_overview_keep_live_boards(self):
        out = os.path.join(self.tmp, 'out')
        self.assertEqual(self.run_cli('export', self.idea, out).returncode, 0)
        index = pathlib.Path(out, 'index.html').as_uri()
        self.s.file_roots = [out]   # sessions refuse every file:// URL outside the allowed folders
        self.open(index)
        # No server: no thumbnails; visible boards are live iframes at any zoom
        self.until('document.querySelectorAll("iframe").length > 0', 10)
        self.assertEqual(self.count('img.thumb'), 0)
        self.assertEqual(self.count('.cmt-badge'), 1)
        self.open(index + '?overview=1')
        self.until('document.querySelectorAll("iframe").length === 8', 10)


if __name__ == '__main__':
    unittest.main()
