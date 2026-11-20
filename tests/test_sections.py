"""Sections: an idea moved into another idea opens on that idea's canvas and keeps its own folder."""
import hashlib
import json
import os
import time

from helpers import ServerCase, TempHomeCase, canvas


def tree_digest(folder):
    """Every file under a folder with its content hash: proves a move rewrote nothing."""
    out = {}
    for base, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(base, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, folder)] = hashlib.sha256(fh.read()).hexdigest()
    return out


class MoveFunctions(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.promo = self.make_idea(self.design, 'promo', boards=('P01-Join.html', 'P02-Done.html'))
        self.og = self.make_idea(self.design, 'og', boards=('P01-Join.html', 'O02-Card.html'),
                                 links=[{'from': 'P01-Join.html', 'to': 'O02-Card.html', 'label': 'next'}])
        cj = os.path.join(self.og, 'canvas.json')
        data = self.read_json(cj)
        data['boards']['O02-Card.html'].update(status='approved', note='ok', comments=[{'text': 'hi'}])
        self.write_json(cj, data)
        with open(os.path.join(self.og, 'shared', 'tokens.css'), 'w') as f:
            f.write(':root{--og:1}')

    def test_move_in_keeps_every_file_and_move_out_restores_the_layout(self):
        before = tree_digest(self.og)
        self.assertEqual(canvas.move_idea(self.design, 'og', into='promo'), 'promo/og')
        inside = os.path.join(self.promo, 'og')
        self.assertFalse(os.path.exists(self.og))
        self.assertEqual(tree_digest(inside), before)   # same board id P01 in both, different tokens: nothing merged
        self.assertEqual(canvas._list_ideas(self.design), ['promo'])
        self.assertEqual(canvas._list_sections(self.promo), ['og'])
        self.assertEqual(self.read_json(os.path.join(self.promo, 'canvas.json'))['sections'], ['og'])

        self.assertEqual(canvas.move_idea(self.design, 'promo/og'), 'og')
        self.assertEqual(tree_digest(self.og), before)
        self.assertNotIn('sections', self.read_json(os.path.join(self.promo, 'canvas.json')))
        self.assertEqual(canvas._list_ideas(self.design), ['og', 'promo'])

    def test_section_order_is_the_saved_order_then_names(self):
        for n in ('zeta', 'alpha', 'mid'):
            self.make_idea(self.design, n)
        for n in ('zeta', 'alpha', 'mid'):
            canvas.move_idea(self.design, n, into='promo')
        self.assertEqual(canvas._list_sections(self.promo), ['zeta', 'alpha', 'mid'])
        cj = os.path.join(self.promo, 'canvas.json')
        data = self.read_json(cj)
        data['sections'] = ['mid', 'gone', 7]
        self.write_json(cj, data)
        self.assertEqual(canvas._list_sections(self.promo), ['mid', 'alpha', 'zeta'])

    def test_refusals(self):
        canvas.move_idea(self.design, 'og', into='promo')
        self.make_idea(self.design, 'og')            # a new idea took the old name
        self.make_idea(self.design, 'boards')
        self.make_idea(self.design, 'third')
        cases = [
            (('og',), {'into': 'promo'}, 'already has a section named og'),
            (('promo/og',), {}, 'design/og already exists'),
            (('promo/og',), {'into': 'third'}, 'already a section'),
            (('promo',), {'into': 'third'}, 'one level deep'),
            (('boards',), {'into': 'third'}, 'cannot be named boards'),
            (('third',), {'into': 'third'}, 'Not an idea to move into'),
            (('third',), {'into': 'nope'}, 'No idea named nope'),
            (('nope',), {'into': 'third'}, 'No idea named nope'),
            (('third',), {}, 'is not a section'),
            (('../x',), {'into': 'third'}, 'Not an idea name'),
            (('a/b/c',), {}, 'Not an idea name'),
            (('third',), {'into': '../promo'}, 'Not an idea to move into'),
        ]
        for args, kw, text in cases:
            with self.assertRaises(canvas.MoveError, msg=str((args, kw))) as cm:
                canvas.move_idea(self.design, *args, **kw)
            self.assertIn(text, str(cm.exception))
        self.assertTrue(os.path.isdir(os.path.join(self.promo, 'og')))   # nothing moved

    def test_recent_change_is_refused_only_when_asked(self):
        with self.assertRaises(canvas.MoveError) as cm:
            canvas.move_idea(self.design, 'og', into='promo', quiet_secs=10)
        self.assertIn('Try again when the agent is done', str(cm.exception))
        old = time.time() - 60
        for base, _, files in os.walk(self.og):
            for f in files:
                os.utime(os.path.join(base, f), (old, old))
        self.assertEqual(canvas.move_idea(self.design, 'og', into='promo', quiet_secs=10), 'promo/og')

    def test_linked_idea_or_section_is_not_followed(self):
        outside = self.make_idea(os.path.join(self.home, 'other'), 'secret')
        os.symlink(outside, os.path.join(self.design, 'lnk'))
        with self.assertRaises(canvas.MoveError):
            canvas.move_idea(self.design, 'lnk', into='promo')
        os.symlink(outside, os.path.join(self.promo, 'sec'))
        self.assertEqual(canvas._list_sections(self.promo), [])   # a linked folder is never a section

    def test_board_trash_inside_a_section_round_trips(self):
        canvas.move_idea(self.design, 'og', into='promo')
        inside = os.path.join(self.promo, 'og')
        before = self.read_json(os.path.join(inside, 'canvas.json'))
        tid = canvas.trash_board(self.design, 'promo/og', 'O02-Card.html')
        self.assertTrue(tid.startswith('promo/og/O02-Card-'))
        self.assertNotIn('O02-Card.html', self.read_json(os.path.join(inside, 'canvas.json'))['boards'])
        self.assertEqual(canvas.restore_trash(self.design, tid), {'kind': 'board', 'idea': 'promo/og', 'file': 'O02-Card.html'})
        self.assertEqual(self.read_json(os.path.join(inside, 'canvas.json')), before)
        self.assertEqual(os.listdir(os.path.join(self.design, '.trash')), [])
        with self.assertRaises(canvas.TrashError) as cm:
            canvas.trash_idea(self.design, 'promo/og')
        self.assertIn('Move it out of promo', str(cm.exception))
        # deleting the parent takes its sections along, and restore brings them back
        pid = canvas.trash_idea(self.design, 'promo')
        canvas.restore_trash(self.design, pid)
        self.assertEqual(canvas._list_sections(self.promo), ['og'])

    def test_cli_move_and_new_section(self):
        r = self.run_cli('move', self.og, self.promo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(os.path.join(self.promo, 'og'), r.stdout)
        r = self.run_cli('new', self.design, 'promo/winter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.promo, 'winter', 'shared', 'tokens.css')))
        self.assertEqual(canvas._list_sections(self.promo), ['og', 'winter'])
        r = self.run_cli('add', os.path.join(self.promo, 'og'), 'boards/O02-Card.html', '--group', 'current')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)   # every idea command takes a section folder
        r = self.run_cli('move', os.path.join(self.promo, 'og'), self.design)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(self.og))
        for args, text in ((('move', self.og, self.home), 'neither an idea folder'),
                           (('move', self.home, self.promo), 'not an idea folder'),
                           (('new', self.design, 'nope/winter'), 'no idea named nope'),
                           (('new', self.promo, 'winter2'), 'is an idea folder'),
                           (('new', self.design, 'promo/boards'), 'not an idea name')):
            r = self.run_cli(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(text, r.stdout, args)
        self.assertFalse(os.path.exists(os.path.join(self.promo, 'winter2')))


class SectionsServer(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.promo = self.make_idea(self.design, 'promo', boards=('P01-Join.html',))
        self.og = self.make_idea(self.design, 'og', boards=('P01-Join.html', 'O02-Card.html'))
        with open(os.path.join(self.og, 'shared', 'tokens.css'), 'w') as f:
            f.write(':root{--og:1}')
        os.makedirs(os.path.join(self.og, 'assets', 'img'))
        with open(os.path.join(self.og, 'assets', 'img', 'a.txt'), 'w') as f:
            f.write('asset')
        old = time.time() - 60   # past the API's quiet period
        for d in (self.promo, self.og):
            for base, _, files in os.walk(d):
                for f in files:
                    os.utime(os.path.join(base, f), (old, old))
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})

    def post(self, path, body, headers=None):
        status, _, data = self.request('POST', path, body, headers=self.origin() if headers is None else headers)
        return status, json.loads(data or b'{}')

    def index(self):
        return json.loads(self.request('GET', '/api/index')[2])

    def test_registry_move_serves_the_section_under_its_parent(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, d = self.post('/api/move', {'project': 'p', 'idea': 'og', 'into': 'promo'})
        self.assertEqual((st, d), (200, {'ok': True, 'idea': 'promo/og'}))

        idx = self.index()
        self.assertEqual([i['name'] for i in idx['ideas']], ['promo'])
        idea = idx['ideas'][0]
        self.assertEqual(idea['sections'], [{'name': 'og', 'boards': 2}])
        self.assertEqual([(b['f'], b.get('p')) for b in idea['boards']],
                         [('P01-Join.html', None), ('P01-Join.html', 'og'), ('O02-Card.html', 'og')])
        self.assertEqual((idx['projects'][0]['ideas'], idx['projects'][0]['boards']), (1, 3))

        for path, want in (('/p/promo/og/', 200), ('/p/promo/og/canvas.json', 200),
                           ('/p/promo/og/boards/O02-Card.html', 200), ('/p/promo/og/shared/tokens.css', 200),
                           ('/p/promo/og/assets/img/a.txt', 200), ('/p/promo/boards/P01-Join.html', 200),
                           ('/p/promo/og/boards/../canvas.json', 404), ('/p/promo/og/nope/', 404),
                           ('/p/promo/og/og/', 404), ('/p/promo/shared/', 404)):
            self.assertEqual(self.request('GET', path)[0], want, path)
        self.assertEqual(self.request('GET', '/p/promo/og/shared/tokens.css')[2], b':root{--og:1}')
        self.assertEqual(json.loads(self.request('GET', '/p/promo/og/canvas.json')[2])['boards'].keys(),
                         {'P01-Join.html', 'O02-Card.html'})

        st, hdrs, _ = self.request('GET', '/p/og/')            # an old link follows the move
        self.assertEqual((st, hdrs.get('Location')), (302, '/p/promo/og/'))
        self.assertEqual(self.request('GET', '/p/og/canvas.json')[0], 404)

        st, d = self.post('/p/promo/og/api/layout', {'board': 'O02-Card.html', 'x': 77, 'y': 5})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.read_json(os.path.join(self.promo, 'og', 'canvas.json'))['boards']['O02-Card.html']['x'], 77)

        st, d = self.post('/api/move', {'project': 'p', 'idea': 'promo/og', 'out': True, 'force': True})
        self.assertEqual((st, d), (200, {'ok': True, 'idea': 'og'}))
        self.assertEqual([i['name'] for i in self.index()['ideas']], ['og', 'promo'])
        self.assertEqual(self.request('GET', '/p/promo/og/')[0], 404)

    def test_new_idea_holds_the_moved_one_and_failures_leave_nothing(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, d = self.post('/api/move', {'project': 'p', 'idea': 'og', 'new': 'marketing'})
        self.assertEqual((st, d), (200, {'ok': True, 'idea': 'marketing/og'}))
        self.assertTrue(os.path.isfile(os.path.join(self.design, 'marketing', 'canvas.json')))
        for body, text in (({'project': 'p', 'idea': 'promo', 'new': 'marketing'}, 'already exists'),
                           ({'project': 'p', 'idea': 'nope', 'new': 'fresh'}, 'No idea named nope'),
                           ({'project': 'p', 'idea': 'promo', 'new': '../x'}, 'Not an idea name'),
                           ({'project': 'p', 'idea': 'promo', 'new': 'api'}, 'Not an idea name'),
                           ({'project': 'p', 'idea': 'promo'}, 'Say where it goes'),
                           ({'project': 'zzz', 'idea': 'promo', 'into': 'marketing'}, 'No such project')):
            st, d = self.post('/api/move', body)
            self.assertIn(st, (400, 404), body)
            self.assertIn(text, d['error'], body)
        self.assertFalse(os.path.exists(os.path.join(self.design, 'fresh')))
        self.assertTrue(os.path.isdir(self.promo))

    def test_quiet_period(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        os.utime(os.path.join(self.og, 'canvas.json'), None)
        st, d = self.post('/api/move', {'project': 'p', 'idea': 'og', 'into': 'promo'})
        self.assertEqual(st, 400)
        self.assertIn('Try again when the agent is done', d['error'])
        self.assertTrue(os.path.isdir(self.og))

    def test_needs_same_origin_and_local_mode(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, _ = self.post('/api/move', {'project': 'p', 'idea': 'og', 'into': 'promo'}, headers={})
        self.assertEqual(st, 403)
        st, _ = self.post('/api/move', {'project': 'p', 'idea': 'og', 'into': 'promo'}, headers={'Origin': 'http://evil.example'})
        self.assertEqual(st, 403)
        self.assertTrue(os.path.isdir(self.og))

    def test_read_only_and_share_never_move(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=True)
        st, d = self.post('/api/move', {'project': 'p', 'idea': 'og', 'into': 'promo'})
        self.assertEqual((st, d['error']), (403, 'Read-only'))
        self.assertTrue(os.path.isdir(self.og))

    def test_single_root_and_share_keys(self):
        canvas.move_idea(self.design, 'og', into='promo')
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True, read_only=False)
        for path, want in (('/promo/og/', 200), ('/promo/og/boards/O02-Card.html', 200), ('/promo/og/canvas.json', 200),
                           ('/promo/og/shared/tokens.css', 200), ('/promo/', 200)):
            self.assertEqual(self.request('GET', path)[0], want, path)
        st, hdrs, _ = self.request('GET', '/og/')
        self.assertEqual((st, hdrs.get('Location')), (302, '/promo/og/'))
        st, d = self.post('/api/move', {'idea': 'promo/og', 'out': True, 'force': True})
        self.assertEqual((st, d), (200, {'ok': True, 'idea': 'og'}))

    def test_share_key_of_a_section_opens_only_that_section(self):
        canvas.move_idea(self.design, 'og', into='promo')
        tok = 'tok123'
        self.start_server(canvas.RegistryHandler, share_token=tok, share_edit=False, read_only=False,
                          frozen_roots=[{'name': 'p', 'path': self.design}], share_host='127.0.0.1', share_until=0.0)
        key = lambda scope: canvas.hmac.new(tok.encode(), ('assets:' + '/'.join(scope)).encode(), canvas.hashlib.sha256).hexdigest()[:32]
        sec, par = key(['p', 'promo/og']), key(['p', 'promo'])
        self.assertEqual(self.request('GET', f'/_k/{sec}/p/promo/og/boards/O02-Card.html')[0], 200)
        self.assertEqual(self.request('GET', f'/_k/{sec}/p/promo/og/shared/tokens.css')[0], 200)
        self.assertEqual(self.request('GET', f'/_k/{par}/p/promo/boards/P01-Join.html')[0], 200)
        for path in (f'/_k/{par}/p/promo/og/boards/O02-Card.html', f'/_k/{sec}/p/promo/boards/P01-Join.html',
                     f'/_k/{sec}/p/promo/og/canvas.json'):
            self.assertIn(self.request('GET', path)[0], (401, 404), path)


class SectionEvents(TempHomeCase):
    def test_a_section_event_reaches_its_parent_and_the_dashboard_once(self):
        got = []

        class W:
            def __init__(self, name):
                self.name = name

            def write(self, data):
                got.append((self.name, json.loads(data.decode().split('data: ', 1)[1])))

            def flush(self):
                pass
        ws = {k: W(k) for k in ('p/promo', 'p/promo/og', canvas.DASH_SSE_KEY)}
        for k, w in ws.items():
            self.assertTrue(canvas._add_sse(k, w))
            self.addCleanup(canvas._rm_sse, k, w)
        canvas._SSE_PARENT['p/promo/og'] = 'p/promo'
        self.addCleanup(canvas._SSE_PARENT.clear)
        canvas._broadcast('p/promo/og', {'type': 'board', 'file': 'O02-Card.html'})
        self.assertCountEqual(got, [
            ('p/promo/og', {'type': 'board', 'file': 'O02-Card.html'}),
            ('p/promo', {'type': 'board', 'file': 'O02-Card.html', 'section': 'og'}),
            (canvas.DASH_SSE_KEY, {'type': 'board', 'file': 'O02-Card.html', 'section': 'og', 'key': 'p/promo'}),
        ])


class SectionsViewer(ServerCase):
    """What the server tells the canvas page about sections."""

    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.promo = self.make_idea(self.design, 'promo', boards=('P01-Join.html',))
        self.make_idea(self.design, 'og', boards=('O02-Card.html',))
        self.make_idea(self.design, 'zed')
        canvas.move_idea(self.design, 'zed', into='promo')
        canvas.move_idea(self.design, 'og', into='promo')
        self.write_json(os.path.join(self.data_dir, 'roots.json'), {'roots': [{'name': 'p', 'path': self.design}]})

    def info(self, path, headers=None):
        st, hdrs, body = self.request('GET', path, headers=headers)
        self.assertEqual(st, 200, path)
        html = body.decode()
        raw = html.split('var CANVAS_INFO=', 1)[1].split(';</script>', 1)[0]
        # the injected script is covered by the page's CSP hash list
        self.assertIn(canvas._script_hashes(html).split(' ')[0], hdrs['Content-Security-Policy'])
        return json.loads(raw)

    def test_parent_page_lists_its_sections_in_order(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        self.assertEqual(self.info('/p/promo/'), {'idea': 'promo', 'sections': ['zed', 'og']})
        self.assertEqual(self.info('/p/promo/og/'), {'idea': 'promo/og'})   # a section has no sections of its own

    def test_single_root_and_plain_idea(self):
        self.make_idea(self.design, 'plain')
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True, read_only=False)
        self.assertEqual(self.info('/promo/')['sections'], ['zed', 'og'])
        self.assertEqual(self.info('/promo/zed/'), {'idea': 'promo/zed'})
        self.assertEqual(self.info('/plain/'), {'idea': 'plain'})

    def test_share_page_gets_a_key_per_section(self):
        tok = 'tok123'
        self.start_server(canvas.RegistryHandler, share_token=tok, share_edit=False, read_only=False,
                          frozen_roots=[{'name': 'p', 'path': self.design}], share_host='127.0.0.1', share_until=0.0)
        info = self.info('/p/promo/', headers={'Cookie': 'canvas_token=' + tok})
        self.assertEqual(set(info['prefix']), {'zed', 'og'})
        self.assertNotEqual(info['prefix']['og'], info['prefix']['zed'])
        self.assertEqual(self.request('GET', info['prefix']['og'] + '/p/promo/og/boards/O02-Card.html')[0], 200)
        self.assertIn(self.request('GET', info['prefix']['og'] + '/p/promo/zed/canvas.json')[0], (401, 404))

    def test_viewer_page_has_the_section_ui(self):
        with open(canvas.VIEWER_PATH, encoding='utf-8') as f:
            page = f.read()
        for needle in ('id="outline"', 'id="rej-btn"', 'function mergeSections', "secBase(sec) + '/api/layout'",
                       "post('/api/move'", 'b.x - (b._dx', ):
            self.assertIn(needle.replace('b.x - (b._dx', 'x - (b._dx'), page, needle)
