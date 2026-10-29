"""Delete with undo: ideas and boards move to <design dir>/.trash/, collections come back by name."""
import json
import os

from helpers import ServerCase, TempHomeCase, canvas


class TrashFunctions(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html', 'A03-Three.html'),
                                   links=[{'from': 'A01-One.html', 'to': 'A02-Two.html', 'label': 'next'},
                                          {'from': 'A02-Two.html', 'to': 'A03-Three.html'}])
        self.cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(self.cj)
        data['boards']['A02-Two.html'].update(status='approved', group='flow', note='ok',
                                              comments=[{'text': 'hi', 'by': 'r', 'created': 't'}])
        self.write_json(self.cj, data)
        self.before = self.read_json(self.cj)

    def test_board_moves_with_its_metadata_and_comes_back(self):
        thumbs = os.path.join(self.idea, 'render', '.thumbs')
        os.makedirs(thumbs)
        for n in ('A02-Two-390x844-3-8-abc.png', 'A02-Two-Extra-390x844-3-8-abc.png'):
            open(os.path.join(thumbs, n), 'w').close()
        tid = canvas.trash_board(self.design, 'demo', 'A02-Two.html')
        self.assertTrue(tid.startswith('demo/A02-Two-'))
        self.assertFalse(os.path.exists(os.path.join(self.idea, 'boards', 'A02-Two.html')))
        self.assertTrue(os.path.isfile(os.path.join(self.design, '.trash', tid + '.html')))
        data = self.read_json(self.cj)
        self.assertNotIn('A02-Two.html', data['boards'])
        self.assertEqual(data['links'], [])   # both arrows touched the board
        # only this board's thumbnails go; a board whose name starts the same keeps its own
        self.assertEqual(os.listdir(thumbs), ['A02-Two-Extra-390x844-3-8-abc.png'])

        r = canvas.restore_trash(self.design, tid)
        self.assertEqual(r, {'kind': 'board', 'idea': 'demo', 'file': 'A02-Two.html'})
        data = self.read_json(self.cj)
        self.assertEqual(data['boards']['A02-Two.html'], self.before['boards']['A02-Two.html'])
        self.assertCountEqual(data['links'], self.before['links'])
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'boards', 'A02-Two.html')))
        self.assertEqual(os.listdir(os.path.join(self.design, '.trash')), [])   # the empty idea folder is gone
        self.assertEqual(canvas.list_trash(self.design), [])

    def test_restore_skips_arrows_to_boards_that_are_gone(self):
        tid = canvas.trash_board(self.design, 'demo', 'A02-Two.html')
        canvas.trash_board(self.design, 'demo', 'A03-Three.html')
        canvas.restore_trash(self.design, tid)
        self.assertEqual(self.read_json(self.cj)['links'], [{'from': 'A01-One.html', 'to': 'A02-Two.html', 'label': 'next'}])

    def test_idea_moves_and_comes_back(self):
        tid = canvas.trash_idea(self.design, 'demo')
        self.assertRegex(tid, r'^demo-\d{8}T\d{6}Z$')
        self.assertFalse(os.path.exists(self.idea))
        self.assertEqual(canvas._list_ideas(self.design), [])   # .trash is not an idea
        self.assertEqual([e['kind'] for e in canvas.list_trash(self.design)], ['idea'])
        self.assertEqual(canvas.restore_trash(self.design, tid), {'kind': 'idea', 'idea': 'demo'})
        self.assertEqual(self.read_json(self.cj), self.before)

    def test_same_second_gets_a_new_name(self):
        a = canvas.trash_idea(self.design, 'demo')
        self.make_idea(self.design, 'demo')
        b = canvas.trash_idea(self.design, 'demo')
        self.assertNotEqual(a, b)
        self.assertEqual(len(canvas.list_trash(self.design)), 2)

    def test_restore_never_overwrites(self):
        tid = canvas.trash_idea(self.design, 'demo')
        self.make_idea(self.design, 'demo')
        with self.assertRaisesRegex(canvas.TrashError, 'already exists'):
            canvas.restore_trash(self.design, tid)
        self.assertTrue(os.path.isdir(os.path.join(self.design, '.trash', tid)))   # still in the trash

        bid = canvas.trash_board(self.design, 'demo', 'A01-One.html')
        with open(os.path.join(self.design, 'demo', 'boards', 'A01-One.html'), 'w') as f:
            f.write('new')
        with self.assertRaisesRegex(canvas.TrashError, 'already exists'):
            canvas.restore_trash(self.design, bid)
        with open(os.path.join(self.design, 'demo', 'boards', 'A01-One.html')) as f:
            self.assertEqual(f.read(), 'new')

    def test_board_of_a_trashed_idea_waits_for_the_idea(self):
        bid = canvas.trash_board(self.design, 'demo', 'A01-One.html')
        canvas.trash_idea(self.design, 'demo')
        with self.assertRaisesRegex(canvas.TrashError, 'Restore the idea demo first'):
            canvas.restore_trash(self.design, bid)

    def test_names_that_escape_are_refused(self):
        outside = self.make_idea(os.path.join(self.home, 'other'), 'victim')
        for idea in ('..', '.', '../other/victim', 'demo/../demo', '.trash', '', None, 'demo\\x', 'a\x00b'):
            with self.assertRaises(canvas.TrashError, msg=repr(idea)):
                canvas.trash_idea(self.design, idea)
        for f in ('../canvas.json', '..', 'boards/A01-One.html', '.hidden.html', 'A01-One', '/etc/passwd.html'):
            with self.assertRaises(canvas.TrashError, msg=f):
                canvas.trash_board(self.design, 'demo', f)
        for tid in ('../x-20260101T000000Z', 'demo/../../x-20260101T000000Z', '/etc-20260101T000000Z',
                    'demo', 'a/b/c-20260101T000000Z', '.trash-20260101T000000Z', ''):
            with self.assertRaises(canvas.TrashError, msg=tid):
                canvas.restore_trash(self.design, tid)
        self.assertTrue(os.path.isdir(outside))
        self.assertEqual(self.read_json(self.cj), self.before)

    def test_symlinked_idea_or_trash_is_refused(self):
        outside = self.make_idea(os.path.join(self.home, 'other'), 'victim')
        os.symlink(outside, os.path.join(self.design, 'link'))
        with self.assertRaises(canvas.TrashError):
            canvas.trash_idea(self.design, 'link')
        target = os.path.join(self.home, 'elsewhere')
        os.makedirs(target)
        os.symlink(target, os.path.join(self.design, '.trash'))
        with self.assertRaisesRegex(canvas.TrashError, 'not a plain folder'):
            canvas.trash_idea(self.design, 'demo')
        with self.assertRaisesRegex(canvas.TrashError, 'not a plain folder'):
            canvas.trash_board(self.design, 'demo', 'A01-One.html')
        self.assertEqual(os.listdir(target), [])
        self.assertEqual(self.read_json(self.cj), self.before)

    def test_linked_boards_folder_is_never_moved_into_or_out_of(self):
        bid = canvas.trash_board(self.design, 'demo', 'A01-One.html')
        boards = os.path.join(self.idea, 'boards')
        outside = os.path.join(self.home, 'outside-boards')
        os.rename(boards, outside)
        os.symlink(outside, boards)
        with self.assertRaisesRegex(canvas.TrashError, 'link out of the idea folder'):
            canvas.restore_trash(self.design, bid)
        self.assertNotIn('A01-One.html', os.listdir(outside))
        canvas.trash_board(self.design, 'demo', 'A02-Two.html')   # the entry goes, the linked file stays
        self.assertIn('A02-Two.html', os.listdir(outside))

    def test_failed_canvas_write_puts_the_file_back(self):
        real = canvas.save_canvas_atomic

        def boom(path, data):
            raise OSError('disk full')
        canvas.save_canvas_atomic = boom
        try:
            with self.assertRaises(OSError):
                canvas.trash_board(self.design, 'demo', 'A01-One.html')
        finally:
            canvas.save_canvas_atomic = real
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'boards', 'A01-One.html')))
        self.assertEqual(canvas.list_trash(self.design), [])
        self.assertEqual(self.read_json(self.cj), self.before)

    def test_cli_round_trip(self):
        r = self.run_cli('trash', self.idea, 'A02-Two')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Moved to the trash: demo/A02-Two-', r.stdout)
        r = self.run_cli('trash', '--list', self.design)
        tid = r.stdout.split()[0]
        self.assertIn('board', r.stdout)
        r = self.run_cli('restore', self.design, tid)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read_json(self.cj)['boards'].keys(), self.before['boards'].keys())
        r = self.run_cli('trash', self.idea)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.idea))
        r = self.run_cli('restore', self.design, '../etc-20260101T000000Z')
        self.assertEqual(r.returncode, 1)
        self.assertIn('Not a trash id', r.stderr)


