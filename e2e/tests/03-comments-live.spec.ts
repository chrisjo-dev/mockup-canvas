// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { test, expect, openCanvas, board, settled, zoomInOn, shot, record } from './fixtures';

test.describe('Comments and built badge', () => {
  test('CLI comments show as a badge and a panel; Esc closes; XSS is text', async ({ page, sandbox }, testInfo) => {
    // 1. Add two comments with the CLI, both carrying markup
    const img = '<img src=x onerror="window.__xss=1">';
    const scr = '<script>window.__xss=2</script> close & "quote"';
    sandbox.cli('comment', sandbox.idea, 'T01-Home.html', img, '--by', 'qa<b>bot</b>');
    sandbox.cli('comment', sandbox.idea, 'T01-Home.html', scr);
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
    await zoomInOn(page, 'T01-Home.html', 0.6);
    // 2. Badge shows the count; click opens the panel
    const badge = board(page, 'T01-Home.html').locator('.cmt-badge');
    await expect(badge).toHaveText('2');
    await expect(badge).toHaveAttribute('title', '2 comment(s)');
    await badge.click();
    const panel = page.locator('#cmt-panel');
    await expect(panel).toBeVisible();
    await expect(panel.locator('.cmt-head')).toContainText('T01-Home comments');
    await expect(panel.locator('.cmt-text')).toHaveText([img, scr]);
    await expect(panel.locator('.cmt-meta').first()).toContainText('qa<b>bot</b>');
    await expect(panel.locator('img, script, b')).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();
    await shot(page, testInfo, '05-comment-panel');
    // Esc closes
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();
    // Clicking the close button also works
    await badge.click();
    await expect(panel).toBeVisible();
    await panel.getByRole('button', { name: 'Close' }).click();
    await expect(panel).toBeHidden();
  });

  test('Built badge tooltip shows the route', async ({ page, sandbox }) => {
    // 1. Record an implementation
    sandbox.cli('impl', sandbox.idea, 'T01-Home.html', '--route', '/home', '--file', 'src/Home.tsx');
    const srv = await sandbox.serveRegistry();
    // 2. Open the idea
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    const built = board(page, 'T01-Home.html').locator('.built-badge');
    await expect(built).toHaveText('built');
    await expect(built).toHaveAttribute('title', 'Route: /home');
    await expect(page.locator('.built-badge')).toHaveCount(1);
  });
});

test.describe('Live reload', () => {
  test('Editing a board file reloads only that iframe', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
    await zoomInOn(page, 'T01-Home.html', 0.6);
    const frame = page.frameLocator('.board[data-file="T01-Home.html"] iframe');
    await expect(frame.getByText('Pine Ridge Loop').first()).toBeVisible({ timeout: 10_000 });
    // 1. Marker on window
    await page.evaluate(() => { (window as any).__noReload = 'kept'; });
    // 2. Append a visible element on disk
    const file = path.join(sandbox.idea, 'boards', 'T01-Home.html');
    const html = fs.readFileSync(file, 'utf8');
    const t0 = Date.now();
    fs.writeFileSync(file, html.replace('</body>',
      '<div id="qa-live" style="position:fixed;top:0;left:0;background:#ff0;font-size:40px">LIVE EDIT 42</div></body>'));
    await expect(frame.locator('#qa-live')).toHaveText('LIVE EDIT 42', { timeout: 5_000 });
    const ms = Date.now() - t0;
    record(testInfo, 'live-reload-ms', ms);
    expect(ms, 'board reload should land within about 2 s').toBeLessThan(2_600);
    expect(await page.evaluate(() => (window as any).__noReload)).toBe('kept');
    await shot(page, testInfo, '06-live-edit');
  });

  test('CLI status and link update the open canvas', async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await page.evaluate(() => { (window as any).__noReload = 'kept'; });
    const t3 = board(page, 'T03-Invite.html');
    await expect(t3.locator('.status-badge.approved')).toHaveCount(0);
    // 1. status
    sandbox.cli('status', sandbox.idea, 'T03-Invite.html', 'approved', '--note', 'QA approved');
    await expect(t3.locator('.status-badge.approved')).toHaveCount(1, { timeout: 5_000 });
    await expect(t3.locator('.board-bar')).toHaveAttribute('title', 'QA approved');
    // 2. link
    sandbox.cli('link', sandbox.idea, 'T04-Plan.html', 'T05-Empty.html', '--label', 'QA link');
    await expect(page.locator('#arrow-svg > path')).toHaveCount(5, { timeout: 5_000 });
    await expect(page.locator('#arrow-svg text', { hasText: 'QA link' })).toHaveCount(1);
    expect(await page.evaluate(() => (window as any).__noReload)).toBe('kept');
  });
});
