"""render and overview need Google Chrome; skipped when it is not installed."""
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from helpers import ServerCase, TempHomeCase, canvas


def dump_dom(url, budget=3000):
    """Load url with the same Chrome flags render/overview use and return the DOM."""
    profile = tempfile.mkdtemp(prefix='mc-test-chrome-')
    try:
        return subprocess.run(canvas._chrome_args(profile, 800, 600, budget) + ['--dump-dom', url],
                              capture_output=True, text=True, timeout=90).stdout
    finally:
        shutil.rmtree(profile, ignore_errors=True)


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class RenderCommands(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo',
                                   boards=('A01-One.html', 'A02-Two.html'),
                                   links=[{'from': 'A02-Two.html', 'to': 'A01-One.html', 'label': 'Back'}])

    def test_render_board(self):
        r = self.run_cli('render', self.idea, 'boards/A01-One.html')
        self.assertEqual(r.returncode, 0, r.stderr)
        png = os.path.join(self.idea, 'render', 'A01-One.png')
        with open(png, 'rb') as f:
            self.assertEqual(f.read(8), b'\x89PNG\r\n\x1a\n')

    def test_overview(self):
        r = self.run_cli('overview', self.idea)
        self.assertEqual(r.returncode, 0, r.stderr)
        png = os.path.join(self.idea, 'render', '_overview.png')
        self.assertGreater(os.path.getsize(png), 0)
        self.assertFalse(os.path.exists(os.path.join(self.idea, 'render', '_overview_tmp')))


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'viewport.html')


def pixel(rows, ch, x, y):
    return tuple(rows[y][x * ch:x * ch + 3])


