"""CLI commands: new, add, link, status, group, artifact, roots, check, export, migration."""
import os
import shutil
import unittest
from unittest import mock

from helpers import SCRIPTS, TempHomeCase, board_html, canvas


class NewAddCommands(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'proj', 'design')
        self.idea = os.path.join(self.design, 'demo')

    def test_new_creates_structure_and_registers_root(self):
        r = self.run_cli('new', self.design, 'demo')
        self.assertEqual(r.returncode, 0, r.stderr)
        for sub in ('boards', 'assets', 'render', 'shared'):
            self.assertTrue(os.path.isdir(os.path.join(self.idea, sub)))
        self.assertEqual(self.read_json(os.path.join(self.idea, 'canvas.json')),
                         {'boards': {}, 'groups': [], 'links': []})
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'shared', 'tokens.css')))
        with open(os.path.join(self.idea, '.gitignore')) as f:
            self.assertEqual(f.read(), 'render/\n')
        roots = self.read_json(os.path.join(self.data_dir, 'roots.json'))
        self.assertEqual(roots, {'roots': [{'name': 'proj', 'path': '~/proj/design'}]})
        self.assertIn('Registered design folder: proj', r.stdout)
        # Second run neither re-registers nor fails
        r2 = self.run_cli('new', self.design, 'demo')
        self.assertEqual(r2.returncode, 0)
        self.assertNotIn('Registered design folder', r2.stdout)

    def test_add_registers_board_with_size_and_group(self):
        self.run_cli('new', self.design, 'demo')
        src = os.path.join(self.tmp, 'D01-Home.html')
        with open(src, 'w') as f:
            f.write(board_html())
        r = self.run_cli('add', self.idea, src, '--group', 'current', '--size', 'tablet')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.idea, 'boards', 'D01-Home.html')))
        data = self.read_json(os.path.join(self.idea, 'canvas.json'))
        b = data['boards']['D01-Home.html']
        self.assertEqual((b['x'], b['y'], b['w'], b['h']), (0, 0, 768, 1024))
        self.assertEqual(b['group'], 'current')
        self.assertEqual(data['groups'], [{'id': 'current', 'label': 'current'}])

        # A second board goes to the right of the first one
        with open(os.path.join(self.idea, 'boards', 'D02-Next.html'), 'w') as f:
            f.write(board_html())
        self.run_cli('add', self.idea, os.path.join(self.idea, 'boards', 'D02-Next.html'), '--size', '200x300')
        b2 = self.read_json(os.path.join(self.idea, 'canvas.json'))['boards']['D02-Next.html']
        self.assertEqual((b2['x'], b2['w'], b2['h']), (768 + 40, 200, 300))

        r = self.run_cli('add', self.idea, src)
        self.assertIn('Already registered', r.stdout)

    def test_add_refuses_to_overwrite_different_file(self):
        self.run_cli('new', self.design, 'demo')
        with open(os.path.join(self.idea, 'boards', 'D01-Home.html'), 'w') as f:
            f.write('original')
        src = os.path.join(self.tmp, 'D01-Home.html')
        with open(src, 'w') as f:
            f.write('different')
        r = self.run_cli('add', self.idea, src)
        self.assertIn('a different file already exists', r.stdout)
        with open(os.path.join(self.idea, 'boards', 'D01-Home.html')) as f:
            self.assertEqual(f.read(), 'original')

    def test_add_rejects_unknown_size(self):
        self.run_cli('new', self.design, 'demo')
        r = self.run_cli('add', self.idea, 'x.html', '--size', 'huge')
        self.assertIn('Unknown size', r.stdout)


class BoardCommands(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'proj', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')

    def test_link_normalizes_board_paths(self):
        r = self.run_cli('link', self.idea, 'boards/A01-One.html', 'A02-Two', '--label', 'Next')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read_json(self.cj)['links'],
                         [{'from': 'A01-One.html', 'to': 'A02-Two.html', 'label': 'Next'}])
        r = self.run_cli('link', self.idea, 'A01-One.html', './boards/A02-Two.html')
        self.assertIn('Already linked', r.stdout)
        self.assertEqual(len(self.read_json(self.cj)['links']), 1)

    def test_link_unknown_board_fails(self):
        r = self.run_cli('link', self.idea, 'A01-One.html', 'boards/Z99-Missing.html')
        self.assertEqual(r.returncode, 1)
        self.assertIn('Z99-Missing.html', r.stderr)
        self.assertEqual(self.read_json(self.cj)['links'], [])

    def test_status_set_and_clear(self):
        r = self.run_cli('status', self.idea, 'boards/A01-One.html', 'approved', '--note', 'ok by user')
        self.assertEqual(r.returncode, 0, r.stderr)
        b = self.read_json(self.cj)['boards']['A01-One.html']
        self.assertEqual((b['status'], b['note']), ('approved', 'ok by user'))
        self.run_cli('status', self.idea, 'A01-One', 'draft')
        b = self.read_json(self.cj)['boards']['A01-One.html']
        self.assertNotIn('status', b)
        self.assertNotIn('note', b)

    def test_status_errors_exit_1(self):
        self.assertEqual(self.run_cli('status', self.idea, 'Nope.html', 'approved').returncode, 1)
        self.assertEqual(self.run_cli('status', self.idea, 'A01-One.html', 'maybe').returncode, 1)

    def test_group(self):
        r = self.run_cli('group', self.idea, 'boards/A02-Two.html', 'old drafts')
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.read_json(self.cj)
        self.assertEqual(data['boards']['A02-Two.html']['group'], 'old drafts')
        self.assertIn({'id': 'old drafts', 'label': 'old drafts'}, data['groups'])
        self.assertEqual(self.run_cli('group', self.idea, 'Nope', 'g').returncode, 1)

    def test_artifact(self):
        self.assertEqual(self.run_cli('artifact', self.idea).stdout.strip(), '(none)')
        self.run_cli('artifact', self.idea, 'https://example.com/a/1')
        self.assertEqual(self.read_json(self.cj)['artifact_url'], 'https://example.com/a/1')
        self.assertEqual(self.run_cli('artifact', self.idea).stdout.strip(), 'https://example.com/a/1')


