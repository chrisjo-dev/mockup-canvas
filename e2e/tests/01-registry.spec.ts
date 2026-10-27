// spec: specs/mockup-canvas-journeys.md (section 1, registry dashboard)
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, shot } from './fixtures';

const card = (page: Page, idea: string) => page.locator('article.gc', { has: page.locator('a.cl', { hasText: idea }) });
const rail = (page: Page) => page.locator('nav.rail');

test.describe('Registry dashboard', () => {
  test('Opens the dashboard, shows the idea card with a thumbnail, and opens the canvas', async ({ page, sandbox, consoleErrors }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await expect(page.getByRole('heading', { name: 'All ideas' })).toBeVisible();
    await expect(page.locator('.mh p')).toHaveText('1 idea, 6 boards, 0 open comments');
    const c = card(page, 'trailmate');
    await expect(c).toContainText('6 boards');
    await expect(c.locator('.meter')).toHaveAttribute('aria-label', '2 approved, 4 draft, 0 rejected of 6');
    await expect(rail(page).getByRole('button', { name: /alpha/ })).toContainText('1');
    // Thumbnails come from the thumbnail endpoint (PNG), never an iframe
    await expect(c.locator('.gw img').first()).toBeVisible({ timeout: 45_000 });
    expect(await page.locator('iframe').count()).toBe(0);
    await shot(page, testInfo, '01-dashboard');
    await c.locator('a.cl').click();
    await expect(page).toHaveURL(/\/alpha\/trailmate\/$/);
    await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
    expect(consoleErrors).toEqual([]);
  });

  test('Status filter and search narrow the gallery', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await rail(page).getByRole('button', { name: /Needs decision/ }).click();
    await expect(page).toHaveURL(/filter=needs-decision/);
    await expect(page.getByRole('heading', { name: 'Needs decision' })).toBeVisible();
    await expect(page.locator('.mh p')).toHaveText('1 idea and 4 boards match');
    // the palette's last action filters the gallery by the query
    await page.keyboard.press('/');
    await page.getByRole('combobox').fill('plan');
    await page.getByRole('option', { name: /Filter the gallery by "plan"/ }).click();
    await expect(page).toHaveURL(/q=plan/);
    await expect(page.locator('.mh p')).toHaveText('1 idea and 1 board match');
    await expect(page.locator('a.tile')).toHaveCount(1);
    await expect(page.locator('a.tile')).toContainText('T04');
    await shot(page, testInfo, '01-filtered');
    // Escape clears the search, Clear all the rest
    await page.locator('main').click({ position: { x: 5, y: 5 } });
    await page.keyboard.press('Escape');
    await expect(page).not.toHaveURL(/q=plan/);
    await page.getByRole('button', { name: 'Clear all' }).click();
    await expect(page.getByRole('heading', { name: 'All ideas' })).toBeVisible();
  });

  test('Command palette finds boards, highlights matches, and says when nothing matches', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+k' : 'Control+k');
    const input = page.getByRole('combobox');
    await expect(input).toBeFocused();
    await expect(page.locator('.pal .grp')).toHaveText(['Recent ideas', 'Recent boards', 'Actions']);
    await input.fill('trail');
    await expect(page.locator('.pal .cnt')).toHaveText(/\d+ results?/);
    const row = page.getByRole('option', { name: /T02 Trail Detail/ });
    await expect(row.locator('mark')).toHaveText('Trail');
    await shot(page, testInfo, '01-palette');
    await input.fill('zzzz');
    await expect(page.getByRole('heading', { name: 'Nothing matches "zzzz"' })).toBeVisible();
    await page.getByRole('button', { name: 'Clear search' }).click();
    await expect(input).toHaveValue('');
    await input.fill('home');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowUp');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/alpha\/trailmate\/#T01-Home$/);
  });

  test('Add project shows the server error, suggests the design folder, and adds it', async ({ page, sandbox }, testInfo) => {
    sandbox.makeBeta();
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await rail(page).getByRole('button', { name: 'Add project' }).click();
    const dlg = page.getByRole('dialog', { name: 'Add a project' });
    const pathIn = dlg.getByLabel('Design folder');
    const add = dlg.getByRole('button', { name: 'Add project' });
    await pathIn.fill('/etc');
    await expect(dlg.getByRole('alert')).toHaveText(/Paths outside the home directory are not allowed/);
    await expect(add).toBeDisabled();
    await pathIn.fill(path.join(sandbox.home, 'nope'));
    await expect(dlg.getByRole('alert')).toHaveText(/Directory does not exist/);
    // The parent of a design folder: the server suggests the design/ inside it
    await pathIn.fill(path.dirname(sandbox.betaDesign));
    await expect(dlg.getByRole('alert')).toHaveText(/no subfolder contains canvas.json/);
    await expect(dlg.locator('.suggest')).toContainText('1 idea, 6 boards');
    await expect(add).toBeDisabled();
    await shot(page, testInfo, '01-add-error');
    await dlg.getByRole('button', { name: 'Use this folder' }).click();
    await expect(dlg.locator('.okmsg')).toHaveText('Found 1 idea, 6 boards');
    await expect(dlg.locator('.df .mono')).toHaveText('canvas roots add ~/work/beta/design');
    await add.click();
    await expect(dlg).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'beta' })).toBeVisible();
    await expect(card(page, 'second')).toBeVisible();
    expect(sandbox.rootsFile().map((r) => r.name)).toEqual(['alpha', 'beta']);
  });

  test('Find in folders lists design folders and adds the checked ones', async ({ page, sandbox }) => {
    sandbox.makeBeta();
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await rail(page).getByRole('button', { name: 'Find in folders' }).click();
    const dlg = page.getByRole('dialog', { name: 'Add a project' });
    await dlg.getByLabel('Folders to search').fill(sandbox.work);
    await dlg.getByRole('button', { name: 'Search' }).click();
    await expect(dlg.locator('.status-line')).toHaveText('Found 2 design folders');
    await expect(dlg.locator('.scanitem', { hasText: 'alpha' }).locator('input')).toBeDisabled();
    await expect(dlg.locator('.scanitem', { hasText: 'beta' }).locator('input')).toBeChecked();
    await dlg.getByRole('button', { name: 'Add 1 project' }).click();
    await expect(dlg).toHaveCount(0);
    expect(sandbox.rootsFile().map((r) => r.name).sort()).toEqual(['alpha', 'beta']);
  });

  test('A missing folder shows a warning page and can be removed from the list', async ({ page, sandbox }, testInfo) => {
    const beta = sandbox.makeBeta();
    const srv = await sandbox.serveRegistry([[beta, 'beta']]);
    fs.renameSync(path.dirname(beta), path.join(sandbox.work, 'beta-moved'));
    await page.goto(srv.origin + '/');
    const row = rail(page).getByRole('button', { name: /beta/ });
    await expect(row).toContainText('Missing');
    await row.click();
    await expect(page.getByRole('heading', { name: 'This folder is not on disk' })).toBeVisible();
    await expect(page.locator('.miss .code')).toHaveText('$ canvas roots remove beta');
    await shot(page, testInfo, '01-missing');
    page.once('dialog', (d) => { expect(d.message()).toContain('No files are deleted'); void d.accept(); });
    await page.getByRole('button', { name: 'Remove from list' }).click();
    await expect(rail(page).getByRole('button', { name: /beta/ })).toHaveCount(0);
    expect(sandbox.rootsFile().map((r) => r.name)).toEqual(['alpha']);
    expect(fs.existsSync(path.join(sandbox.work, 'beta-moved', 'design', 'second', 'canvas.json'))).toBe(true);
  });

  test('Theme toggle (Shift T) and Compact size persist across reloads', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    const html = page.locator('html');
    await expect(html).not.toHaveAttribute('data-theme', 'light');
    await page.keyboard.press('Shift+T');
    await expect(html).toHaveAttribute('data-theme', 'light');
    await page.getByRole('button', { name: 'Compact' }).click();
    await expect(page.locator('.grid.compact')).toBeVisible();
    await shot(page, testInfo, '01-light-compact');
    await page.reload();
    await expect(html).toHaveAttribute('data-theme', 'light');
    await expect(page.locator('.grid.compact')).toBeVisible();
    await page.getByRole('button', { name: /Switch to dark theme/ }).click();
    await expect(html).not.toHaveAttribute('data-theme', 'light');
  });

  test('Card menu copies the URL and the project view lists recent boards', async ({ page, sandbox, context, browserName }) => {
    test.skip(browserName !== 'chromium', 'clipboard permissions are Chromium only in Playwright');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    const c = card(page, 'trailmate');
    await c.hover();
    await c.getByRole('button', { name: 'More actions for trailmate' }).click();
    await expect(page.getByRole('menu', { name: 'Idea actions' })).toBeVisible();
    await page.getByRole('menuitem', { name: 'Copy URL' }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(srv.origin + '/alpha/trailmate/');
    await rail(page).getByRole('button', { name: /alpha/ }).click();
    await expect(page).toHaveURL(/project=alpha/);
    await expect(page.locator('.tiles a.tile')).toHaveCount(6);
    await page.getByRole('button', { name: 'All 6 boards' }).click();
    await expect(page.getByRole('heading', { name: 'All boards in alpha' })).toBeVisible();
    await page.getByRole('button', { name: 'Approved', exact: true }).click();
    await expect(page.locator('a.tile')).toHaveCount(2);
  });

  test('Copied shell commands quote paths and names', async ({ page, sandbox }) => {
    const odd = path.join(sandbox.work, "my proj's", 'design');
    fs.cpSync(sandbox.idea, path.join(odd, 'second'), { recursive: true });
    const srv = await sandbox.serveRegistry([[odd, 'odd one']]);
    await page.goto(srv.origin + '/?project=' + encodeURIComponent('odd one'));
    await expect(page.locator('.add-idea .mono')).toHaveText(`canvas new ~/'work/my proj'\\''s/design' <idea>`);
    fs.renameSync(path.dirname(odd), path.join(sandbox.work, 'elsewhere'));
    await page.reload();
    await expect(page.locator('.miss .code')).toHaveText(`$ canvas roots remove 'odd one'`);
    await page.getByRole('button', { name: 'Locate folder' }).click();
    const dlg = page.getByRole('dialog', { name: 'Add a project' });
    fs.renameSync(path.join(sandbox.work, 'elsewhere'), path.join(sandbox.work, 'else where'));
    await dlg.getByLabel('Design folder').fill('~/work/else where/design');
    await expect(dlg.locator('.df .mono')).toHaveText(`canvas roots add ~/'work/else where/design' --name 'odd one'`);
    await expect(dlg.locator('.okmsg')).toContainText('Updates the missing folder of odd one');
  });

  test('Rail lists the most recently edited project first; loading text never counts past the boards', async ({ page, sandbox }) => {
    const beta = sandbox.makeBeta();
    const old = new Date(Date.now() - 3_600_000);
    for (const f of fs.readdirSync(path.join(sandbox.idea, 'boards'))) fs.utimesSync(path.join(sandbox.idea, 'boards', f), old, old);
    fs.utimesSync(path.join(sandbox.idea, 'canvas.json'), old, old);
    const srv = await sandbox.serveRegistry([[beta, 'beta']]);
    await page.goto(srv.origin + '/');
    const rows = page.locator('nav.rail ul').first().locator('.ri .lb');
    await expect(rows).toHaveText(['All ideas', 'beta', 'alpha']);
    // second idea in the loading state has "2 of" its boards; one desktop board means 1 of 1
    const web = new Date(Date.now() + 1000);
    const older = new Date(Date.now() - 600_000);
    for (const f of fs.readdirSync(path.join(sandbox.idea, 'boards'))) fs.utimesSync(path.join(sandbox.idea, 'boards', f), older, older);
    fs.utimesSync(path.join(sandbox.idea, 'boards', 'T06-WebLanding.html'), web, web);
    fs.utimesSync(path.join(sandbox.idea, 'canvas.json'), older, older);
    await page.goto(srv.origin + '/?state=loading');
    const notes = page.locator('.wnote');
    await expect(notes.first()).toBeVisible();
    for (const t of await notes.allTextContents()) {
      const m = t.match(/(\d+) of (\d+)/)!;
      expect(Number(m[1])).toBeLessThanOrEqual(Number(m[2]));
    }
  });

  test('Palette names line up for ideas, boards, and actions', async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/?palette=t0');
    const xs = await page.locator('.pal li .lt').evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().left)));
    expect(xs.length).toBeGreaterThan(2);
    expect(new Set(xs).size).toBe(1);
  });

  test('All boards: each idea shows its first row and Show all opens that idea', async ({ page, sandbox }) => {
    sandbox.makeBeta();
    fs.cpSync(sandbox.idea, path.join(sandbox.alphaDesign, 'trail-2'), { recursive: true });
    const srv = await sandbox.serveRegistry();
    await page.setViewportSize({ width: 900, height: 800 });   // 4 tiles per row
    await page.goto(srv.origin + '/?project=alpha&page=boards');
    await expect(page.locator('.allb .tiles')).toHaveCount(2);
    for (const t of await page.locator('.allb .tiles').all()) await expect(t.locator('a.tile')).toHaveCount(4);
    await expect(page.locator('.more')).toHaveText('Showing 8 of 12. Show all opens one idea and loads its boards 48 at a time.');
    await page.getByRole('button', { name: 'Show all 6' }).first().click();
    await expect(page).toHaveURL(/idea=/);
    await expect(page.locator('a.tile')).toHaveCount(6);
    await expect(page.locator('.more')).toHaveText('Showing all 6 boards.');
  });

  test('The canvas ignores #__proto__ and fits every board', async ({ page, sandbox, consoleErrors }) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/alpha/trailmate/#__proto__');
    await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
    await expect(page.locator('.board')).toHaveCount(6);
    expect(consoleErrors).toEqual([]);
  });

  test('Phone layout: one card per row, 44 px tap targets, palette sheet @mobile', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    await expect(page.locator('nav.rail')).toBeHidden();
    const tab = page.locator('.tabs .chip').first();
    expect((await tab.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    const search = page.locator('#tb-search');
    const box = (await search.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
    await search.tap();
    const sheet = page.getByRole('dialog', { name: 'Command palette' });
    await expect(sheet).toBeVisible();
    await expect.poll(async () => Math.round((await sheet.boundingBox())!.y)).toBe(44);
    await page.getByRole('combobox').fill('habit');
    await expect(page.getByRole('heading', { name: 'Nothing matches "habit"' })).toBeVisible();
    await shot(page, testInfo, '01-phone-palette');
    await page.getByRole('button', { name: 'Clear' }).first().tap();
    await page.keyboard.press('Escape');
    expect((await page.locator('a.brand').boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await page.getByRole('button', { name: 'Add project' }).first().tap();
    // The sheet slides in; measure after the animation settles (sub-pixel heights during the transform)
    for (const tab of await page.getByRole('tab').all()) {
      await expect.poll(async () => Math.round((await tab.boundingBox())!.height)).toBeGreaterThanOrEqual(44);
    }
  });
});
