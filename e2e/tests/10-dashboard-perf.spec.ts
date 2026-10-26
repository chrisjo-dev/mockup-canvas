// spec: specs/mockup-canvas-journeys.md (section 1, dashboard performance)
// Opt-in (MC_E2E_PERF=1): scroll a 40-idea registry and record frame times, first paint, and heap.
// Targets: at least 55 FPS and no frame over 50 ms while scrolling with every thumbnail loaded.
import fs from 'node:fs';
import path from 'node:path';
import { test, expect, record, EXAMPLE_IDEA } from './fixtures';

test.skip(!process.env.MC_E2E_PERF, 'set MC_E2E_PERF=1 to run the dashboard performance check');

test('Dashboard scrolls a 40-idea registry smoothly', async ({ page, sandbox, browserName }, testInfo) => {
  test.skip(browserName !== 'chromium', 'frame and heap numbers are recorded in Chromium');
  test.setTimeout(600_000);
  // 4 projects x 10 ideas, each a copy of the 6-board sample (alpha already holds trailmate)
  const extra: Array<[string, string]> = [];
  for (let p = 0; p < 4; p++) {
    const design = path.join(sandbox.work, 'proj' + p, 'design');
    for (let i = 0; i < (p ? 10 : 9); i++) fs.cpSync(EXAMPLE_IDEA, path.join(design, `idea-${p}-${i}`), { recursive: true });
    extra.push([design, 'proj' + p]);
  }
  const srv = await sandbox.serveRegistry(extra);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(srv.origin + '/');
  await expect(page.locator('article.gc')).toHaveCount(40);
  const fcp = await page.evaluate(() => performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? -1);

  // Warm up: walk down the page until every card shows its thumbnails (rendered once by the server)
  await page.evaluate(async () => {
    const main = document.getElementById('main')!;
    const ready = () => [...document.querySelectorAll('article.gc .slot')].every((s) => s.querySelector('img') || (s as HTMLElement).hidden);
    for (let y = 0; y <= main.scrollHeight; y += 400) {
      main.scrollTop = y;
      await new Promise((r) => setTimeout(r, 150));
    }
    const until = Date.now() + 480_000;
    while (!ready() && Date.now() < until) {
      for (let y = 0; y <= main.scrollHeight; y += 600) { main.scrollTop = y; await new Promise((r) => setTimeout(r, 300)); }
    }
    main.scrollTop = 0;
  });

  // Scroll down and up at 14 px per frame (about 840 px/s) for 6 s with hover effects active
  const box = (await page.locator('main').boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 300);
  const r = await page.evaluate(() => new Promise<{ frames: number[]; ms: number }>((resolve) => {
    const main = document.getElementById('main')!;
    const max = main.scrollHeight - main.clientHeight;
    const frames: number[] = [];
    let last = 0, dir = 1;
    const t0 = performance.now();
    const step = (t: number) => {
      if (last) frames.push(t - last);
      last = t;
      let y = main.scrollTop + dir * 14;
      if (y >= max) { y = max; dir = -1; } else if (y <= 0) { y = 0; dir = 1; }
      main.scrollTop = y;
      if (t - t0 < 6000) requestAnimationFrame(step); else resolve({ frames, ms: t - t0 });
    };
    requestAnimationFrame(step);
  }));
  const frames = r.frames.slice(5);
  const avg = frames.reduce((s, x) => s + x, 0) / frames.length;
  const sorted = frames.slice().sort((a, b) => a - b);
  const result = {
    fps: Math.round(1000 / avg * 10) / 10,
    p95: Math.round(sorted[Math.floor(sorted.length * 0.95)] * 10) / 10,
    worst: Math.round(sorted[sorted.length - 1] * 10) / 10,
    over50: frames.filter((f) => f > 50).length,
    frames: frames.length,
    fcp: Math.round(fcp),
    heapMB: await page.evaluate(() => (performance as any).memory ? Math.round((performance as any).memory.usedJSHeapSize / 104857.6) / 10 : null),
    nodes: await page.evaluate(() => document.getElementsByTagName('*').length),
  };
  record(testInfo, 'dashboard-scroll-40', result);
  console.log('dashboard scroll, 40 ideas:', JSON.stringify(result));
  expect(result.fps).toBeGreaterThanOrEqual(55);
  expect(result.over50).toBe(0);
});
