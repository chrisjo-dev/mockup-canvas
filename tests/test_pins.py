"""Pins: comments that point at a spot or an area of a board, filled in by the server's Chrome."""
import json
import os
import unittest
from unittest import mock

from helpers import ServerCase, TempHomeCase, board_html, canvas


class PinStorage(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(self.cj)
        data['boards']['A01-One.html']['comments'] = [{'text': 'plain comment', 'by': 'r', 'created': 't'}]
        self.write_json(self.cj, data)

    def comments(self, f='A01-One.html'):
        return self.read_json(self.cj)['boards'][f]['comments']

    def test_point_area_and_selector(self):
        n, c = canvas.add_pin(self.idea, 'A01-One.html', ' Too small ', at={'x': 10.4, 'y': 20})
        self.assertEqual(n, 1)   # plain comments are not numbered
        self.assertRegex(c['id'], r'^p[0-9a-f]{8}$')
        self.assertEqual((c['text'], c['at'], c['state']), ('Too small', {'x': 10, 'y': 20, 'w': 0, 'h': 0}, 'pending'))
        n, c = canvas.add_pin(self.idea, 'A01-One.html', 'Header', at='0,0,500,90')
        self.assertEqual((n, c['at']), (2, {'x': 0, 'y': 0, 'w': 390, 'h': 90}))   # clamped to the 390 px board
        n, c = canvas.add_pin(self.idea, 'A01-One.html', 'Nav', selector='nav > a')
        self.assertEqual((n, c['target'], 'at' in c), (3, {'selector': 'nav > a'}, False))
        self.assertEqual([x['text'] for x in self.comments()], ['plain comment', 'Too small', 'Header', 'Nav'])
        self.assertEqual([n for n, _ in canvas.board_pins(self.read_json(self.cj)['boards']['A01-One.html'])], [1, 2, 3])

    def test_bad_input_and_limits(self):
        for kw in ({'at': {'x': 'a', 'y': 1}}, {'at': '1'}, {'at': {'x': 1, 'y': 1, 'w': -5}}, {'at': {'x': float('nan'), 'y': 0}},
                   {}, {'selector': ''}, {'selector': 'x' * 301}):
            with self.assertRaises(canvas.PinError, msg=kw):
                canvas.add_pin(self.idea, 'A01-One.html', 'note', **kw)
        with self.assertRaisesRegex(canvas.PinError, 'empty'):
            canvas.add_pin(self.idea, 'A01-One.html', '   ', at='1,1')
        with self.assertRaisesRegex(canvas.PinError, '500'):
            canvas.add_pin(self.idea, 'A01-One.html', 'x' * 501, at='1,1')
        with self.assertRaisesRegex(canvas.PinError, 'No board'):
            canvas.add_pin(self.idea, 'Z99.html', 'note', at='1,1')
        for i in range(canvas.PIN_MAX_PER_BOARD):
            canvas.add_pin(self.idea, 'A02-Two.html', f'n{i}', at='1,1')
        with self.assertRaisesRegex(canvas.PinError, 'at most'):
            canvas.add_pin(self.idea, 'A02-Two.html', 'one more', at='1,1')

    def test_resolve_reopen_delete(self):
        canvas.add_pin(self.idea, 'A01-One.html', 'a', at='1,1')
        _, c = canvas.add_pin(self.idea, 'A01-One.html', 'b', at='2,2')
        n, r = canvas.set_pin_resolved(self.idea, 'A01-One.html', 2, note='fixed', by='agent')
        self.assertEqual((n, r['resolved']['note'], r['resolved']['by']), (2, 'fixed', 'agent'))
        canvas.set_pin_resolved(self.idea, 'A01-One.html', c['id'], resolved=False)
        self.assertNotIn('resolved', self.comments()[2])
        img = os.path.join(self.idea, canvas.PIN_DIR, c['id'] + '.png')
        os.makedirs(os.path.dirname(img))
        open(img, 'wb').close()
        canvas.delete_pin(self.idea, 'A01-One.html', '2')
        self.assertEqual([x['text'] for x in self.comments()], ['plain comment', 'a'])
        self.assertFalse(os.path.exists(img))
        with self.assertRaisesRegex(canvas.PinError, 'No pin'):
            canvas.delete_pin(self.idea, 'A01-One.html', 1 + 1)
        with self.assertRaisesRegex(canvas.PinError, 'No pin'):
            canvas.set_pin_resolved(self.idea, 'A01-One.html', 'plain comment')

    def test_other_commands_keep_pin_fields(self):
        _, c = canvas.add_pin(self.idea, 'A01-One.html', 'a', at='1,1')
        data = self.read_json(self.cj)
        data['boards']['A01-One.html']['comments'][1].update(target={'selector': 'b', 'future': 1}, img=c['id'] + '.png', later=True)
        self.write_json(self.cj, data)
        before = self.read_json(self.cj)['boards']['A01-One.html']['comments']
        for args in (('status', self.idea, 'A01-One.html', 'approved'), ('group', self.idea, 'A01-One.html', 'g'),
                     ('comment', self.idea, 'A01-One.html', 'another')):
            self.assertEqual(self.run_cli(*args).returncode, 0, args)
        self.assertEqual(self.comments()[:2], before)

    def test_needs_probe(self):
        _, a = canvas.add_pin(self.idea, 'A01-One.html', 'a', at='1,1')
        b = self.read_json(self.cj)['boards']['A01-One.html']
        self.assertEqual([c['id'] for c in canvas.pins_needing_probe(self.idea, b, 'A01-One.html')], [a['id']])
        ver = canvas._board_ver(self.idea, 'A01-One.html')
        b['comments'][1].update(state='found', ver=ver)
        self.assertEqual(canvas.pins_needing_probe(self.idea, b, 'A01-One.html'), [])
        b['comments'][1]['ver'] = '1'   # the board changed since
        self.assertEqual(len(canvas.pins_needing_probe(self.idea, b, 'A01-One.html')), 1)
        b['comments'][1]['resolved'] = {'at': 't'}
        self.assertEqual(canvas.pins_needing_probe(self.idea, b, 'A01-One.html'), [])

    def test_crop_box_stays_inside_the_board(self):
        self.assertEqual(canvas._pin_crop_box({'x': 5, 'y': 5, 'w': 0, 'h': 0}, None, 390, 844),
                         {'x': 0, 'y': 0, 'width': 240, 'height': 160, 'scale': 1})
        box = canvas._pin_crop_box({'x': 0, 'y': 0, 'w': 390, 'h': 844}, None, 390, 844)
        self.assertLessEqual(box['height'], 400)
        self.assertLessEqual(box['x'] + box['width'], 390)

    def test_cli(self):
        r = self.run_cli('comment', self.idea, 'A01-One.html', 'Button', '--at', '20,30')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Pin 1 added', r.stdout)
        self.assertEqual(self.run_cli('comment', self.idea, 'A01-One.html', 'x', '--at', 'nope').returncode, 1)
        r = self.run_cli('comment', self.idea, 'A01-One.html', 'Nav', '--el', 'nav')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cli('pins', self.idea, '--json')
        rows = json.loads(r.stdout)
        self.assertEqual([(x['board'], x['n'], x['text'], x['selector']) for x in rows],
                         [('A01-One.html', 1, 'Button', None), ('A01-One.html', 2, 'Nav', 'nav')])
        r = self.run_cli('pins', self.idea, 'A01-One.html', '--resolve', '1', '--note', 'done')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cli('pins', self.idea)
        self.assertNotIn('Button', r.stdout)
        self.assertIn('2. "Nav"', r.stdout)
        self.assertIn('resolved: done', self.run_cli('pins', self.idea, '--all').stdout)
        self.assertEqual(self.run_cli('pins', self.idea, 'A01-One.html', '--resolve', '9').returncode, 1)


class PinApi(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo')
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})
        patcher = mock.patch.object(canvas._PINS, 'request')   # no Chrome in API tests
        self.probe = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, body, headers=None):
        status, _, data = self.request('POST', '/api/pin', body, headers=self.origin() if headers is None else headers)
        return status, json.loads(data or b'{}')

    def test_registry_round_trip(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, d = self.post({'project': 'p', 'idea': 'demo', 'file': 'A01-One.html', 'action': 'add', 'text': 'hi',
                           'at': {'x': 5, 'y': 6, 'w': 0, 'h': 0}})
        self.assertEqual((st, d['ok'], d['n']), (200, True, 1))
        self.assertEqual(self.probe.call_args[0][1:], ('A01-One.html', 'p/demo'))
        st, d = self.post({'project': 'p', 'idea': 'demo', 'file': 'A01-One.html', 'action': 'resolve', 'ref': d['pin']['id']})
        self.assertIn('resolved', d['pin'])
        st, d = self.post({'project': 'p', 'idea': 'demo', 'file': 'A01-One.html', 'action': 'delete', 'ref': 1})
        self.assertEqual((st, d['ok']), (200, True))
        self.assertNotIn('comments', self.read_json(self.cj)['boards']['A01-One.html'])

    def test_bad_input(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True, read_only=False)
        add = {'action': 'add', 'text': 'hi', 'at': '1,1'}
        for body in (dict(add, idea='../p/design/demo', file='A01-One.html'), dict(add, idea='demo', file='../canvas.json'),
                     dict(add, idea='demo', file='A01-One.html', text='x' * 501), dict(add, idea='.trash', file='A01-One.html'),
                     dict(add, idea='demo', file='A01-One.html', action='nuke'), dict(add, idea='demo', file='Z.html')):
            st, d = self.post(body)
            self.assertEqual((st, d['ok']), (400, False), body)
        st, d = self.post(dict(add, idea='demo', file='A01-One.html'))
        self.assertEqual((st, d['ok']), (200, True))
        self.assertEqual(self.probe.call_args[0][2], 'demo')

    def test_needs_same_origin(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        for headers in ({}, {'Origin': 'http://evil.example'}):
            st, _ = self.post({'project': 'p', 'idea': 'demo', 'file': 'A01-One.html', 'action': 'add', 'text': 'x', 'at': '1,1'},
                              headers=headers)
            self.assertEqual(st, 403)
        self.assertNotIn('comments', self.read_json(self.cj)['boards']['A01-One.html'])

    def test_share_and_read_only_have_no_pins(self):
        _, c = canvas.add_pin(self.idea, 'A01-One.html', 'a', at='1,1')
        os.makedirs(os.path.join(self.idea, canvas.PIN_DIR))
        with open(os.path.join(self.idea, canvas.PIN_DIR, c['id'] + '.png'), 'wb') as f:
            f.write(b'png')
        token = 'tok_pin_1'
        cookie = {'Cookie': 'canvas_token=' + token}
        cases = [
            (canvas.CanvasHandler, dict(design_dir=self.design, share_token=token, share_edit=True, read_only=False), '/demo/'),
            (canvas.CanvasHandler, dict(design_dir=self.design, share_token='', share_edit=True, read_only=True), '/demo/'),
            (canvas.RegistryHandler, dict(share_token=token, share_edit=True, read_only=False,
                                         frozen_roots=[{'name': 'p', 'path': self.design}]), '/p/demo/'),
        ]
        for base, attrs, prefix in cases:
            self.start_server(base, **attrs)
            st, _ = self.post({'project': 'p', 'idea': 'demo', 'file': 'A01-One.html', 'action': 'delete', 'ref': 1},
                              headers=dict(self.origin(), **cookie))
            self.assertEqual(st, 403, (base.__name__, attrs))
            self.assertEqual(self.request('GET', prefix + 'pins/' + c['id'] + '.png', headers=cookie)[0], 404)
        self.assertEqual(len(self.read_json(self.cj)['boards']['A01-One.html']['comments']), 1)

    def test_pin_image(self):
        _, c = canvas.add_pin(self.idea, 'A01-One.html', 'a', at='1,1')
        os.makedirs(os.path.join(self.idea, canvas.PIN_DIR))
        with open(os.path.join(self.idea, canvas.PIN_DIR, c['id'] + '.png'), 'wb') as f:
            f.write(b'png')
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, h, body = self.request('GET', '/p/demo/pins/' + c['id'] + '.png')
        self.assertEqual((st, body, h['Content-Type']), (200, b'png', 'image/png'))
        for name in ('..%2Fcanvas.json', 'p1234.png', c['id'] + '.html', '..'):
            self.assertEqual(self.request('GET', '/p/demo/pins/' + name)[0], 404, name)

    def test_linked_pin_folder_is_not_served(self):
        outside = os.path.join(self.home, 'outside')
        os.makedirs(outside)
        with open(os.path.join(outside, 'p0123abcd.png'), 'wb') as f:
            f.write(b'secret')
        os.makedirs(os.path.join(self.idea, 'render'))
        os.symlink(outside, os.path.join(self.idea, canvas.PIN_DIR))
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        self.assertEqual(self.request('GET', '/p/demo/pins/p0123abcd.png')[0], 404)


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class PinProbe(TempHomeCase):
    BODY = ('<style>body{margin:0}main{padding:40px 20px}button{display:block;width:120px;height:40px}</style>'
            '<main><h1 id="t">Title</h1><div class="row"><button class="primary">Send</button>'
            '<button class="ghost">Cancel</button></div></main>')

    def setUp(self):
        super().setUp()
        self.idea = self.make_idea(os.path.join(self.home, 'design'), 'demo')
        self.board = os.path.join(self.idea, 'boards', 'A01-One.html')
        with open(self.board, 'w') as f:
            f.write(board_html(self.BODY))
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.session = canvas._CdpSession(block_private=True)
        self.addCleanup(self.session.close)

    def pins(self):
        return [c for _, c in canvas.board_pins(self.read_json(self.cj)['boards']['A01-One.html'])]

    def test_find_follow_and_lose(self):
        h1 = self.read_json(self.cj)
        canvas.add_pin(self.idea, 'A01-One.html', 'send', at='60,150')
        canvas.add_pin(self.idea, 'A01-One.html', 'title', selector='#t')
        canvas.add_pin(self.idea, 'A01-One.html', 'nothing', selector='.missing')
        self.assertEqual(canvas.probe_pins(self.session, self.idea, 'A01-One.html'), 3)
        send, title, nothing = self.pins()
        self.assertEqual((send['state'], send['target']['text'], send['target']['selector']),
                         ('found', 'Send', 'button.primary'))
        self.assertTrue(os.path.getsize(os.path.join(self.idea, canvas.PIN_DIR, send['img'])) > 100)
        self.assertEqual((title['state'], title['at']['y'], title['target']['text']), ('found', title['target']['rect']['y'], 'Title'))
        self.assertEqual(nothing['state'], 'none')
        self.assertEqual(canvas.probe_pins(self.session, self.idea, 'A01-One.html'), 0)   # nothing new

        # The board gets 100 px taller at the top: the pins move with their elements
        with open(self.board, 'w') as f:
            f.write(board_html('<div style="height:100px"></div>' + self.BODY))
        os.utime(self.board, ns=(1, os.stat(self.board).st_mtime_ns + 10**9))
        canvas.probe_pins(self.session, self.idea, 'A01-One.html')
        send2, title2, _ = self.pins()
        self.assertEqual((send2['at']['x'], send2['at']['y']), (60, 250))
        self.assertEqual(title2['at']['y'], title['at']['y'] + 100)

        # The button is gone: the pin stays and says so
        with open(self.board, 'w') as f:
            f.write(board_html('<main><h1 id="t">Title</h1></main>'))
        os.utime(self.board, ns=(1, os.stat(self.board).st_mtime_ns + 2 * 10**9))
        canvas.probe_pins(self.session, self.idea, 'A01-One.html')
        send3 = self.pins()[0]
        self.assertEqual((send3['state'], send3['at']), ('lost', send2['at']))
        self.assertEqual(h1['boards']['A01-One.html']['x'], self.read_json(self.cj)['boards']['A01-One.html']['x'])


if __name__ == '__main__':
    unittest.main()
