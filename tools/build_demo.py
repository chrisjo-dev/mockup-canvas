#!/usr/bin/env python3
"""Build the read-only live demo for GitHub Pages into _site/ (stdlib only).

Exports examples/trailmate with `canvas.py export`, then adds search and AI crawler
metadata to the <head> of index.html (no visible UI changes), robots.txt, sitemap.xml,
and a copy of llms.txt.

Usage: python3 tools/build_demo.py [output dir]   (default: _site)
"""
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = 'https://chrisjo-dev.github.io/mockup-canvas/'
REPO_URL = 'https://github.com/chrisjo-dev/mockup-canvas'
IMAGE = 'https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/social-preview.png'
TITLE = 'mockup-canvas live demo: AI-drawn HTML mockups on a local canvas'
DESCRIPTION = ('Read-only demo of mockup-canvas, a free, open-source (MIT) Claude Code plugin and Codex '
               'skill set that draws UI mockups as HTML artboards on a local Figma-like canvas, reviews '
               'them, and builds approved screens into app code. This page shows the six-screen '
               'TrailMate example.')


def head_tags():
    ld = {
        '@context': 'https://schema.org',
        '@type': ['SoftwareSourceCode', 'SoftwareApplication'],
        'name': 'mockup-canvas',
        'description': DESCRIPTION,
        'url': SITE_URL,
        'codeRepository': REPO_URL,
        'license': 'https://opensource.org/licenses/MIT',
        'programmingLanguage': 'Python',
        'applicationCategory': 'DeveloperApplication',
        'operatingSystem': 'macOS, Linux',
        'image': IMAGE,
        'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'},
        'author': {'@type': 'Person', 'name': 'chrisjo-dev', 'url': 'https://github.com/chrisjo-dev'},
    }
    # "</" inside a script element would end it early
    ld_json = json.dumps(ld, ensure_ascii=False, indent=2).replace('</', '<\\/')
    a = lambda s: html.escape(s, quote=True)
    return '\n'.join([
        f'  <meta name="description" content="{a(DESCRIPTION)}">',
        f'  <link rel="canonical" href="{SITE_URL}">',
        '  <meta name="robots" content="index, follow">',
        '  <meta property="og:type" content="website">',
        '  <meta property="og:site_name" content="mockup-canvas">',
        f'  <meta property="og:title" content="{a(TITLE)}">',
        f'  <meta property="og:description" content="{a(DESCRIPTION)}">',
        f'  <meta property="og:url" content="{SITE_URL}">',
        f'  <meta property="og:image" content="{IMAGE}">',
        '  <meta property="og:image:width" content="1280">',
        '  <meta property="og:image:height" content="640">',
        '  <meta name="twitter:card" content="summary_large_image">',
        f'  <meta name="twitter:title" content="{a(TITLE)}">',
        f'  <meta name="twitter:description" content="{a(DESCRIPTION)}">',
        f'  <meta name="twitter:image" content="{IMAGE}">',
        f'  <link rel="alternate" type="text/plain" title="llms.txt" href="{SITE_URL}llms.txt">',
        '  <script type="application/ld+json">\n' + ld_json + '\n  </script>',
        '',
    ])


ROBOTS = '''User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: {site}sitemap.xml
'''

SITEMAP = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{site}</loc></url>
  <url><loc>{site}llms.txt</loc></url>
</urlset>
'''


def main():
    out = os.path.realpath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, '_site'))
    if os.path.exists(out):
        shutil.rmtree(out)
    canvas_py = os.path.join(REPO, 'skills', 'mockup-canvas', 'scripts', 'canvas.py')
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, MOCKUP_CANVAS_HOME=home)
        subprocess.run([sys.executable, canvas_py, 'export',
                        os.path.join(REPO, 'examples', 'trailmate'), out], check=True, env=env)

    index = os.path.join(out, 'index.html')
    page = open(index, encoding='utf-8').read()
    if page.count('<title>Canvas</title>') != 1 or '</head>' not in page:
        sys.exit('Error: the exported index.html does not have the expected <head>')
    page = page.replace('<title>Canvas</title>', f'<title>{html.escape(TITLE)}</title>', 1)
    page = page.replace('</head>', head_tags() + '</head>', 1)
    with open(index, 'w', encoding='utf-8') as f:
        f.write(page)

    with open(os.path.join(out, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(ROBOTS.format(site=SITE_URL))
    with open(os.path.join(out, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(SITEMAP.format(site=SITE_URL))
    shutil.copyfile(os.path.join(REPO, 'llms.txt'), os.path.join(out, 'llms.txt'))
    print(f'Demo site: {out}')


if __name__ == '__main__':
    main()
