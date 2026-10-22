// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import { test, expect, openCanvas, board, bar, xform, settled, zoomInOn, emptyPoint, arrowPaths, shot } from './fixtures';

test.describe('Open an idea and navigate', () => {
  test.beforeEach(async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
  });

  test('Boards render with real content', async ({ page, consoleErrors }, testInfo) => {
    await expect(page.locator('.board')).toHaveCount(6);
    await expect(page.locator('.board-bar .board-id')).toHaveText(
      ['T01-Home', 'T02-TrailDetail', 'T03-Invite', 'T04-Plan', 'T05-Empty', 'T06-WebLanding']);
    await shot(page, testInfo, '02-fit');
    // 2. Zoom in over T01-Home above 35%
    await zoomInOn(page, 'T01-Home.html', 0.6);
    await expect(board(page, 'T01-Home.html').locator('iframe')).toBeAttached();
    const frame = page.frameLocator('.board[data-file="T01-Home.html"] iframe');
    await expect(frame.getByText('Pine Ridge Loop').first()).toBeVisible({ timeout: 10_000 });
    await shot(page, testInfo, '02-zoomed-live');
    expect(consoleErrors).toEqual([]);
  });

  test('Wheel zoom in and out, F fits', async ({ page }) => {
    const fitted = await xform(page);
    // 2. Wheel up, then down, over the stage
    const p = await emptyPoint(page);
    await page.mouse.move(p.x, p.y);
    await page.mouse.wheel(0, -200);
    await settled(page);
    const zin = await xform(page);
    expect(zin.s).toBeGreaterThan(fitted.s);
    await expect(page.locator('#zoom-lbl')).toHaveText(Math.round(zin.s * 100) + '%');
    await page.mouse.wheel(0, 400);
    await settled(page);
    const zout = await xform(page);
    expect(zout.s).toBeLessThan(zin.s);
    // 3. F returns the fitted transform
    await page.keyboard.press('f');
    await settled(page);
    const refit = await xform(page);
    expect(refit.s).toBeCloseTo(fitted.s, 5);
    expect(refit.x).toBeCloseTo(fitted.x, 1);
    expect(refit.y).toBeCloseTo(fitted.y, 1);
  });

  test('Pan by dragging empty space', async ({ page }) => {
    const before = await xform(page);
    // 1. Find an empty point; 2. drag it by (150, 80)
    const p = await emptyPoint(page);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 75, p.y + 40, { steps: 5 });
    await page.mouse.move(p.x + 150, p.y + 80, { steps: 5 });
    await page.mouse.up();
    await settled(page);
    const after = await xform(page);
    expect(after.x - before.x).toBeCloseTo(150, 0);
    expect(after.y - before.y).toBeCloseTo(80, 0);
    expect(after.s).toBe(before.s);
  });

  test('Arrows are drawn and L toggles them', async ({ page }, testInfo) => {
    const svg = page.locator('#arrow-svg');
    await expect(svg.locator(':scope > path')).toHaveCount(4);
    await expect(svg.locator('text')).toHaveText(['Create first hike', 'Open trail', 'Invite friends', 'Plan together']);
    await expect(svg).toBeVisible();
    // 2. L hides, L shows
    await page.keyboard.press('l');
    await expect(page.locator('#toast')).toHaveText('Arrows hidden');
    await expect(svg).toHaveClass(/hidden/);
    await expect(svg).toBeHidden();
    await shot(page, testInfo, '02-arrows-hidden');
    await page.keyboard.press('l');
    await expect(page.locator('#toast')).toHaveText('Arrows shown');
    await expect(svg.locator(':scope > path')).toHaveCount(4);
    await expect(svg).toBeVisible();
  });

  test('Collapsing a group hides its boards', async ({ page }) => {
    // 1. Click the group header (visible at the fitted zoom)
    const hdr = page.locator('.grp-hdr', { hasText: 'v1' });
    await hdr.click();
    await expect(page.locator('.board.collapsed')).toHaveCount(6);
    await expect(hdr.locator('.grp-arrow')).toHaveText('\u25b6');
    // Zoomed in, a collapsed board keeps no live iframe
    await zoomInOn(page, 'T01-Home.html', 0.5);
    await expect(page.locator('.board iframe')).toHaveCount(0);
    // 2. Fit again and expand
    await page.keyboard.press('f');
    await settled(page);
    await hdr.click();
    await expect(page.locator('.board.collapsed')).toHaveCount(0);
    await zoomInOn(page, 'T01-Home.html', 0.5);
    await expect(board(page, 'T01-Home.html').locator('iframe')).toBeAttached();
  });
});