class TrashApi(ServerCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {'roots': [{'name': 'p', 'path': self.design}]})

    def post(self, path, body, headers=None):
        status, _, data = self.request('POST', path, body, headers=self.origin() if headers is None else headers)
        return status, json.loads(data or b'{}')

    def test_registry_board_and_idea_round_trip(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, d = self.post('/api/trash', {'project': 'p', 'idea': 'demo', 'file': 'A01-One.html'})
        self.assertEqual((st, d['ok'], d['kind']), (200, True, 'board'))
        self.assertNotIn('A01-One.html', self.read_json(self.cj)['boards'])
        st, r = self.post('/api/restore', {'project': 'p', 'id': d['id']})
        self.assertEqual((st, r['ok']), (200, True))
        self.assertIn('A01-One.html', self.read_json(self.cj)['boards'])

        st, d = self.post('/api/trash', {'project': 'p', 'idea': 'demo'})
        self.assertEqual(d['kind'], 'idea')
        _, _, body = self.request('GET', '/api/index')
        self.assertEqual(json.loads(body)['ideas'], [])   # the trash never shows as an idea
        for path in ('/p/.trash/', '/p/.trash/' + d['id'] + '/', '/p/.trash/' + d['id'] + '/canvas.json',
                     '/p/.trash/' + d['id'] + '/boards/A01-One.html'):
            self.assertEqual(self.request('GET', path)[0], 404, path)
        st, r = self.post('/api/restore', {'project': 'p', 'id': d['id']})
        self.assertEqual(r['kind'], 'idea')
        self.assertTrue(os.path.isdir(self.idea))

    def test_single_root_and_bad_input(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token='', share_edit=True, read_only=False)
        self.assertEqual(self.request('GET', '/.trash/')[0], 404)
        st, d = self.post('/api/trash', {'idea': '../p/design/demo'})
        self.assertEqual((st, d['ok']), (400, False))
        st, d = self.post('/api/trash', {'idea': 'demo', 'file': '../canvas.json'})
        self.assertEqual(st, 400)
        st, d = self.post('/api/restore', {'id': '../../x-20260101T000000Z'})
        self.assertEqual(st, 400)
        st, d = self.post('/api/trash', {'idea': 'demo'})
        self.assertEqual((st, d['ok']), (200, True))

    def test_needs_same_origin(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        for headers in ({}, {'Origin': 'http://evil.example'}):
            st, _ = self.post('/api/trash', {'project': 'p', 'idea': 'demo'}, headers=headers)
            self.assertEqual(st, 403)
        self.assertTrue(os.path.isdir(self.idea))

    def test_share_and_read_only_never_move_files(self):
        token = 'tok_trash_1'
        cookie = {'Cookie': 'canvas_token=' + token}
        cases = [
            (canvas.CanvasHandler, dict(design_dir=self.design, share_token=token, share_edit=True, read_only=False)),
            (canvas.CanvasHandler, dict(design_dir=self.design, share_token=token, share_edit=False, read_only=False)),
            (canvas.CanvasHandler, dict(design_dir=self.design, share_token='', share_edit=True, read_only=True)),
            (canvas.RegistryHandler, dict(share_token=token, share_edit=True, read_only=False,
                                         frozen_roots=[{'name': 'p', 'path': self.design}])),
        ]
        for base, attrs in cases:
            self.start_server(base, **attrs)
            for path, body in (('/api/trash', {'project': 'p', 'idea': 'demo'}),
                               ('/api/trash', {'project': 'p', 'idea': 'demo', 'file': 'A01-One.html'}),
                               ('/api/restore', {'project': 'p', 'id': 'demo-20260101T000000Z'})):
                st, _ = self.post(path, body, headers=dict(self.origin(), **cookie))
                self.assertEqual(st, 403, (base.__name__, attrs, path))
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'boards', 'A01-One.html')))
        self.assertFalse(os.path.exists(os.path.join(self.design, '.trash')))

    def test_share_viewer_has_no_delete_menu(self):
        token = 'tok_trash_2'
        self.start_server(canvas.CanvasHandler, design_dir=self.design, share_token=token, share_edit=True, read_only=False)
        _, _, body = self.request('GET', '/demo/', headers={'Cookie': 'canvas_token=' + token})
        self.assertIn(b'var CANVAS_ASSET_PREFIX=', body)   # the viewer turns the menu off on this flag
        self.assertIn(b'const CAN_DELETE = !READ_ONLY && !SHARED', body)
        _, _, body = self.request('GET', '/', headers={'Cookie': 'canvas_token=' + token})
        self.assertNotIn(b'Delete idea', body)   # the management script is not on share pages


