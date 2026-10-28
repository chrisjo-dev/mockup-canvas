"""tools/changelog_section.py: the release notes taken from CHANGELOG.md."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import REPO

TOOL = os.path.join(REPO, 'tools', 'changelog_section.py')
_spec = importlib.util.spec_from_file_location('changelog_section', TOOL)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

SAMPLE = """# Changelog

## [Unreleased]

- pending

## [1.2.0] - 2026-01-02

### Fixed

- Two.
- [1.2.0] in text is fine.

## [1.1.0] - 2026-01-01

- One.

## [1.0.0] - 2025-12-31

[Unreleased]: https://example.com/compare/v1.2.0...HEAD
[1.2.0]: https://example.com/v1.2.0
"""


class ChangelogSection(unittest.TestCase):
    def test_takes_the_section_up_to_the_next_heading(self):
        self.assertEqual(cs.section(SAMPLE, 'v1.2.0'), '### Fixed\n\n- Two.\n- [1.2.0] in text is fine.\n')
        self.assertEqual(cs.section(SAMPLE, '1.1.0'), '- One.\n')

    def test_missing_or_empty_section_is_none(self):
        self.assertIsNone(cs.section(SAMPLE, 'v9.9.9'))
        self.assertIsNone(cs.section(SAMPLE, 'v1.0.0'))   # stops at the link definitions
        self.assertIsNone(cs.section(SAMPLE, 'v1.2'))     # no prefix match on a shorter version

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'CHANGELOG.md')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE)
            ok = subprocess.run([sys.executable, TOOL, 'v1.1.0', path], capture_output=True, text=True)
            self.assertEqual((ok.returncode, ok.stdout), (0, '- One.\n'))
            bad = subprocess.run([sys.executable, TOOL, 'v9.9.9', path], capture_output=True, text=True)
            self.assertEqual((bad.returncode, bad.stdout), (1, ''))
            self.assertIn('no section for v9.9.9', bad.stderr)

    def test_repo_changelog_has_the_released_versions(self):
        with open(os.path.join(REPO, 'CHANGELOG.md'), encoding='utf-8') as f:
            self.assertIn('### Security', cs.section(f.read(), 'v0.5.0'))


if __name__ == '__main__':
    unittest.main()