def decode(rgb):
    """Inverse of enc() in fixtures/viewport.html."""
    assert rgb[2] == 7, rgb
    return rgb[0] * 256 + rgb[1]


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class ExactViewport(TempHomeCase):
    """Headless Chrome keeps windows at least 500 px wide; render must still lay out at 390."""

    def setUp(self):
        super().setUp()
        self.idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo', boards=())
        with open(FIXTURE, encoding='utf-8') as f:
            page = f.read()
        meta = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        for name, html in (('V01-Meta.html', page.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + meta)),
                           ('V02-NoMeta.html', page)):
            with open(os.path.join(self.idea, 'boards', name), 'w') as f:
                f.write(html)
            self.assertEqual(self.run_cli('add', self.idea, os.path.join(self.idea, 'boards', name),
                                          '--size', 'mobile').returncode, 0)

    def read(self, name):
        return canvas.png_read(os.path.join(self.idea, 'render', name))

    def test_390_render_is_390_wide_with_fixed_element(self):
        r = self.run_cli('render', self.idea, '--wait', '0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('Warning', r.stderr)
        for name in ('V01-Meta.png', 'V02-NoMeta.png'):
            w, h, ch, rows = self.read(name)
            self.assertEqual((w, h), (390, 844), name)
            self.assertEqual(decode(pixel(rows, ch, 5, 5)), 390, name)       # innerWidth
            self.assertEqual(decode(pixel(rows, ch, 5, 25)), 844, name)      # innerHeight
            # the right:16px fixed square is inside the PNG, with white on its right
            self.assertEqual(pixel(rows, ch, 390 - 16 - 20, 844 - 16 - 20), (255, 102, 0), name)
            self.assertEqual(pixel(rows, ch, 390 - 8, 844 - 36), (255, 255, 255), name)

    def test_full_page_keeps_width(self):
        r = self.run_cli('render', self.idea, 'V01-Meta.html', '--full-page', '--wait', '0')
        self.assertEqual(r.returncode, 0, r.stderr)
        w, h, ch, rows = self.read('V01-Meta.png')
        self.assertEqual((w, h), (390, 2000))
        self.assertEqual(decode(pixel(rows, ch, 5, 5)), 390)
        self.assertEqual(pixel(rows, ch, 10, 1990), (0, 0, 255))   # bottom of the page is captured

    def test_wait_is_real_time(self):
        board = os.path.join(self.idea, 'boards', 'V01-Meta.html')
        with open(board, encoding='utf-8') as f:
            html = f.read()
        with open(board, 'w', encoding='utf-8') as f:
            f.write(html.replace('</body>', '<script>setTimeout(function(){'
                                 'document.body.style.background="#00ff00"},1200)</script></body>'))
        self.assertEqual(self.run_cli('render', self.idea, 'V01-Meta.html', '--wait', '0').returncode, 0)
        _, _, ch, rows = self.read('V01-Meta.png')
        self.assertEqual(pixel(rows, ch, 200, 400), (255, 255, 255))
        self.assertEqual(self.run_cli('render', self.idea, 'V01-Meta.html', '--wait', '2500').returncode, 0)
        _, _, ch, rows = self.read('V01-Meta.png')
        self.assertEqual(pixel(rows, ch, 200, 400), (0, 255, 0))


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class BoardIsolation(ServerCase):
    def test_board_cannot_read_local_files(self):
        secret = os.path.join(self.home, 'secret.txt')
        with open(secret, 'w') as f:
            f.write('TOPSECRET')
        board = os.path.join(self.home, 'board.html')
        with open(board, 'w') as f:
            f.write('<!doctype html><body><p id="r">PENDING</p><script>'
                    'var r=document.getElementById("r");'
                    'try{var x=new XMLHttpRequest();x.open("GET",%s,false);x.send();'
                    'r.textContent="LEAK:"+x.responseText}catch(e){r.textContent="BLOCKED"}'
                    '</script></body>' % json.dumps(pathlib.Path(secret).as_uri()))
        dom = dump_dom(pathlib.Path(board).as_uri())
        self.assertIn('id="r"', dom)
        self.assertNotIn('TOPSECRET', dom)
        self.assertIn('BLOCKED', dom)

    def test_board_script_cannot_call_roots_api(self):
        design = os.path.join(self.home, 'p', 'design')
        idea = self.make_idea(design, 'demo')
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': design}]})
        with open(os.path.join(idea, 'boards', 'A01-One.html'), 'w') as f:
            f.write('<!doctype html><body><p id="a">PENDING</p><p id="b">PENDING</p><script>'
                    'var body=JSON.stringify({dirs:["~"]});'
                    'fetch("/api/roots/scan",{method:"POST",headers:{"Content-Type":"application/json"},body:body})'
                    '.then(function(r){return r.text()}).then(function(t){document.getElementById("a").textContent="OK:"+t})'
                    '.catch(function(){document.getElementById("a").textContent="BLOCKED"});'
                    'fetch("/api/roots/scan",{method:"POST",mode:"no-cors",headers:{"Content-Type":"text/plain"},body:body})'
                    '.then(function(){document.getElementById("b").textContent="SENT"})'
                    '.catch(function(){document.getElementById("b").textContent="BLOCKED"});'
                    '</script></body>')
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        with mock.patch.object(canvas, '_scan_for_roots', return_value=[]) as scan:
            dom = dump_dom(f'http://127.0.0.1:{self.port}/p/demo/boards/A01-One.html')
        self.assertIn('id="a">BLOCKED', dom)
        self.assertNotIn('id="a">OK:', dom)
        scan.assert_not_called()


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class ViewerSanitizes(TempHomeCase):
    def test_group_colors_and_geometry(self):
        idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo')
        cj = os.path.join(idea, 'canvas.json')
        data = self.read_json(cj)
        b = data['boards']['A01-One.html']
        b.update(x='10px;position:fixed;background:url(http://evil.example/x)', group='g')
        data['groups'] = [{'id': 'g', 'label': 'G', 'color': 'red;background-image:url(http://evil.example/c)',
                           'textColor': '#abc'}]
        self.write_json(cj, data)
        out = os.path.join(self.tmp, 'out')
        self.assertEqual(self.run_cli('export', idea, out).returncode, 0)
        dom = dump_dom(pathlib.Path(out, 'index.html').as_uri())
        styles = ' '.join(re.findall(r'style="([^"]*)"', dom))
        self.assertIn('class="board"', dom)
        self.assertNotIn('evil.example', styles)
        self.assertNotIn('position: fixed', styles)
        self.assertIn('left: 0px', styles)
        self.assertIn('rgb(170, 187, 204)', styles)   # a safe color is kept


if __name__ == '__main__':
    unittest.main()