class CheckCommand(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'proj', 'design')
        self.idea = self.make_idea(self.design, 'demo', boards=('A01-One.html', 'A02-Two.html'),
                                   links=[{'from': 'A01-One.html', 'to': 'A02-Two.html'}])
        self.cj = os.path.join(self.idea, 'canvas.json')

    def test_clean_idea_exits_0(self):
        r = self.run_cli('check', self.idea)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('0 problems', r.stdout)

    def assertProblem(self, text):
        r = self.run_cli('check', self.idea)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(text, r.stdout)

    def test_missing_board_file(self):
        os.remove(os.path.join(self.idea, 'boards', 'A02-Two.html'))
        self.assertProblem('missing file in boards: A02-Two.html')

    def test_broken_reference(self):
        with open(os.path.join(self.idea, 'boards', 'A01-One.html'), 'w') as f:
            f.write(board_html('<img src="../assets/nope.png">'))
        self.assertProblem('broken reference -> ../assets/nope.png')

    def test_unregistered_board(self):
        with open(os.path.join(self.idea, 'boards', 'A03-Extra.html'), 'w') as f:
            f.write(board_html())
        self.assertProblem('not registered in canvas.json: A03-Extra.html')

    def test_overlap(self):
        data = self.read_json(self.cj)
        data['boards']['A02-Two.html']['x'] = 100
        self.write_json(self.cj, data)
        self.assertProblem('overlap')

    def test_dangling_link(self):
        data = self.read_json(self.cj)
        data['links'].append({'from': 'boards/A01-One.html', 'to': 'A02-Two.html'})
        self.write_json(self.cj, data)
        self.assertProblem('link from is not a registered board')

    def test_forbidden_chars_only_with_config(self):
        with open(os.path.join(self.idea, 'boards', 'A01-One.html'), 'w', encoding='utf-8') as f:
            f.write(board_html('a—b'))
        self.assertEqual(self.run_cli('check', self.idea).returncode, 0)
        self.write_json(os.path.join(self.data_dir, 'config.json'), {'forbidden_chars': ['—']})
        self.assertProblem('forbidden character (U+2014) found: A01-One.html')


class RootsCommand(TempHomeCase):
    def test_add_list_remove_scan(self):
        d1 = os.path.join(self.home, 'work', 'alpha', 'design')
        d2 = os.path.join(self.home, 'work', 'beta', 'design')
        self.make_idea(d1, 'idea1')
        self.make_idea(d2, 'idea2')
        roots_json = os.path.join(self.data_dir, 'roots.json')

        r = self.run_cli('roots', 'add', d1, '--name', 'a')
        self.assertIn('Registered: a', r.stdout)
        r = self.run_cli('roots', 'add', d1)
        self.assertIn('Already registered', r.stdout)
        r = self.run_cli('roots', 'list')
        self.assertIn('a', r.stdout)
        self.assertIn('(1 ideas)', r.stdout)

        r = self.run_cli('roots', 'scan', os.path.join(self.home, 'work'))
        self.assertIn('Skipped (already registered): alpha', r.stdout)
        self.assertIn('Added: beta', r.stdout)
        names = [x['name'] for x in self.read_json(roots_json)['roots']]
        self.assertEqual(names, ['a', 'beta'])

        r = self.run_cli('roots', 'remove', 'a')
        self.assertIn('Removed: a', r.stdout)
        r = self.run_cli('roots', 'remove', 'a')
        self.assertIn('Not found: a', r.stdout)
        self.assertEqual([x['name'] for x in self.read_json(roots_json)['roots']], ['beta'])

    def test_save_keeps_symlinked_registry(self):
        real = os.path.join(self.tmp, 'synced', 'roots.json')
        self.write_json(real, {'roots': []})
        os.makedirs(self.data_dir, exist_ok=True)
        link = os.path.join(self.data_dir, 'roots.json')
        os.symlink(real, link)
        d1 = os.path.join(self.home, 'p', 'design')
        self.make_idea(d1, 'i')
        self.run_cli('roots', 'add', d1)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(self.read_json(real)['roots'][0]['name'], 'p')

    def test_legacy_registry_migrates_once(self):
        skill = os.path.join(self.tmp, 'old-skill')
        shutil.copytree(SCRIPTS, os.path.join(skill, 'scripts'))
        legacy = {'roots': [{'name': 'old', 'path': '~/old/design'}]}
        self.write_json(os.path.join(skill, 'roots.json'), legacy)
        script = os.path.join(skill, 'scripts', 'canvas.py')
        r = self.run_cli('roots', 'list', script=script)
        self.assertIn('Migrated project registry', r.stderr)
        self.assertEqual(self.read_json(os.path.join(self.data_dir, 'roots.json')), legacy)
        r = self.run_cli('roots', 'list', script=script)
        self.assertNotIn('Migrated', r.stderr)


