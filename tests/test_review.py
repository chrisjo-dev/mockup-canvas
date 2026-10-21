"""v0.2 review commands: PNG codec, snap, compare, impl, comment, check additions, viewer badges, install.sh."""
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import unittest
import zlib

from helpers import REPO, SCRIPTS, ServerCase, TempHomeCase, board_html, canvas


# ── PNG fixtures ───────────────────────────────────────────────────────────

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def encode_png(w, h, ch, rows, filters=(0,), color=None, depth=8, interlace=0):
    """Test-side encoder that applies the given filter types (cycled per row)."""
    out, prev = [], bytes(w * ch)
    for y, row in enumerate(rows):
        ft = filters[y % len(filters)]
        line = bytearray(len(row))
        for i, v in enumerate(row):
            a = row[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            pred = (0, a, b, (a + b) >> 1, _paeth(a, b, c))[ft]
            line[i] = (v - pred) & 255
        out.append(bytes([ft]) + bytes(line))
        prev = row

    def chunk(kind, body):
        return len(body).to_bytes(4, 'big') + kind + body + zlib.crc32(kind + body).to_bytes(4, 'big')
    if color is None:
        color = 2 if ch == 3 else 6
    ihdr = w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + bytes([depth, color, 0, 0, interlace])
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', zlib.compress(b''.join(out))) + chunk(b'IEND', b''))


def gradient_rows(w, h, ch, seed=0):
    return [bytes(((x * 7 + y * 13 + k * 51 + seed) * (k + 3)) & 255
                  for x in range(w) for k in range(ch)) for y in range(h)]


def solid_png(path, w, h, rgb):
    canvas.png_write(path, w, h, [bytes(rgb) * w for _ in range(h)])


class PngCodec(TempHomeCase):
    def test_all_five_filters_rgb_and_rgba(self):
        import random
        rnd = random.Random(1)
        for ch in (3, 4):
            rows = gradient_rows(17, 11, ch)
            # small random values make Paeth ties (pb == pc with b != c) common
            rows[5:] = [bytes(rnd.randrange(0, 21) for _ in range(17 * ch)) for _ in range(6)]
            for filters in ((0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)):
                p = os.path.join(self.tmp, f'f{ch}{filters}.png')
                with open(p, 'wb') as f:
                    f.write(encode_png(17, 11, ch, rows, filters))
                w, h, got_ch, got = canvas.png_read(p)
                self.assertEqual((w, h, got_ch), (17, 11, ch))
                self.assertEqual(got, rows, f'channels {ch}, filters {filters}')

    def test_write_then_read_roundtrip(self):
        rows = gradient_rows(33, 5, 3, seed=9)
        p = os.path.join(self.tmp, 'rt.png')
        canvas.png_write(p, 33, 5, rows)
        self.assertEqual(canvas.png_read(p), (33, 5, 3, rows))

    def test_rgba_alpha_is_dropped(self):
        rows = [bytes([1, 2, 3, 4, 5, 6, 7, 8])]
        self.assertEqual(canvas._rgb_rows(2, 4, rows), [bytes([1, 2, 3, 5, 6, 7])])

    def test_unsupported_formats_fail_clearly(self):
        rows = gradient_rows(4, 4, 3)
        cases = {
            'palette': (dict(color=3), 'color type 3'),
            'gray': (dict(color=0), 'color type 0'),
            '16bit': (dict(depth=16), 'bit depth 16'),
            'interlaced': (dict(interlace=1), 'interlaced'),
        }
        for name, (kw, msg) in cases.items():
            p = os.path.join(self.tmp, name + '.png')
            with open(p, 'wb') as f:
                f.write(encode_png(4, 4, 3, rows, **kw))
            with self.assertRaises(canvas.PngError) as cm:
                canvas.png_read(p)
            self.assertIn(msg, str(cm.exception))
        p = os.path.join(self.tmp, 'not.png')
        with open(p, 'wb') as f:
            f.write(b'GIF89a....')
        with self.assertRaisesRegex(canvas.PngError, 'not a PNG'):
            canvas.png_read(p)
        # A valid file with an invalid filter byte (7) on the first row
        good = encode_png(4, 4, 3, rows)
        body = zlib.compress(bytes([7]) + rows[0] + b''.join(b'\x00' + r for r in rows[1:]))
        idat = len(body).to_bytes(4, 'big') + b'IDAT' + body + zlib.crc32(b'IDAT' + body).to_bytes(4, 'big')
        p = os.path.join(self.tmp, 'badfilter.png')
        with open(p, 'wb') as f:
            f.write(good[:8 + 25] + idat + good[-12:])   # signature + IHDR, new IDAT, IEND
        with self.assertRaisesRegex(canvas.PngError, 'filter type 7'):
            canvas.png_read(p)

    def test_diff_counts_pixels_over_threshold(self):
        a = [bytes([100, 100, 100] * 4)]
        b = [bytes([100, 100, 100, 110, 100, 100, 100, 100, 200, 0, 0, 0])]
        out, bad = canvas._diff_rows(a, b, 4, 24)
        self.assertEqual(bad, 2)                       # +10 is under the threshold, +100 and -100 are over
        self.assertEqual(out[0][6:9], b'\xff\x00\xff')
        self.assertEqual(out[0][9:12], b'\xff\x00\xff')
        self.assertEqual(out[0][0:3], canvas._DIM[100:101] * 3)
        self.assertEqual(canvas._diff_rows(a, b, 4, 255)[1], 0)

    def test_resize_nearest(self):
        rows = [b'\x01\x01\x01\x02\x02\x02', b'\x03\x03\x03\x04\x04\x04']
        big = canvas._resize_nearest(rows, 2, 2, 4, 4)
        self.assertEqual(len(big), 4)
        self.assertEqual(big[0], b'\x01' * 6 + b'\x02' * 6)
        self.assertEqual(big[3], b'\x03' * 6 + b'\x04' * 6)


# ── fake Chrome: copies a fixture PNG chosen by URL substring ─────────────

FAKE_CHROME = r'''#!/usr/bin/env python3
import json, os, shutil, sys
args = sys.argv[1:]
with open(os.environ['FAKE_CHROME_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\n')
out = next(a.split('=', 1)[1] for a in args if a.startswith('--screenshot='))
url = args[-1]
for needle, png in json.loads(os.environ.get('FAKE_CHROME_MAP', '{}')).items():
    if needle in url:
        shutil.copyfile(png, out)
        sys.exit(0)
sys.exit(int(os.environ.get('FAKE_CHROME_EXIT', '0')))
'''


class FakeChromeCase(TempHomeCase):
    def setUp(self):
        super().setUp()
        fake = os.path.join(self.tmp, 'fake-chrome')
        with open(fake, 'w') as f:
            f.write(FAKE_CHROME.replace('/usr/bin/env python3', sys.executable, 1))
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        self.log = os.path.join(self.tmp, 'chrome.log')
        self.env.update(MOCKUP_CANVAS_CHROME=fake, FAKE_CHROME_LOG=self.log)

    def chrome_map(self, mapping):
        self.env['FAKE_CHROME_MAP'] = json.dumps(mapping)

    def chrome_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(l) for l in f]


