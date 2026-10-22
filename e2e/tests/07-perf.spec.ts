// spec: specs/mockup-canvas-journeys.md (7. Large canvas, frame rate per engine)
// Needs MC_E2E_LARGE_IDEA (the 71-board case). Run it alone so other tests do not share the CPU:
//   MC_E2E_PERF=1 MC_E2E_LARGE_IDEA=/path/to/design/<idea> npx playwright test tests/07-perf.spec.ts --workers=1
// Targets in every engine: average >= 55 FPS and no frame over 50 ms while panning.
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, openCanvas, xform, settled, record, Sandbox } from './fixtures';
import { measurePan, zoomTo } from './perf-measure';

const LARGE = process.env.MC_E2E_LARGE_IDEA || '';
const MIN_FPS = 55;
const MAX_FRAME_MS = 50;

async function openLarge(page: Page, sandbox: Sandbox) {
  const design = path.join(sandbox.work, 'large', 'design');
  const idea = path.basename(LARGE);
  fs.cpSync(LARGE, path.join(design, idea), { recursive: true, filter: (src) => !src.includes(`${path.sep}render`) });
  const srv = await sandbox.serveRegistry([[design, 'large']]);
  const url = `${srv.origin}/large/${encodeURIComponent(idea)}/`;
  await openCanvas(page, url);
  await settled(page);
  return { url, count: Object.keys(sandbox.canvasJson(path.join(design, idea)).boards).length };
}

test.describe('Frame rate per engine (71 boards)', () => {
  test.skip(!LARGE, 'set MC_E2E_LARGE_IDEA to a large idea folder');
  test.skip(!process.env.MC_E2E_PERF, 'set MC_E2E_PERF=1 (and run with --workers=1)');
  test.setTimeout(240_000);

  test('Pan at fit, 25%, 50%, and 72%', async ({ page, sandbox, browserName }, testInfo) => {
    const { url, count } = await openLarge(page, sandbox);
    // Warm: wait until every board has its thumbnail, then reload so all of them come from the cache
    await expect.poll(() => page.locator('.board img.thumb').count(), { timeout: 180_000, intervals: [1000] })
      .toBe(count);
    await openCanvas(page, url);
    await expect.poll(() => page.locator('.board img.thumb').count(), { timeout: 30_000 }).toBe(count);
    await settled(page);
    // Floor: the same pan with the canvas hidden. It measures the machine and the headless
    // browser, not the viewer; a slow frame here means the run is too noisy to judge frame times.
    const results: Record<string, any> = {};
    await page.addStyleTag({ content: '#canvas.floor-probe{visibility:hidden}' });
    await page.locator('#canvas').evaluate((e) => e.classList.add('floor-probe'));
    const floor = await measurePan(page);
    await page.locator('#canvas').evaluate((e) => e.classList.remove('floor-probe'));
    await settled(page);
    // Fit view (thumbnails), 25% (thumbnails, bar text shown), 50% and 72% (live boards near the view)
    for (const z of [0, 0.25, 0.5, 0.72]) {
      if (z) {
        await zoomTo(page, z);
        await page.waitForTimeout(2500);   // live boards and thumbnails load while the view rests
      }
      const name = z ? `z${z}` : 'fit';
      results[name] = { zoom: Math.round((await xform(page)).s * 1000) / 1000, ...(await measurePan(page)) };
      await settled(page);
    }
    record(testInfo, `perf-${browserName}`, { floor, ...results });
    console.log(`[perf] ${testInfo.project.name} ${JSON.stringify({ floor, ...results })}`);
    const noisy = floor.over50 > 0;
    if (noisy) testInfo.annotations.push({ type: 'noisy', description: `empty-canvas pan had a ${floor.worstMs} ms frame; worst-frame checks skipped` });
    for (const [name, r] of Object.entries(results)) {
      expect.soft(r.fps, `${name} average FPS`).toBeGreaterThanOrEqual(MIN_FPS);
      if (!noisy) expect.soft(r.worstMs, `${name} worst frame (ms)`).toBeLessThanOrEqual(MAX_FRAME_MS);
    }
  });
});