test.describe('Drag, undo, redo', () => {
  test.beforeEach(async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
  });

  async function dragBar(page: import('@playwright/test').Page, file: string, dx: number, dy: number, release = true) {
    const box = (await bar(page, file).boundingBox())!;
    const sx = box.x + Math.min(20, box.width / 4), sy = box.y + box.height / 2;
    await page.mouse.move(sx, sy);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(sx + (dx * i) / 10, sy + (dy * i) / 10);
    if (release) await page.mouse.up();
  }

  test('Dragging a board by its title bar saves canvas.json, undo and redo', async ({ page, sandbox }, testInfo) => {
    const orig = sandbox.canvasJson().boards['T03-Invite.html'];
    const { s } = await xform(page);
    // 1. Drag the T03-Invite bar by (200, 120)
    await dragBar(page, 'T03-Invite.html', 200, 120);
    await expect.poll(() => sandbox.canvasJson().boards['T03-Invite.html'].x).not.toBe(orig.x);
    const moved = sandbox.canvasJson().boards['T03-Invite.html'];
    expect(moved.x - orig.x).toBeCloseTo(200 / s, -1);
    expect(moved.y - orig.y).toBeCloseTo(120 / s, -1);
    await shot(page, testInfo, '03-after-drag');
    // Undo
    await page.keyboard.press('ControlOrMeta+z');
    await expect(page.locator('#toast')).toHaveText('Undo: T03-Invite');
    await expect.poll(() => sandbox.canvasJson().boards['T03-Invite.html']).toMatchObject({ x: orig.x, y: orig.y });
    // Redo
    await page.keyboard.press('ControlOrMeta+Shift+z');
    await expect(page.locator('#toast')).toHaveText('Redo: T03-Invite');
    await expect.poll(() => sandbox.canvasJson().boards['T03-Invite.html']).toMatchObject({ x: moved.x, y: moved.y });
    // Edge case: undo twice leaves nothing to undo
    await page.keyboard.press('ControlOrMeta+z');
    await expect(page.locator('#toast')).toHaveText('Undo: T03-Invite');
    await page.keyboard.press('ControlOrMeta+z');
    await expect(page.locator('#toast')).toHaveText('Nothing to undo');
    await expect.poll(() => sandbox.canvasJson().boards['T03-Invite.html']).toMatchObject({ x: orig.x, y: orig.y });
  });

  test('Dragging a board does not copy its id', async ({ page, context, browserName }) => {
    if (browserName === 'chromium') {
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await page.evaluate(() => navigator.clipboard.writeText('user clipboard'));
    }
    await dragBar(page, 'T03-Invite.html', 200, 120);
    await page.waitForTimeout(400);
    const toast = page.locator('#toast');
    const shown = (await toast.getAttribute('class'))!.includes('on') ? await toast.textContent() : '';
    expect(shown).not.toContain('T03-Invite');
    if (browserName === 'chromium') expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('user clipboard');
  });

  test('Arrows follow during the drag', async ({ page }) => {
    const before = await arrowPaths(page);
    // links: 0 T05->T01, 1 T01->T02, 2 T02->T03, 3 T03->T04
    await dragBar(page, 'T03-Invite.html', 120, 160, false);
    await expect.poll(async () => (await arrowPaths(page))[2]).not.toBe(before[2]);
    const mid = await arrowPaths(page);
    expect(mid[3]).not.toBe(before[3]);
    expect(mid[0]).toBe(before[0]);
    await page.mouse.up();
  });
});

test.describe('Title bar click and double click', () => {
  test.beforeEach(async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
  });

  test('Click copies the board id', async ({ page, context, browserName }, testInfo) => {
    const canReadClipboard = browserName === 'chromium';
    if (canReadClipboard) await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    // 1. Click the T01-Home title bar
    await bar(page, 'T01-Home.html').click({ position: { x: 10, y: 5 } });
    await expect(page.locator('#toast')).toHaveText(canReadClipboard ? 'Copied: T01-Home' : /T01-Home/);
    await expect(page.locator('#toast')).toHaveClass(/on/);
    await shot(page, testInfo, '04-copied-toast');
    if (canReadClipboard) expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('T01-Home');
    testInfo.annotations.push({ type: 'toast', description: await page.locator('#toast').textContent() || '' });
  });

  test('Double click opens the board alone in a new tab', async ({ page, context }) => {
    const pagePromise = context.waitForEvent('page');
    // 1. Double click the T01-Home title bar
    await bar(page, 'T01-Home.html').dblclick({ position: { x: 10, y: 5 } });
    const tab = await pagePromise;
    await tab.waitForLoadState();
    expect(tab.url()).toMatch(/\/alpha\/trailmate\/boards\/T01-Home\.html$/);
    await expect(tab.getByText('Pine Ridge Loop').first()).toBeVisible();
  });
});