class SnapCommand(FakeChromeCase):
    def test_snap_writes_png_with_size_and_safe_flags(self):
        png = os.path.join(self.tmp, 'fixture.png')
        solid_png(png, 768, 1024, (1, 2, 3))
        self.chrome_map({'localhost:5999': png})
        out = os.path.join(self.tmp, 'shots', 'home.png')
        r = self.run_cli('snap', 'http://localhost:5999/', '--size', 'tablet', '--out', out, '--wait', '500')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Snapped:', r.stdout)
        self.assertNotIn('Warning', r.stderr)
        self.assertTrue(os.path.getsize(out) > 0)
        args = self.chrome_calls()[0]
        self.assertIn('--window-size=768,1024', args)
        self.assertIn('--virtual-time-budget=500', args)
        self.assertTrue(any(a.startswith('--user-data-dir=') for a in args))
        self.assertFalse(any('file-access' in a or 'disable-web-security' in a for a in args))
        profile = next(a.split('=', 1)[1] for a in args if a.startswith('--user-data-dir='))
        self.assertFalse(os.path.exists(profile))   # throwaway profile removed

    def test_snap_fails_without_png_and_removes_stale_file(self):
        out = os.path.join(self.tmp, 'x.png')
        with open(out, 'wb') as f:
            f.write(b'stale')
        r = self.run_cli('snap', 'http://127.0.0.1:5999/', '--out', out)
        self.assertEqual(r.returncode, 1)
        self.assertIn('snap failed', r.stderr)
        self.assertFalse(os.path.exists(out))
        self.env['FAKE_CHROME_EXIT'] = '3'
        self.assertEqual(self.run_cli('snap', 'http://127.0.0.1:5999/', '--out', out).returncode, 1)

    def test_snap_rejects_non_http_and_warns_for_remote(self):
        for url in ('file:///etc/passwd', 'javascript:alert(1)', 'ftp://localhost/', 'http://'):
            r = self.run_cli('snap', url, '--out', os.path.join(self.tmp, 'x.png'))
            self.assertEqual(r.returncode, 1, url)
            self.assertIn('only http:// or https://', r.stderr)
        self.assertEqual(self.chrome_calls(), [])
        png = os.path.join(self.tmp, 'fixture.png')
        solid_png(png, 4, 4, (0, 0, 0))
        self.chrome_map({'example.com': png, '[::1]': png})
        r = self.run_cli('snap', 'https://example.com/', '--out', os.path.join(self.tmp, 'r.png'), '--size', '4x4')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Warning: example.com is not localhost', r.stderr)
        r = self.run_cli('snap', 'http://[::1]:5999/', '--out', os.path.join(self.tmp, 'v6.png'), '--size', '4x4')
        self.assertNotIn('Warning', r.stderr)

    def test_snap_times_out_on_open_requests(self):
        from unittest import mock
        out = os.path.join(self.tmp, 't.png')
        with mock.patch.dict(os.environ, {'MOCKUP_CANVAS_CHROME': '/bin/true'}), \
                mock.patch.object(canvas.subprocess, 'run',
                                  side_effect=subprocess.TimeoutExpired('chrome', 61)) as run, \
                mock.patch('sys.stderr') as err:
            self.assertFalse(canvas._snap('http://localhost:5999/', 10, 10, 1000, out))
        self.assertEqual(run.call_args.kwargs['timeout'], 61)
        self.assertIn('did not finish', ''.join(str(c.args[0]) for c in err.write.call_args_list))

    def test_snap_usage_errors(self):
        self.assertIn('Usage: canvas.py snap', self.run_cli('snap', '-h').stdout)
        self.assertEqual(self.run_cli('snap', 'http://localhost/').returncode, 1)              # no --out
        r = self.run_cli('snap', 'http://localhost/', '--out', 'a.png', '--size', 'huge')
        self.assertEqual(r.returncode, 1)
        self.assertIn('unknown size', r.stderr)
        r = self.run_cli('snap', 'http://localhost/', '--out', 'a.png', '--wait', 'soon')
        self.assertEqual(r.returncode, 1)
        r = self.run_cli('snap', 'http://localhost/', '--out', 'a.png', '--bogus')
        self.assertIn('unknown option: --bogus', r.stderr)


