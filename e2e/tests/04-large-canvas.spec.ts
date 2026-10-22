// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
// Needs a large idea folder (the 71-board case): MC_E2E_LARGE_IDEA=/path/to/design/<idea>.
// The folder is copied into the sandbox; the original is never touched.
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, openCanvas, xform, settled, zoomInOn, shot, record, Sandbox } from './fixtures';

const LARGE = process.env.MC_E2E_LARGE_IDEA || '';

async function openLarge(page: Page, sandbox: Sandbox) {
  const design = path.join(sandbox.work, 'large', 'design');
  const idea = path.basename(LARGE);
  fs.cpSync(LARGE, path.join(design, idea), { recursive: true, filter: (src) => !src.includes(`${path.sep}render`) });
  const srv = await sandbox.serveRegistry([[design, 'large']]);
  await openCanvas(page, `${srv.origin}/large/${encodeURIComponent(idea)}/`);
  await settled(page);
  return { count: Object.keys(sandbox.canvasJson(path.join(design, idea)).boards).length };
}

/** Drives a scripted pan for `ms` with synthetic mouse events, one move per frame, and counts frames. */
async function measurePanFps(page: Page, ms = 2000) {
  return page.evaluate(async (dur) => {
    const stage = document.getElementById('stage')!;
    const sx = 30, sy = 30;
    stage.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0, clientX: sx, clientY: sy }));
    const times: number[] = [];
    const t0 = performance.now();
    await new Promise<void>((resolve) => {
      function step(t: number) {
        times.push(t);
        const k = (t - t0) / dur;
        // Back and forth across about 600 px horizontally and 200 px vertically
        const x = sx + Math.sin(k * Math.PI * 2) * 300;
        const y = sy + Math.sin(k * Math.PI * 4) * 100;
        window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
        if (t - t0 < dur) requestAnimationFrame(step); else resolve();
      }
      requestAnimationFrame(step);
    });
    window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: sx, clientY: sy }));
    const gaps = times.slice(1).map((t, i) => t - times[i]);
    const total = times[times.length - 1] - times[0];
    const sorted = [...gaps].sort((a, b) => a - b);
    return {
      fps: Math.round(((times.length - 1) / total) * 1000 * 10) / 10,
      frames: times.length,
      worstFrameMs: Math.round(sorted[sorted.length - 1] * 10) / 10,
      p95FrameMs: Math.round(sorted[Math.floor(sorted.length * 0.95)] * 10) / 10,
    };
  }, ms);
}

test.describe('Large canvas (71 boards)', () => {
  test.skip(!LARGE, 'set MC_E2E_LARGE_IDEA to a large idea folder');
  test.setTimeout(120_000);

  test('Zoomed out shows thumbnails or title cards, zoomed in shows live boards, no console errors',
    async ({ page, sandbox, consoleErrors }, testInfo) => {
      const { count } = await openLarge(page, sandbox);
      await expect(page.locator('.board')).toHaveCount(count);
      record(testInfo, 'boards', count);
      // 2. Fitted zoom is below 35%, no live iframes
      const fitted = await xform(page);
      expect(fitted.s).toBeLessThan(0.35);
      await expect(page.locator('.board iframe')).toHaveCount(0);
      // Each board shows a thumbnail or its title card (.ph) once idle
      await page.waitForTimeout(1500);
      const content = await page.locator('.board').evaluateAll((els) => els.map((e) => ({
        thumb: !!e.querySelector('img.thumb'), ph: !!e.querySelector('.ph') })));
      expect(content.every((c) => c.thumb || c.ph)).toBe(true);
      // Thumbnails arrive as the server renders them
      await expect.poll(() => page.locator('.board img.thumb').count(), { timeout: 60_000 }).toBeGreaterThan(0);
      record(testInfo, 'thumbs-after-load', await page.locator('.board img.thumb').count());
      await shot(page, testInfo, '07-large-zoomed-out');
      // 3. Zoom in over a board above 35%
      const first = await page.locator('.board').first().getAttribute('data-file');
      await zoomInOn(page, first!, 0.6);
      await expect.poll(() => page.locator('.board iframe').count()).toBeGreaterThan(0);
      const live = await page.locator('.board iframe').count();
      record(testInfo, 'live-iframes-zoomed', live);
      expect(live).toBeLessThan(count);
      await shot(page, testInfo, '07-large-zoomed-in');
      expect(consoleErrors).toEqual([]);
    });

  test('Pan frame rate', async ({ page, sandbox, browserName }, testInfo) => {
    await openLarge(page, sandbox);
    // 1a. Fitted (thumbnail) zoom
    await page.waitForTimeout(1500);
    const low = await measurePanFps(page);
    record(testInfo, `fps-fitted-${browserName}`, { zoom: (await xform(page)).s, ...low });
    await settled(page);
    // 1b. About 60% (live boards near the view)
    const first = await page.locator('.board').first().getAttribute('data-file');
    await zoomInOn(page, first!, 0.6);
    await page.waitForTimeout(1500);
    const high = await measurePanFps(page);
    record(testInfo, `fps-live-${browserName}`, { zoom: (await xform(page)).s, ...high });
    expect(low.fps).toBeGreaterThanOrEqual(30);
    expect(high.fps).toBeGreaterThanOrEqual(30);
  });
});
