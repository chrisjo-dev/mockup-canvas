"""A board cannot bake local files outside its idea folder into a PNG (real Chrome).

The secret file paints its whole page red; boards put it in a full-size iframe. A control board
loads a green page from its own assets/ folder, which must still work."""
import json
import os
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


class LocalFiles(TempHomeCase):
    def setUp(self):
        super().setUp()
        secret_dir = os.path.join(self.tmp, 'outside')
        os.makedirs(secret_dir)
        self.secret = os.path.join(secret_dir, 'secret.html')
        with open(self.secret, 'w') as f:
            f.write('<!doctype html><body style="margin:0;background:#f00;height:100vh">secret</body>')
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-Leak.html', 'A02-Ok.html'))
        os.makedirs(os.path.join(self.idea, 'assets'))
        with open(os.path.join(self.idea, 'assets', 'ok.html'), 'w') as f:
            f.write('<!doctype html><body style="margin:0;background:#008000;height:100vh">ok</body>')
        with open(os.path.join(self.idea, 'boards', 'A01-Leak.html'), 'w') as f:
            f.write(frame('file://' + self.secret))
        with open(os.path.join(self.idea, 'boards', 'A02-Ok.html'), 'w') as f:
            f.write(frame('../assets/ok.html'))
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
        self.assertEqual(colored(leak, RED), 0, 'local file baked into the render')
        self.assertGreater(colored(ok, GREEN), 400 * 300 // 2, 'files inside the idea must still load')

    def test_compare_board_render_blocks_files_outside_the_idea(self):
        app = os.path.join(self.tmp, 'app.png')
        canvas.png_write(app, 400, 300, [bytes(400 * 3)] * 300)
        out = os.path.join(self.tmp, 'cmp')
        r = self.run_cli('compare', self.idea, 'A01-Leak', '--png', app, '--out', out)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertEqual(colored(os.path.join(out, 'board.png'), RED), 0)

    def test_overview_blocks_files_outside_the_idea(self):
        r = self.run_cli('overview', self.idea)
        self.assertEqual(r.returncode, 0, r.stderr)
        png = os.path.join(self.idea, 'render', '_overview.png')
        self.assertEqual(colored(png, RED), 0)
        self.assertGreater(colored(png, GREEN), 0)


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
        for name in ('A01-Leak', 'A02-Ok'):
            self.assertEqual(self.request('GET', f'/demo/thumbs/{name}.png', headers=headers)[0], 202)
            outs[name] = canvas._thumb_target(self.idea, name + '.html')[3]
        end = time.monotonic() + 60
        while not all(os.path.isfile(o) for o in outs.values()):
            self.assertLess(time.monotonic(), end, 'thumbnails not rendered')
            time.sleep(0.2)
        return outs

    def check(self, outs):
        self.assertEqual(colored(outs['A01-Leak'], RED), 0, 'local file baked into the thumbnail')
        w, h, _, _ = canvas.png_read(outs['A02-Ok'])
        self.assertGreater(colored(outs['A02-Ok'], GREEN), w * h // 2)

    def test_thumbnail_blocks_local_files(self):
        self.check(self.render_thumbs())

    def test_thumbnail_in_share_mode(self):
        self.check(self.render_thumbs(share_token='tok_ABCdef123456', share_edit=False))


if __name__ == '__main__':
    unittest.main()
