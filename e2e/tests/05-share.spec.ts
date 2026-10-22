// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import { Page } from '@playwright/test';
import { test, expect, openCanvas, board, bar, xform, settled, zoomInOn, shot, Sandbox } from './fixtures';

async function startShare(sandbox: Sandbox) {
  // 1. serve <design> --share --minutes 5 (single-root mode, read-only)
  const srv = await sandbox.serve([sandbox.alphaDesign, '--share', '--minutes', '5']);
  expect(srv.token).not.toBe('');
  expect(srv.output()).toContain('read-only');
  return srv;
}

async function openShared(page: Page, sandbox: Sandbox) {
  const srv = await startShare(sandbox);
  await page.goto(`${srv.origin}/?t=${srv.token}`);
  // The token is swapped for a cookie and removed from the URL
  await expect(page).toHaveURL(`${srv.origin}/`);
  await page.getByRole('link', { name: /trailmate/ }).click();
  await openCanvas(page, page.url());
  await settled(page);
  return srv;
}

test.describe('Share mode', () => {
  test('Without the token the server answers 401', async ({ request, sandbox }) => {
    const srv = await startShare(sandbox);
    for (const p of ['/', '/trailmate/', '/trailmate/canvas.json', '/trailmate/boards/T01-Home.html']) {
      const r = await request.get(srv.origin + p, { maxRedirects: 0 });
      expect(r.status(), p).toBe(401);
      expect(await r.text()).toContain('This link needs its access token');
    }
    const wrong = await request.get(`${srv.origin}/?t=not-the-token`, { maxRedirects: 0 });
    expect(wrong.status()).toBe(401);
    const ok = await request.get(`${srv.origin}/?t=${srv.token}`, { maxRedirects: 0 });
    expect(ok.status()).toBe(302);
    expect(ok.headers()['set-cookie']).toMatch(/canvas_token=.*HttpOnly.*SameSite=Strict/);
  });

  test('The token URL opens a read-only viewer', async ({ page, sandbox, consoleErrors }, testInfo) => {
    const srv = await openShared(page, sandbox);
    // Read-only badge
    await expect(page.locator('#ro-badge')).toBeVisible();
    await expect(page.locator('#ro-badge')).toHaveText(/read-only/i);
    // 2. Board content loads through the keyed asset path
    await zoomInOn(page, 'T01-Home.html', 0.6);
    const iframe = board(page, 'T01-Home.html').locator('iframe');
    await expect(iframe).toHaveAttribute('src', /^\/_k\/[0-9a-f]+\/trailmate\/boards\/T01-Home\.html/);
    await expect(page.frameLocator('.board[data-file="T01-Home.html"] iframe').getByText('Pine Ridge Loop').first()).toBeVisible();
    await shot(page, testInfo, '08-share-readonly');
    // Drag does not move or save
    const before = sandbox.canvasJson().boards['T01-Home.html'];
    const leftBefore = await board(page, 'T01-Home.html').evaluate((e) => (e as HTMLElement).style.left);
    const box = (await bar(page, 'T01-Home.html').boundingBox())!;
    await page.mouse.move(box.x + 20, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 220, box.y + 150, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(800);
    expect(await board(page, 'T01-Home.html').evaluate((e) => (e as HTMLElement).style.left)).toBe(leftBefore);
    expect(sandbox.canvasJson().boards['T01-Home.html']).toMatchObject({ x: before.x, y: before.y });
    // Undo is ignored in read-only mode
    await page.keyboard.press('ControlOrMeta+z');
    await page.waitForTimeout(300);
    expect(sandbox.canvasJson().boards['T01-Home.html']).toMatchObject({ x: before.x, y: before.y });
    // 3. A direct layout POST with the session cookie is refused
    const status = await page.evaluate(async () => (await fetch(location.pathname.replace(/\/$/, '') + '/api/layout', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ board: 'T01-Home.html', x: 5, y: 5 }) })).status);
    expect(status).toBe(403);
    expect(sandbox.canvasJson().boards['T01-Home.html']).toMatchObject({ x: before.x, y: before.y });
    // Registry management API is not reachable in share mode
    const roots = await page.evaluate(async () => (await fetch('/api/roots/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dirs: ['~'] }) })).status);
    expect([403, 404]).toContain(roots);
    expect(srv.token).toBeTruthy();
    // Expected 403s are logged by some browsers. Under parallel load WebKit once reported the live
    // reload stream (/api/events) as blocked "due to access control checks"; the viewer reconnects,
    // and the cause is not confirmed (see README, observations), so it is recorded, not asserted.
    const sse = consoleErrors.filter((e) => /\/api\/events/.test(e));
    if (sse.length) testInfo.annotations.push({ type: 'sse-error', description: sse.join(' | ') });
    expect(consoleErrors.filter((e) => !/403|Forbidden/.test(e) && !/\/api\/events/.test(e))).toEqual([]);
  });
});

test.describe('Share mode on a phone @mobile', () => {
  async function touch(page: Page, type: string, points: Array<[number, number]>) {
    await page.evaluate(({ type, points }) => {
      const stage = document.getElementById('stage')!;
      const live = type === 'touchend' ? [] : points;
      let ev: Event;
      try {
        const mk = (pts: Array<[number, number]>) =>
          pts.map(([x, y], i) => new Touch({ identifier: i + 1, target: stage, clientX: x, clientY: y }));
        ev = new TouchEvent(type, { bubbles: true, cancelable: true,
          touches: mk(live), targetTouches: mk(live), changedTouches: mk(points) });
      } catch {
        // Playwright's WebKit has TouchEvent but no Touch constructor ("Illegal constructor"):
        // a plain event of the same type carrying touch-like points reaches the same handlers.
        const mk = (pts: Array<[number, number]>) =>
          pts.map(([x, y], i) => ({ identifier: i + 1, target: stage, clientX: x, clientY: y, pageX: x, pageY: y }));
        ev = new Event(type, { bubbles: true, cancelable: true });
        Object.defineProperty(ev, 'touches', { value: mk(live) });
        Object.defineProperty(ev, 'targetTouches', { value: mk(live) });
        Object.defineProperty(ev, 'changedTouches', { value: mk(points) });
      }
      stage.dispatchEvent(ev);
    }, { type, points });
  }

  test('Badge visible, one-finger pan, two-finger pinch @mobile', async ({ page, sandbox }, testInfo) => {
    await openShared(page, sandbox);
    const vp = page.viewportSize()!;
    // 1. Read-only badge inside the viewport
    const badge = page.locator('#ro-badge');
    await expect(badge).toBeVisible();
    const bb = (await badge.boundingBox())!;
    await shot(page, testInfo, '08-mobile-share');
    expect.soft(bb.x, 'Read-only badge left edge inside the viewport').toBeGreaterThanOrEqual(0);
    expect.soft(bb.x + bb.width, 'Read-only badge right edge inside the viewport').toBeLessThanOrEqual(vp.width);
    const tb = (await page.locator('#toolbar').boundingBox())!;
    testInfo.annotations.push({ type: 'toolbar-box', description: JSON.stringify({ tb, vp }) });
    // A real tap on the stage reaches the page (touch emulation is on)
    await page.touchscreen.tap(vp.width / 2, 40);
    // 2. One-finger pan (synthesized TouchEvents: Playwright has no touch-drag API)
    const a = await xform(page);
    await touch(page, 'touchstart', [[100, 300]]);
    for (let i = 1; i <= 8; i++) await touch(page, 'touchmove', [[100 + i * 10, 300 + i * 15]]);
    await touch(page, 'touchend', [[180, 420]]);
    await settled(page);
    const b = await xform(page);
    expect(b.x - a.x).toBeCloseTo(80, 0);
    expect(b.y - a.y).toBeCloseTo(120, 0);
    expect(b.s).toBe(a.s);
    // 3. Two-finger spread zooms in
    await touch(page, 'touchstart', [[150, 300], [240, 300]]);
    for (let i = 1; i <= 8; i++) await touch(page, 'touchmove', [[150 - i * 10, 300], [240 + i * 10, 300]]);
    await touch(page, 'touchend', [[70, 300], [320, 300]]);
    await settled(page);
    const c = await xform(page);
    expect(c.s).toBeGreaterThan(b.s * 2);
    await shot(page, testInfo, '08-mobile-after-pinch');
  });

  test('Toolbar fits inside the phone viewport @mobile', async ({ page, sandbox }, testInfo) => {
    // Product bug (reported, not fixed here): on a 390 px wide phone the toolbar is wider than the
    // viewport (white-space: nowrap, centred with translateX(-50%)), so both rounded ends are cut off.
    // Screenshot: 08-mobile-share.png. Remove test.fail() when the toolbar wraps or shrinks.
    test.fail();
    await openShared(page, sandbox);
    const vp = page.viewportSize()!;
    const tb = (await page.locator('#toolbar').boundingBox())!;
    testInfo.annotations.push({ type: 'toolbar-box', description: JSON.stringify({ tb, vp }) });
    expect(tb.x).toBeGreaterThanOrEqual(0);
    expect(tb.x + tb.width).toBeLessThanOrEqual(vp.width);
  });
});
