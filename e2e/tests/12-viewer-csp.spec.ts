// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import { Page } from '@playwright/test';
import { test, expect, openCanvas, board, bar, settled, zoomInOn, emptyPoint } from './fixtures';

// The viewer is served with a hash-based CSP (issue #12). Every browser fires
// securitypolicyviolation for a blocked script, style, frame, image or request, also where the
// console message is only a warning (Firefox), so the page collects those events itself.
async function watchCsp(page: Page) {
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      (window as any).__csp.push(`${e.violatedDirective} ${e.blockedURI}`);
    });
  });
}
const violations = (page: Page) => page.evaluate(() => (window as any).__csp as string[]);

test.describe('Viewer CSP', () => {
  test('Opening, panning, zooming, comments, drag save and live updates raise no CSP violation', async ({ page, sandbox, consoleErrors }) => {
    sandbox.cli('comment', sandbox.idea, 'T01-Home.html', 'CSP check');
    const srv = await sandbox.serveRegistry();
    await watchCsp(page);
    const resp = await page.goto(srv.origin + '/alpha/trailmate/');
    const csp = resp!.headers()['content-security-policy'];
    expect(csp).toContain("script-src 'sha256-");
    expect(csp).not.toContain('unsafe-eval');
    await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
    await settled(page);
    // 1. Pan
    const p = await emptyPoint(page);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 120, p.y + 60, { steps: 6 });
    await page.mouse.up();
    await settled(page);
    // 2. Zoom in: thumbnails, then live board iframes
    await zoomInOn(page, 'T01-Home.html', 0.6);
    const frame = page.frameLocator('.board[data-file="T01-Home.html"] iframe').last();
    await expect(frame.getByText('Pine Ridge Loop').first()).toBeVisible({ timeout: 10_000 });
    // 3. Comment panel
    await board(page, 'T01-Home.html').locator('.cmt-badge').click();
    await expect(page.locator('#cmt-panel')).toBeVisible();
    await page.keyboard.press('Escape');
    // 4. Drag a board: the layout POST
    const x0 = sandbox.canvasJson().boards['T01-Home.html'].x;
    const box = (await bar(page, 'T01-Home.html').boundingBox())!;
    await page.mouse.move(box.x + 20, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 80, box.y + 40, { steps: 6 });
    await page.mouse.up();
    await expect.poll(() => sandbox.canvasJson().boards['T01-Home.html'].x, { timeout: 5_000 }).not.toBe(x0);
    // 5. A status change arrives over the event stream
    sandbox.cli('status', sandbox.idea, 'T03-Invite.html', 'approved');
    await expect(board(page, 'T03-Invite.html').locator('.status-badge.approved')).toHaveCount(1, { timeout: 5_000 });
    expect(await violations(page)).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });

  test('The read-only share viewer runs its injected scripts under the CSP', async ({ page, sandbox, consoleErrors }) => {
    const srv = await sandbox.serve([sandbox.alphaDesign, '--share', '--minutes', '5']);
    await watchCsp(page);
    await page.goto(`${srv.origin}/?t=${srv.token}`);
    await expect(page).toHaveURL(`${srv.origin}/`);
    await page.getByRole('link', { name: /trailmate/ }).click();
    await page.waitForURL(`${srv.origin}/trailmate/`);
    await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
    await settled(page);
    // The injected read-only flag ran: the badge shows
    await expect(page.locator('#ro-badge')).toBeVisible();
    await zoomInOn(page, 'T01-Home.html', 0.6);
    const frame = page.frameLocator('.board[data-file="T01-Home.html"] iframe').last();
    await expect(frame.getByText('Pine Ridge Loop').first()).toBeVisible({ timeout: 10_000 });
    // Boards load through the injected asset prefix
    expect(await board(page, 'T01-Home.html').locator('iframe').last().getAttribute('src')).toMatch(/^\/_k\/[0-9a-f]+\//);
    expect(await violations(page)).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
