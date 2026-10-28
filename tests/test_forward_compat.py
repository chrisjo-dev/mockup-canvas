"""Forward compatibility: saves keep fields a newer version wrote into roots.json and canvas.json."""
import json
import os
import unittest

from helpers import ServerCase, canvas


class RootsKeepUnknownFields(ServerCase):
    def setUp(self):
        super().setUp()
        self.d_a = os.path.join(self.home, 'work', 'alpha', 'design')
        self.d_b = os.path.join(self.home, 'work', 'beta', 'design')
        self.make_idea(self.d_a, 'ideaA')
        self.make_idea(self.d_b, 'ideaB')
        self.roots_json = os.path.join(self.data_dir, 'roots.json')
        self.write_json(self.roots_json, {
            'roots': [{'name': 'alpha', 'path': self.d_a, 'color': 'red', 'pinned': True},
                      {'name': 'beta', 'path': self.d_b, 'color': 'blue'}],
            'future': {'version': 9, 'flags': ['x']},
        })
        self.start_server(canvas.RegistryHandler, share_token='', share_edit=True, read_only=False)

    def post(self, action, body):
        status, _, raw = self.request('POST', '/api/roots/' + action, body, headers=self.origin())
        self.assertEqual(status, 200, raw)

    def entry(self, name):
        return next(r for r in self.read_json(self.roots_json)['roots'] if r['name'] == name)

    def assert_kept(self, name='alpha'):
        data = self.read_json(self.roots_json)
        self.assertEqual(data['future'], {'version': 9, 'flags': ['x']})
        e = self.entry(name)
        self.assertEqual((e['color'], e['pinned']), ('red', True))

    def test_collection_set_keeps_them(self):
        self.post('collection', {'key': 'alpha/ideaA', 'collection': 'Lily'})
        self.assert_kept()
        self.assertEqual(self.read_json(self.roots_json)['collections'], {'Lily': ['alpha/ideaA']})

    def test_rename_keeps_them_on_the_renamed_entry(self):
        self.post('rename', {'name': 'alpha', 'new_name': 'omega'})
        self.assert_kept('omega')
        self.assertEqual(self.entry('beta')['color'], 'blue')

    def test_add_and_remove_keep_them(self):
        gamma = os.path.join(self.home, 'work', 'gamma', 'design')
        self.make_idea(gamma, 'g')
        self.post('add', {'path': gamma})
        self.assert_kept()
        self.assertEqual(set(self.entry('gamma')), {'name', 'path'})
        self.post('remove', {'name': 'beta'})
        self.assert_kept()

    def test_cli_saves_keep_them(self):
        gamma = os.path.join(self.home, 'work', 'gamma', 'design')
        self.make_idea(gamma, 'g')
        r = self.run_cli('roots', 'add', gamma)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cli('roots', 'remove', 'beta')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_kept()

    def test_bad_known_values_are_still_dropped(self):
        data = self.read_json(self.roots_json)
        data['roots'].append({'name': '', 'path': self.d_b, 'color': 'green'})
        data['collections'] = {'Lily': ['alpha', 3], '': ['beta']}
        self.write_json(self.roots_json, data)
        self.post('collection', {'key': 'beta', 'collection': 'Manito'})
        after = self.read_json(self.roots_json)
        self.assertEqual([r['name'] for r in after['roots']], ['alpha', 'beta'])
        self.assertEqual(after['collections'], {'Lily': ['alpha'], 'Manito': ['beta']})
        self.assert_kept()


class CanvasKeepsUnknownFields(ServerCase):
    """canvas.json saves already read, change, and write the whole file; this pins that down."""

    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'p', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')
        data = self.read_json(self.cj)
        data['future'] = {'layers': [1, 2]}
        data['boards']['A01-One.html']['tags'] = ['hero']
        self.write_json(self.cj, data)

    def assert_kept(self):
        data = self.read_json(self.cj)
        self.assertEqual(data['future'], {'layers': [1, 2]})
        self.assertEqual(data['boards']['A01-One.html']['tags'], ['hero'])

    def test_layout_save_keeps_them(self):
        self.start_server(canvas.CanvasHandler, design_dir=self.design,
                          share_token='', share_edit=True, read_only=False)
        status, _, body = self.request('POST', '/demo/api/layout', {'board': 'A01-One.html', 'x': 7, 'y': 8},
                                       headers=self.origin())
        self.assertEqual(status, 200, body)
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['x'], 7)
        self.assert_kept()

    def test_cli_saves_keep_them(self):
        for args in (('status', self.idea, 'A01-One.html', 'approved', '--note', 'ok'),
                     ('impl', self.idea, 'A01-One.html', '--route', '/home'),
                     ('comment', self.idea, 'A01-One.html', 'looks good'),
                     ('group', self.idea, 'A01-One.html', 'Main'),
                     ('link', self.idea, 'A01-One.html', 'A02-Two.html'),
                     ('artifact', self.idea, 'https://example.com/a')):
            r = self.run_cli(*args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assert_kept()
        b = self.read_json(self.cj)['boards']['A01-One.html']
        self.assertEqual((b['status'], b['impl']['route'], b['group']), ('approved', '/home', 'Main'))


if __name__ == '__main__':
    unittest.main()