class ExportCommand(TempHomeCase):
    def test_export_escapes_script_close(self):
        idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo')
        cj = os.path.join(idea, 'canvas.json')
        data = self.read_json(cj)
        evil = '</script><script>alert(1)</script>'
        data['boards']['A01-One.html']['title'] = evil
        data['boards']['A01-One.html']['note'] = 'line sep'
        self.write_json(cj, data)
        out = os.path.join(self.tmp, 'out')
        r = self.run_cli('export', idea, out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Check OK', r.stdout)
        with open(os.path.join(out, 'index.html'), encoding='utf-8') as f:
            html = f.read()
        self.assertNotIn(evil, html)
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('\\u003c/script>\\u003cscript>alert(1)\\u003c/script>', html)
        self.assertNotIn(' ', html)
        self.assertTrue(os.path.isfile(os.path.join(out, 'boards', 'A01-One.html')))


class Usage(TempHomeCase):
    def test_help_and_unknown_command(self):
        r = self.run_cli('--help')
        self.assertIn('Usage: python3 canvas.py <command>', r.stdout)
        r = self.run_cli('frobnicate')
        self.assertIn('Unknown command: frobnicate', r.stdout)


class RootsNoArgs(TempHomeCase):
    """canvas.py roots with no subcommand lists projects (same as roots list)."""

    def test_no_args_lists_projects(self):
        d = os.path.join(self.home, 'myproj', 'design')
        self.make_idea(d, 'idea1')
        self.run_cli('roots', 'add', d, '--name', 'myproj')
        r = self.run_cli('roots')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('myproj', r.stdout)
        self.assertIn('(1 ideas)', r.stdout)

    def test_no_args_empty_registry(self):
        r = self.run_cli('roots')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('No projects registered', r.stdout)

    def test_help_flag_shows_usage(self):
        r = self.run_cli('roots', '--help')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Usage:', r.stdout)
        self.assertIn('list projects', r.stdout)


class ChromeResolution(unittest.TestCase):
    """_resolve_chrome follows the documented priority order."""

    def test_env_var_takes_priority(self):
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': '/custom/chrome'}):
            with mock.patch('os.path.isfile', return_value=False):
                with mock.patch('shutil.which', return_value=None):
                    self.assertEqual(canvas._resolve_chrome(), '/custom/chrome')

    def test_env_var_empty_falls_through(self):
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': '   '}):
            with mock.patch('os.path.isfile', return_value=False):
                with mock.patch('shutil.which', return_value=None):
                    self.assertIsNone(canvas._resolve_chrome())

    def test_macos_paths_checked_in_order(self):
        # Only the Chromium app path (index 1) exists.
        target = canvas._MACOS_CHROME_PATHS[1]
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': ''}):
            with mock.patch('os.path.isfile', side_effect=lambda p: p == target):
                with mock.patch('shutil.which', return_value=None):
                    self.assertEqual(canvas._resolve_chrome(), target)

    def test_which_fallback_order(self):
        # chromium is tried; google-chrome must appear before chromium in the list.
        called = []
        def fake_which(name):
            called.append(name)
            return '/usr/bin/chromium' if name == 'chromium' else None
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': ''}):
            with mock.patch('os.path.isfile', return_value=False):
                with mock.patch('shutil.which', side_effect=fake_which):
                    result = canvas._resolve_chrome()
        self.assertEqual(result, '/usr/bin/chromium')
        self.assertIn('google-chrome', called)
        self.assertLess(called.index('google-chrome'), called.index('chromium'))

    def test_returns_none_when_nothing_found(self):
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': ''}):
            with mock.patch('os.path.isfile', return_value=False):
                with mock.patch('shutil.which', return_value=None):
                    self.assertIsNone(canvas._resolve_chrome())


if __name__ == '__main__':
    unittest.main()