class CollectionDelete(ServerCase):
    def setUp(self):
        super().setUp()
        self.d = os.path.join(self.home, 'p', 'design')
        self.make_idea(self.d, 'one')
        self.make_idea(self.d, 'two')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {'roots': [{'name': 'p', 'path': self.d}], 'future': 1,
                                          'collections': {'Lily': ['p/one', 'p/two'], 'Other': ['p']}})

    def post(self, action, body):
        status, _, data = self.request('POST', '/api/roots/' + action, body, headers=self.origin())
        return status, json.loads(data)

    def test_delete_and_restore(self):
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)
        st, d = self.post('collection-delete', {'name': 'Lily'})
        self.assertEqual((st, d['keys']), (200, ['p/one', 'p/two']))
        data = self.read_json(self.roots_json)
        self.assertEqual(data['collections'], {'Other': ['p']})
        self.assertEqual(data['future'], 1)   # unknown keys survive
        self.assertTrue(os.path.isdir(os.path.join(self.d, 'one')))
        st, r = self.post('collection-restore', {'name': d['name'], 'keys': d['keys'] + ['gone/x', 'p']})
        self.assertEqual(st, 200)
        # keys of a project that is gone, or already in another collection, are dropped
        self.assertEqual(self.read_json(self.roots_json)['collections']['Lily'], ['p/one', 'p/two'])
        st, r = self.post('collection-restore', {'name': 'Lily', 'keys': ['p/one']})
        self.assertEqual(st, 409)
        st, r = self.post('collection-delete', {'name': 'Nope'})
        self.assertEqual(st, 404)

    def test_share_refuses(self):
        self.start_server(canvas.RegistryHandler, share_token='tok_c', share_edit=True, read_only=False,
                          frozen_roots=[{'name': 'p', 'path': self.d}])
        st, _ = self.post('collection-delete', {'name': 'Lily'})
        self.assertEqual(st, 403)
        self.assertIn('Lily', self.read_json(self.roots_json)['collections'])
