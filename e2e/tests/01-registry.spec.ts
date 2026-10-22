// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { test, expect, openCanvas, shot } from './fixtures';

test.describe('Registry index', () => {
  test('Lists registered projects and their ideas', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    // 2. Open /
    await page.goto(srv.origin + '/');
    await expect(page.getByRole('heading', { name: 'Mockup Canvas' })).toBeVisible();
    const project = page.locator('section.project', { hasText: 'alpha' });
    await expect(project).toBeVisible();
    const link = project.getByRole('link', { name: /trailmate/ });
    await expect(link).toContainText('6 artboards');
    await shot(page, testInfo, '01-registry-index');
    await link.click();
    await expect(page).toHaveURL(/\/alpha\/trailmate\/$/);
    await openCanvas(page, page.url());
    await expect(page.locator('.board')).toHaveCount(6);
  });

  test('Adds a project with a valid path', async ({ page, sandbox }) => {
    const beta = sandbox.makeBeta();
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    // 1. Fill path and name
    await page.getByLabel('Design folder path').fill(beta);
    await page.getByLabel(/^Name/).fill('beta');
    // 2. Click Add
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.locator('#add-msg')).toHaveText('Added: beta');
    await expect(page.locator('section.project', { hasText: 'beta' })).toBeVisible();
    expect(sandbox.rootsFile().map((r) => r.name)).toEqual(['alpha', 'beta']);
  });

  test('Shows errors for invalid paths', async ({ page, sandbox }, testInfo) => {
    const srv = await sandbox.serveRegistry();
    const noCanvas = path.join(sandbox.home, 'plain');
    fs.mkdirSync(path.join(noCanvas, 'sub'), { recursive: true });
    const hidden = path.join(sandbox.home, '.secret', 'design');
    fs.cpSync(sandbox.idea, path.join(hidden, 'trailmate'), { recursive: true });
    await page.goto(srv.origin + '/');
    const msg = page.locator('#add-msg');
    const pathInput = page.getByLabel('Design folder path');
    const add = page.getByRole('button', { name: 'Add', exact: true });

    const nameInput = page.getByLabel(/^Name/);
    // [path, name, expected message]; the default name is the parent folder, so the duplicate
    // path case needs a different name to reach the path check
    const cases: Array<[string, string, RegExp]> = [
      ['', '', /Enter a path/],
      ['/etc', '', /Paths outside the home directory are not allowed/],
      [path.join(sandbox.home, 'nope', 'design'), '', /Directory does not exist/],
      [noCanvas, '', /Not a mockup-canvas design folder/],
      [sandbox.alphaDesign, '', /Name already in use: alpha/],
      [sandbox.alphaDesign, 'other', /Already registered: alpha/],
      [hidden, '', /System or hidden directories are not allowed/],
    ];
    for (const [value, name, expected] of cases) {
      await pathInput.fill(value);
      await nameInput.fill(name);
      await add.click();
      await expect(msg).toHaveText(expected);
      await expect(msg).toHaveClass(/err/);
    }
    await shot(page, testInfo, '01-registry-add-error');
    await page.reload();
    await expect(page.locator('section.project')).toHaveCount(1);
    expect(sandbox.rootsFile()).toHaveLength(1);
  });

  test('Scan finds folders and adds the checked ones', async ({ page, sandbox }, testInfo) => {
    sandbox.makeBeta();
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    // 1. Fill the folders to search
    await page.getByLabel(/Folders to search/).fill(sandbox.work);
    // 2. Search
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.locator('#scan-msg')).toHaveText('Found 2');
    const items = page.locator('#scan-results .scan-item');
    const alpha = items.filter({ hasText: 'alpha' });
    const beta = items.filter({ hasText: 'beta' });
    await expect(alpha.locator('input')).toBeDisabled();
    await expect(alpha).toContainText('already registered');
    await expect(beta.locator('input')).toBeChecked();
    await shot(page, testInfo, '01-registry-scan');
    // 3. Add selected
    await page.getByRole('button', { name: 'Add selected' }).click();
    await expect(page.locator('#scan-msg')).toHaveText('Added 1');
    await expect(page.locator('section.project', { hasText: 'beta' })).toBeVisible();
    expect(sandbox.rootsFile().map((r) => r.name).sort()).toEqual(['alpha', 'beta']);
  });

  test('Remove from list asks for confirmation and leaves files untouched', async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await page.goto(srv.origin + '/');
    const project = page.locator('section.project', { hasText: 'alpha' });
    // 1. Dismiss the confirm dialog
    let dialogText = '';
    page.once('dialog', (d) => { dialogText = d.message(); void d.dismiss(); });
    await project.getByRole('button', { name: 'Remove from list' }).click();
    await expect.poll(() => dialogText).toContain('No files are deleted');
    await expect(project).toBeVisible();
    expect(sandbox.rootsFile()).toHaveLength(1);
    // 2. Accept
    page.once('dialog', (d) => void d.accept());
    await project.getByRole('button', { name: 'Remove from list' }).click();
    await expect(page.locator('section.project', { hasText: 'alpha' })).toHaveCount(0);
    expect(sandbox.rootsFile()).toHaveLength(0);
    expect(fs.existsSync(path.join(sandbox.idea, 'canvas.json'))).toBe(true);
    expect(fs.readdirSync(path.join(sandbox.idea, 'boards'))).toHaveLength(6);
  });
});
