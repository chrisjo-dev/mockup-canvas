// spec: specs/mockup-canvas-journeys.md (7. Large canvas: a board seen once never turns white again)
// Every board is a solid color (no white anywhere), and its load event is held back by a short
// blocking script, so loading is slow enough to catch. After a board has been painted once, no
// sampled point inside it may be pure white while it is panned off and back, zoomed across the
// thumbnail threshold and back, or interrupted by a gesture while its iframe loads.
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, openCanvas, settled } from './fixtures';
import { zoomTo } from './perf-measure';
import { decodePng } from './png';

const COLORS = ['#2f6fdf', '#1f9d55', '#d97706', '#b83280', '#6b46c1', '#0f766e'];

function board(i: number, color: string) {
  return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
    `</head><body style="margin:0;height:100vh;background:${color};color:#111;font:700 40px sans-serif">` +
    '<script>const t = performance.now(); while (performance.now() - t < 400) {}</script>' +
    `<p style="margin:0;padding:40px">Board ${i}</p></body></html>`;
}

async function panBy(page: Page, dx: number, dy: number, frames = 20) {
  await page.evaluate(async ({ dx, dy, frames }) => {
    const stage = document.getElementById('stage')!;
    const sx = 640, sy = 300;
    stage.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0, clientX: sx, clientY: sy }));
    for (let i = 1; i <= frames; i++) {
      await new Promise((r) => requestAnimationFrame(r));
      window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: sx + dx * i / frames, clientY: sy + dy * i / frames }));
    }
    window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: sx + dx, clientY: sy + dy }));
  }, { dx, dy, frames });
}

test.describe('A board seen once never shows blank white again', () => {
  test.setTimeout(120_000);

  test('pan away and back, zoom across the threshold, gesture during load', async ({ page, sandbox }, testInfo) => {
    const idea = path.join(sandbox.alphaDesign, 'colors');
    fs.mkdirSync(path.join(idea, 'boards'), { recursive: true });
    fs.mkdirSync(path.join(idea, 'shared'), { recursive: true });
    const boards: Record<string, unknown> = {};
    COLORS.forEach((c, i) => {
      const f = `C0${i + 1}-Color.html`;
      fs.writeFileSync(path.join(idea, 'boards', f), board(i + 1, c));
      boards[f] = { x: i * 1500, y: 0, w: 390, h: 844, title: `Color ${i + 1}` };
    });
    fs.writeFileSync(path.join(idea, 'canvas.json'), JSON.stringify({ boards, groups: [], links: [] }));
    const srv = await sandbox.serve([sandbox.alphaDesign]);
    await openCanvas(page, `${srv.origin}/colors/`);
    await settled(page);

    const vp = page.viewportSize()!;
    const seen = new Set<string>();
    const blanks: string[] = [];
    let step = 'start', samples = 0;

    /** Screenshot and check a 5x5 grid inside every visible board; returns the boards painted now. */
    async function sample() {
      const boxes = await page.locator('.board').evaluateAll((els) => els.map((e) => {
        const r = e.getBoundingClientRect();
        return { file: (e as HTMLElement).dataset.file!, x: r.x, y: r.y, w: r.width, h: r.height };
      }));
      const png = decodePng(await page.screenshot());
      const k = png.w / vp.width;
      samples++;
      for (const b of boxes) {
        let white = 0, total = 0;
        for (let i = 1; i <= 5; i++) for (let j = 1; j <= 5; j++) {
          const x = b.x + (b.w * i) / 6, y = b.y + (b.h * j) / 6;
          if (x < 0 || y < 0 || x >= vp.width || y >= vp.height - 70) continue;   // off screen or under the toolbar
          const o = (Math.floor(y * k) * png.w + Math.floor(x * k)) * png.ch;
          total++;
          if (png.px[o] === 255 && png.px[o + 1] === 255 && png.px[o + 2] === 255) white++;
        }
        if (!total) continue;
        if (white === 0) seen.add(b.file);
        else if (seen.has(b.file)) blanks.push(`${step}: ${b.file} ${white}/${total} white points`);
      }
    }
    async function sampleFor(ms: number) {
      const end = Date.now() + ms;
      while (Date.now() < end) await sample();
    }

    // 1. Fit view: every board gets its thumbnail (its first paint)
    await expect.poll(() => page.locator('.board img.thumb').count(), { timeout: 60_000 }).toBe(COLORS.length);
    await settled(page);
    await sample();
    expect([...seen].sort()).toHaveLength(COLORS.length);

    // 2. Zoom in: live iframes load hidden over the thumbnails
    step = 'zoom in to 60%';
    await zoomTo(page, 0.6);
    await sampleFor(2500);
    await expect.poll(() => page.locator('.board iframe:not(.pending)').count()).toBeGreaterThan(0);

    // 3. Pan the boards off screen and back
    step = 'pan away';
    await panBy(page, -1200, 0);
    await sampleFor(1500);
    step = 'pan back';
    await panBy(page, 1200, 0);
    await sampleFor(1500);

    // 4. Zoom out across the threshold (and inside the hysteresis band), then back in
    for (const z of [0.33, 0.25, 0.6]) {
      step = `zoom to ${z * 100}%`;
      await zoomTo(page, z);
      await sampleFor(1500);
    }

    // 5. A gesture while iframes are loading
    step = 'gesture during load';
    await zoomTo(page, 0.12);
    await settled(page);
    await zoomTo(page, 0.6);
    await page.waitForTimeout(350);   // idle: iframes start loading (each takes over 400 ms)
    await panBy(page, -300, 0, 10);
    await sampleFor(800);
    await panBy(page, 300, 0, 10);
    await sampleFor(2000);

    testInfo.annotations.push({ type: 'samples', description: String(samples) });
    expect(blanks, `blank boards after their first paint (${samples} samples)`).toEqual([]);
  });
});
