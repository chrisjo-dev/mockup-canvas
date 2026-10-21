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