class CompareCommand(FakeChromeCase):
    def setUp(self):
        super().setUp()
        self.design = os.path.join(self.home, 'proj', 'design')
        self.run_cli('new', self.design, 'demo')
        self.idea = os.path.join(self.design, 'demo')
        for name in ('A01-One.html', 'A02-Two.html'):
            with open(os.path.join(self.idea, 'boards', name), 'w') as f:
                f.write(board_html())
            self.run_cli('add', self.idea, os.path.join(self.idea, 'boards', name), '--size', '40x30')
        self.board_png = os.path.join(self.tmp, 'board.png')
        rows = [bytes([200, 200, 200]) * 40 for _ in range(30)]
        canvas.png_write(self.board_png, 40, 30, rows)
        self.chrome_map({'A01-One.html': self.board_png})

    def test_compare_png_same_and_different(self):
        same = os.path.join(self.tmp, 'same.png')
        shutil.copyfile(self.board_png, same)
        r = self.run_cli('compare', self.idea, 'boards/A01-One.html', '--png', same)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Mismatch: 0.0%', r.stdout)
        out = os.path.join(self.idea, 'compare', 'A01-One')
        for f in ('board.png', 'app.png', 'diff.png', 'side.png', 'report.json'):
            self.assertTrue(os.path.isfile(os.path.join(out, f)), f)
        rep = self.read_json(os.path.join(out, 'report.json'))
        self.assertEqual(rep['board'], 'A01-One.html')
        self.assertEqual(rep['size'], {'w': 40, 'h': 30})
        self.assertEqual((rep['mismatch_percent'], rep['threshold'], rep['url']), (0.0, 24, None))
        self.assertRegex(rep['created'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        w, h, _, _ = canvas.png_read(os.path.join(out, 'side.png'))
        self.assertEqual((w, h), (40 * 3 + 32, 30))

        # Left half different by more than the threshold: 50 %
        half = os.path.join(self.tmp, 'half.png')
        canvas.png_write(half, 40, 30, [bytes([0, 0, 0]) * 20 + bytes([200, 200, 200]) * 20 for _ in range(30)])
        r = self.run_cli('compare', self.idea, 'A01-One', '--png', half, '--threshold', '10')
        self.assertIn('Mismatch: 50.0%', r.stdout)
        _, _, _, diff = canvas.png_read(os.path.join(out, 'diff.png'))
        self.assertEqual(diff[0][:3], b'\xff\x00\xff')
        self.assertEqual(diff[0][-3:], canvas._DIM[200:201] * 3)
        self.assertEqual(self.read_json(os.path.join(out, 'report.json'))['threshold'], 10)

    def test_compare_url_snaps_at_board_size(self):
        app = os.path.join(self.tmp, 'app.png')
        canvas.png_write(app, 40, 30, [bytes([200, 200, 200]) * 40 for _ in range(29)] + [b'\x00' * 120])
        self.chrome_map({'A01-One.html': self.board_png, 'localhost:5998': app})
        outdir = os.path.join(self.tmp, 'cmp')
        r = self.run_cli('compare', self.idea, 'A01-One', '--url', 'http://localhost:5998/home', '--out', outdir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Mismatch: 3.33%', r.stdout)
        self.assertEqual(self.read_json(os.path.join(outdir, 'report.json'))['url'], 'http://localhost:5998/home')
        calls = self.chrome_calls()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all('--window-size=40,30' in c for c in calls))
        self.assertTrue(calls[0][-1].startswith('file://'))
        self.assertFalse(os.path.exists(os.path.join(self.idea, 'compare')))

    def test_compare_resizes_other_sized_png(self):
        big = os.path.join(self.tmp, 'big.png')
        solid_png(big, 80, 60, (200, 200, 200))
        r = self.run_cli('compare', self.idea, 'A01-One', '--png', big)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('resized', r.stderr)
        self.assertIn('Mismatch: 0.0%', r.stdout)

    def test_compare_errors(self):
        png = self.board_png
        self.assertEqual(self.run_cli('compare', self.idea, 'Z99', '--png', png).returncode, 1)
        self.assertEqual(self.run_cli('compare', self.idea, 'A01-One').returncode, 1)              # neither
        self.assertEqual(self.run_cli('compare', self.idea, 'A01-One', '--png', png,
                                      '--url', 'http://localhost/').returncode, 1)                 # both
        self.assertEqual(self.run_cli('compare', self.idea, 'A01-One', '--url', 'file:///x').returncode, 1)
        self.assertEqual(self.run_cli('compare', self.idea, 'A01-One', '--png', png,
                                      '--threshold', '300').returncode, 1)
        self.assertEqual(self.run_cli('compare', self.idea, 'A01-One', '--png', 'nope.png').returncode, 1)
        # board render fails (fake Chrome writes nothing for A02)
        r = self.run_cli('compare', self.idea, 'A02-Two', '--png', png)
        self.assertEqual(r.returncode, 1)
        self.assertIn('render failed', r.stderr)
        # unsupported app PNG
        pal = os.path.join(self.tmp, 'pal.png')
        with open(pal, 'wb') as f:
            f.write(encode_png(2, 2, 3, gradient_rows(2, 2, 3), color=3))
        r = self.run_cli('compare', self.idea, 'A01-One', '--png', pal)
        self.assertEqual(r.returncode, 1)
        self.assertIn('unsupported PNG format', r.stderr)
        self.assertIn('Usage: canvas.py compare', self.run_cli('compare', '--help').stdout)

    def test_new_gitignore_and_old_ideas_get_compare(self):
        with open(os.path.join(self.idea, '.gitignore')) as f:
            self.assertEqual(f.read(), 'render/\ncompare/\n')
        gi = os.path.join(self.idea, '.gitignore')
        with open(gi, 'w') as f:
            f.write('render/')
        self.run_cli('compare', self.idea, 'A01-One', '--png', self.board_png)
        with open(gi) as f:
            self.assertEqual(f.read(), 'render/\ncompare/\n')
        self.run_cli('compare', self.idea, 'A01-One', '--png', self.board_png)
        with open(gi) as f:
            self.assertEqual(f.read(), 'render/\ncompare/\n')


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class CompareRealChrome(ServerCase):
    def test_board_against_served_board_is_zero(self):
        design = os.path.join(self.home, 'p', 'design')
        idea = self.make_idea(design, 'demo', boards=('A01-One.html', 'A02-Two.html'))
        with open(os.path.join(idea, 'boards', 'A02-Two.html'), 'w') as f:
            f.write(board_html('<div style="background:#c00;height:400px">other</div>'))
        self.start_server(canvas.CanvasHandler, design_dir=design, share_token='', share_edit=True, read_only=False)
        url = f'http://127.0.0.1:{self.port}/demo/boards/A01-One.html'
        r = self.run_cli('compare', idea, 'A01-One', '--url', url)
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = self.read_json(os.path.join(idea, 'compare', 'A01-One', 'report.json'))
        self.assertLess(rep['mismatch_percent'], 0.5)
        url2 = f'http://127.0.0.1:{self.port}/demo/boards/A02-Two.html'
        self.run_cli('compare', idea, 'A01-One', '--url', url2)
        rep = self.read_json(os.path.join(idea, 'compare', 'A01-One', 'report.json'))
        self.assertGreater(rep['mismatch_percent'], 20)


# ── impl / comment ─────────────────────────────────────────────────────────

class ImplCommand(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.project = os.path.join(self.home, 'proj')
        self.idea = self.make_idea(os.path.join(self.project, 'design'), 'demo',
                                   boards=('A01-One.html', 'A02-Two.html', 'A03-Three.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')
        self.run_cli('status', self.idea, 'A01-One', 'approved')
        self.run_cli('status', self.idea, 'A02-Two', 'approved')

    def test_record_show_clear(self):
        r = self.run_cli('impl', self.idea, 'boards/A01-One.html', '--route', '/home',
                         '--file', 'src/app/page.tsx', '--file', './src/app/page.tsx', '--file', 'src/ui/Card.tsx')
        self.assertEqual(r.returncode, 0, r.stderr)
        impl = self.read_json(self.cj)['boards']['A01-One.html']['impl']
        self.assertEqual(impl['route'], '/home')
        self.assertEqual(impl['files'], ['src/app/page.tsx', 'src/ui/Card.tsx'])
        self.assertRegex(impl['updated'], r'Z$')
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['status'], 'approved')
        r = self.run_cli('impl', self.idea, 'A01-One')
        self.assertIn('route /home', r.stdout)
        self.assertIn('src/ui/Card.tsx', r.stdout)
        # recording again replaces the mapping
        self.run_cli('impl', self.idea, 'A01-One', '--route', '/')
        self.assertEqual(self.read_json(self.cj)['boards']['A01-One.html']['impl']['files'], [])
        r = self.run_cli('impl', self.idea, 'A01-One', '--clear')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('impl', self.read_json(self.cj)['boards']['A01-One.html'])

    def test_list_and_strict(self):
        self.run_cli('impl', self.idea, 'A01-One', '--route', '/')
        self.run_cli('impl', self.idea, 'A03-Three', '--route', '/three')
        r = self.run_cli('impl', self.idea)
        self.assertEqual(r.returncode, 0)
        self.assertIn('Approved boards: 2/3', r.stdout)
        self.assertRegex(r.stdout, r'implemented\s+A01-One.html')
        self.assertRegex(r.stdout, r'missing\s+A02-Two.html')
        self.assertIn('Warning: A03-Three.html has an implementation but is not approved', r.stdout)
        self.assertEqual(self.run_cli('impl', self.idea, '--strict').returncode, 1)
        self.run_cli('impl', self.idea, 'A02-Two', '--route', '/two')
        self.assertEqual(self.run_cli('impl', self.idea, '--strict').returncode, 0)

    def test_errors(self):
        self.assertEqual(self.run_cli('impl', self.idea, 'Z99', '--route', '/').returncode, 1)
        self.assertEqual(self.run_cli('impl', self.idea, 'A01-One', '--file', 'x').returncode, 1)
        self.assertEqual(self.run_cli('impl', self.idea, 'A01-One', '--route', '/', '--clear').returncode, 1)
        self.assertEqual(self.run_cli('impl', self.idea, 'A01-One', '--route').returncode, 1)
        self.assertIn('Usage: canvas.py impl', self.run_cli('impl', '-h').stdout)

    def test_check_reports_missing_impl_files(self):
        os.makedirs(os.path.join(self.project, 'src'))
        with open(os.path.join(self.project, 'src', 'page.tsx'), 'w') as f:
            f.write('x')
        self.run_cli('impl', self.idea, 'A01-One', '--route', '/', '--file', 'src/page.tsx')
        r = self.run_cli('check', self.idea)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.run_cli('impl', self.idea, 'A02-Two', '--route', '/b', '--file', 'src/gone.tsx')
        r = self.run_cli('check', self.idea)
        self.assertEqual(r.returncode, 1)
        self.assertIn('impl file not found: A02-Two.html -> src/gone.tsx', r.stdout)


class CommentCommand(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.idea = self.make_idea(os.path.join(self.home, 'proj', 'design'), 'demo',
                                   boards=('A01-One.html', 'A02-Two.html'))
        self.cj = os.path.join(self.idea, 'canvas.json')

    def test_add_list_clear(self):
        r = self.run_cli('comment', self.idea, 'boards/A01-One.html', 'Button is too small', '--by', 'reviewer')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.run_cli('comment', self.idea, 'A01-One', '<b>bold</b> & more')
        cs = self.read_json(self.cj)['boards']['A01-One.html']['comments']
        self.assertEqual([c['text'] for c in cs], ['Button is too small', '<b>bold</b> & more'])
        self.assertEqual([c['by'] for c in cs], ['reviewer', 'user'])
        self.assertTrue(all(c['created'].endswith('Z') for c in cs))
        r = self.run_cli('comment', self.idea, 'A01-One')
        self.assertIn('1. [reviewer', r.stdout)
        self.assertIn('Button is too small', r.stdout)
        self.assertIn('no comments', self.run_cli('comment', self.idea, 'A02-Two').stdout)

        r = self.run_cli('check', self.idea)
        self.assertEqual(r.returncode, 0, r.stdout)       # comments are info, not problems
        self.assertIn('Comments: 2 on 1 board(s)', r.stdout)
        self.assertIn('A01-One.html: 2', r.stdout)

        r = self.run_cli('comment', self.idea, 'A01-One', '--clear')
        self.assertIn('2 removed', r.stdout)
        self.assertNotIn('comments', self.read_json(self.cj)['boards']['A01-One.html'])

    def test_errors(self):
        self.assertEqual(self.run_cli('comment', self.idea, 'Z99', 'hi').returncode, 1)
        self.assertEqual(self.run_cli('comment', self.idea, 'A01-One', '   ').returncode, 1)
        self.assertEqual(self.run_cli('comment', self.idea, 'A01-One', 'x', '--clear').returncode, 1)
        self.assertIn('Usage: canvas.py comment', self.run_cli('comment', '--help').stdout)

    def test_writes_keep_other_fields(self):
        data = self.read_json(self.cj)
        data['boards']['A01-One.html']['status'] = 'approved'
        data['links'] = [{'from': 'A01-One.html', 'to': 'A02-Two.html'}]
        self.write_json(self.cj, data)
        self.run_cli('comment', self.idea, 'A01-One', 'ok')
        self.run_cli('impl', self.idea, 'A01-One', '--route', '/')
        after = self.read_json(self.cj)
        self.assertEqual(after['links'], data['links'])
        self.assertEqual(after['boards']['A01-One.html']['status'], 'approved')
        self.assertFalse(os.path.exists(self.cj + '.tmp'))


# ── viewer ─────────────────────────────────────────────────────────────────

class ViewerBadgesStatic(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SCRIPTS, 'viewer.html'), encoding='utf-8') as f:
            self.viewer = f.read()

    def test_comment_and_impl_text_never_goes_through_innerHTML(self):
        self.assertIn("text.textContent = String(c.text == null ? '' : c.text);", self.viewer)
        self.assertIn("built.title = 'Route: ' + String(", self.viewer)
        for line in self.viewer.splitlines():
            if 'innerHTML' in line:
                self.assertNotRegex(line, r'c\.text|c\.by|impl\.route|comments\[')


def dump_dom(url, w=1200, h=900):
    import tempfile
    profile = tempfile.mkdtemp(prefix='mc-test-chrome-')
    try:
        return subprocess.run(canvas._chrome_args(profile, w, h, 3000) + ['--dump-dom', url],
                              capture_output=True, text=True, timeout=90).stdout
    finally:
        shutil.rmtree(profile, ignore_errors=True)


@unittest.skipUnless(os.path.exists(canvas.CHROME), 'Google Chrome not installed')
class ViewerBadgesDom(TempHomeCase):
    def test_export_shows_badges_without_injection(self):
        idea = self.make_idea(os.path.join(self.home, 'p', 'design'), 'demo', boards=('A01-One.html', 'A02-Two.html'))
        cj = os.path.join(idea, 'canvas.json')
        data = self.read_json(cj)
        data['boards']['A01-One.html']['impl'] = {'route': '"><img src=x onerror=alert(1)>', 'files': []}
        data['boards']['A01-One.html']['comments'] = [
            {'text': '<img src=x id=evil onerror=alert(1)>', 'by': '<b>x</b>', 'created': 't'},
            {'text': 'second', 'by': 'r', 'created': 't'}]
        data['boards']['A02-Two.html']['comments'] = 'not a list'
        self.write_json(cj, data)
        out = os.path.join(self.tmp, 'out')
        self.assertEqual(self.run_cli('export', idea, out).returncode, 0)
        dom = dump_dom(pathlib.Path(out, 'index.html').as_uri())
        self.assertIn('class="built-badge"', dom)
        self.assertEqual(dom.count('class="cmt-badge"'), 1)
        self.assertRegex(dom, r'class="cmt-badge"[^>]*>.*?</svg>2</button>')
        self.assertNotIn('id="evil"', dom)
        self.assertNotIn('<img src="x"', dom)


# ── install.sh ─────────────────────────────────────────────────────────────

class InstallAllSkills(TempHomeCase):
    def install(self, *args):
        return subprocess.run(['bash', os.path.join(REPO, 'install.sh'), *args], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def skills(self):
        base = os.path.join(REPO, 'skills')
        return sorted(d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, 'SKILL.md')))

    def test_links_every_skill_and_is_idempotent(self):
        names = self.skills()
        self.assertIn('mockup-canvas', names)
        r = self.install('--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in names:
            self.assertIn('Would link: ' + os.path.join(self.home, '.claude', 'skills', n), r.stdout)
            self.assertIn('Would link: ' + os.path.join(self.home, '.codex', 'skills', n), r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.home, '.claude')))

        r = self.install('--claude')
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in names:
            dst = os.path.join(self.home, '.claude', 'skills', n)
            self.assertTrue(os.path.islink(dst))
            self.assertEqual(os.readlink(dst), os.path.join(REPO, 'skills', n))
        self.assertFalse(os.path.exists(os.path.join(self.home, '.codex')))
        r = self.install('--claude')
        self.assertEqual(r.stdout.count('OK (already linked)'), len(names))
        self.assertNotIn('Linked:', r.stdout)
        self.assertNotIn('Backup:', r.stdout)


if __name__ == '__main__':
    unittest.main()
