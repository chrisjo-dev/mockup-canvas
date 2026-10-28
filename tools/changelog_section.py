"""Print the CHANGELOG.md section of one version, for the release notes.

    python3 tools/changelog_section.py v0.5.0 [CHANGELOG.md] > notes.md

The section is the text under "## [0.5.0]" up to the next "## [" heading or the link
definitions at the end. Exits 1 when the version has no section or the section is empty.
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def section(text, version):
    """The body of the "## [version]" section, or None when there is none."""
    version = version[1:] if version.startswith('v') else version
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith('## [' + version + ']')), None)
    if start is None:
        return None
    body = []
    for line in lines[start + 1:]:
        if line.startswith('## [') or re.match(r'\[[^\]]+\]: ', line):
            break
        body.append(line)
    out = '\n'.join(body).strip()
    return out + '\n' if out else None


def main(argv):
    if not 1 <= len(argv) <= 2:
        print('Usage: changelog_section.py <version or vX.Y.Z tag> [CHANGELOG.md]', file=sys.stderr)
        return 2
    path = argv[1] if len(argv) == 2 else os.path.join(REPO, 'CHANGELOG.md')
    with open(path, encoding='utf-8') as f:
        notes = section(f.read(), argv[0])
    if notes is None:
        print(f'Error: {path} has no section for {argv[0]}', file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
