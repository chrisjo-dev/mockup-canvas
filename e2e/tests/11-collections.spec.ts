// spec: specs/mockup-canvas-journeys.md (section 1.6, collections across projects)
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, shot } from './fixtures';

const card = (page: Page, idea: string) => page.locator('article.gc', { has: page.locator('a.cl', { hasText: idea }) });
const rail = (page: Page) => page.locator('nav.rail');

async function cardMenu(page: Page, idea: string) {
  const c = card(page, idea);
  await c.hover();
  await c.getByRole('button', { name: 'More actions for ' + idea }).click();
  await page.getByRole('menuitem', { name: 'Move to collection' }).click();
  await expect(page.getByRole('menu', { name: 'Move to collection' })).toBeVisible();
}

test('Collections gather ideas from several projects and follow the rail, URL, and filters', async ({ page, sandbox, consoleErrors }, testInfo) => {
  sandbox.makeBeta();
  const srv = await sandbox.serveRegistry([[sandbox.betaDesign, 'beta']]);
  const file = path.join(sandbox.data, 'roots.json');
  const cols = () => JSON.parse(fs.readFileSync(file, 'utf8')).collections;
  await page.goto(srv.origin + '/');
  await expect(card(page, 'second')).toBeVisible();
  await expect(rail(page).getByRole('heading', { name: 'Collections' })).toHaveCount(0);

  // A new collection from the card menu: a field inside the menu, Escape goes back, Enter saves
  await cardMenu(page, 'trailmate');
  await page.getByRole('menuitem', { name: 'New collection' }).click();
  const name = page.getByRole('textbox', { name: 'New collection name' });
  await expect(name).toBeFocused();
  await name.press('Escape');
  await expect(page.getByRole('menuitem', { name: 'New collection' })).toBeVisible();
  await page.getByRole('menuitem', { name: 'New collection' }).click();
  await name.fill('Lily');
  await name.press('Enter');
  await expect(rail(page).getByRole('heading', { name: 'Collections' })).toBeVisible();
  await expect(rail(page).getByRole('button', { name: /Lily/ })).toContainText('1');
  expect(cols()).toEqual({ Lily: ['alpha/trailmate'] });

  // An idea from a second project joins it; the collection page lists both
  await cardMenu(page, 'second');
  await page.getByRole('menuitemradio', { name: /Lily/ }).click();
  await expect(rail(page).getByRole('button', { name: /Lily/ })).toContainText('2');
  await rail(page).getByRole('button', { name: /Lily/ }).click();
  await expect(page).toHaveURL(/col=Lily/);
  await expect(page.getByRole('heading', { name: /Lily/ })).toContainText('2 ideas from 2 projects');
  await expect(page.locator('.mh .incl')).toHaveText('Ideas picked from alpha and beta');
  await expect(page.locator('article.gc')).toHaveCount(2);
  await page.reload();
  await expect(page.locator('article.gc')).toHaveCount(2);
  await expect(rail(page).getByRole('button', { name: /Lily/ })).toHaveAttribute('aria-pressed', 'true');
  await shot(page, testInfo, '11-collection');
  await rail(page).getByRole('button', { name: /Needs decision/ }).click();
  await expect(page).toHaveURL(/col=Lily/);
  await expect(page.locator('.active')).toContainText('Lily');
  await expect(page.locator('.mh p')).toHaveText('2 ideas and 8 boards match');

  // The whole beta project from the project menu, by keyboard
  await rail(page).getByRole('button', { name: /^beta/ }).click();
  await page.getByRole('button', { name: 'Project menu' }).click();
  await page.getByRole('menuitem', { name: 'Add to collection' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('menu', { name: 'Add beta to collection' })).toBeVisible();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('menu', { name: 'Project actions' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: 'Add to collection' })).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await page.getByRole('menuitemradio', { name: /Lily/ }).click();
  await expect.poll(cols).toEqual({ Lily: ['alpha/trailmate', 'beta/second', 'beta'] });
  expect(sandbox.rootsFile().map((r: any) => r.name)).toEqual(['alpha', 'beta']);
  await page.goto(srv.origin + '/?col=Lily');
  await expect(page.locator('.mh .incl')).toHaveText('Includes all ofbetaand ideas picked from alpha');

  // Take every key out: the collection, its URL, and the Collections heading go away
  await cardMenu(page, 'trailmate');
  await page.getByRole('menuitem', { name: 'Remove from collection' }).click();
  await expect(page.locator('article.gc')).toHaveCount(1);
  await cardMenu(page, 'second');
  await page.getByRole('menuitem', { name: 'Remove from collection' }).click();
  await expect.poll(cols).toEqual({ Lily: ['beta'] });
  await rail(page).getByRole('button', { name: /^beta/ }).click();
  await page.getByRole('button', { name: 'Project menu' }).click();
  await page.getByRole('menuitem', { name: 'Add to collection' }).click();
  await page.getByRole('menuitem', { name: 'Remove beta from collection' }).click();
  await expect(rail(page).getByRole('heading', { name: 'Collections' })).toHaveCount(0);
  await expect.poll(cols).toBeUndefined();
  await page.goto(srv.origin + '/?col=Lily');
  await expect(page.getByRole('heading', { name: 'All ideas' })).toBeVisible();
  await expect(page).not.toHaveURL(/col=/);
  expect(consoleErrors).toEqual([]);
});
