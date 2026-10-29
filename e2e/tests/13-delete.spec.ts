// spec: D-B23 to D-B25 (design/canvas-dashboard), issue #14: delete moves to .trash, Undo puts it back
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, openCanvas, board, bar, settled, zoomInOn, shot } from './fixtures';

const card = (page: Page, idea: string) => page.locator('article.gc', { has: page.locator('a.cl', { hasText: idea }) });
const trash = (design: string) => (fs.existsSync(path.join(design, '.trash')) ? fs.readdirSync(path.join(design, '.trash')) : []);

test('Delete an idea from the dashboard, then Undo', async ({ page, sandbox, consoleErrors }, testInfo) => {
  sandbox.makeBeta();
  const srv = await sandbox.serveRegistry([[sandbox.betaDesign, 'beta']]);
  await page.goto(srv.origin + '/');
  const c = card(page, 'second');
  await c.hover();
  await c.getByRole('button', { name: 'More actions for second' }).click();
  await page.getByRole('menuitem', { name: 'Delete idea' }).click();

  const dlg = page.getByRole('alertdialog', { name: 'Delete second?' });
  await expect(dlg).toContainText('6 boards');
  await expect(dlg).toContainText('design/.trash/');
  await expect(dlg.getByRole('button', { name: 'Cancel' })).toBeFocused();   // Enter does not delete
  await shot(page, testInfo, '13-confirm-idea');
  await page.keyboard.press('Escape');
  await expect(dlg).toHaveCount(0);
  expect(fs.existsSync(path.join(sandbox.betaDesign, 'second'))).toBe(true);

  await c.hover();
  await c.getByRole('button', { name: 'More actions for second' }).click();
  await page.getByRole('menuitem', { name: 'Delete idea' }).click();
  await dlg.getByRole('button', { name: 'Delete' }).click();
  await expect(card(page, 'second')).toHaveCount(0);
  expect(fs.existsSync(path.join(sandbox.betaDesign, 'second'))).toBe(false);
  expect(trash(sandbox.betaDesign)).toEqual([expect.stringMatching(/^second-\d{8}T\d{6}Z$/)]);
  const toast = page.locator('#toast');
  await expect(toast).toContainText('Deleted second');
  await shot(page, testInfo, '13-toast-idea');

  await toast.getByRole('button', { name: 'Undo' }).click();
  await expect(card(page, 'second')).toBeVisible();
  await expect(toast).toContainText('Restored second');
  expect(fs.existsSync(path.join(sandbox.betaDesign, 'second', 'canvas.json'))).toBe(true);
  expect(trash(sandbox.betaDesign)).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('Delete a board on the canvas, then Undo brings back its arrows and comments', async ({ page, sandbox, consoleErrors }, testInfo) => {
  const cj = path.join(sandbox.idea, 'canvas.json');
  sandbox.cli('comment', sandbox.idea, 'T03-Invite.html', 'keep me');
  const before = JSON.parse(fs.readFileSync(cj, 'utf8'));
  const srv = await sandbox.serveRegistry();
  await openCanvas(page, srv.origin + '/alpha/trailmate/');
  await settled(page);
  await zoomInOn(page, 'T03-Invite.html', 0.5);
  await bar(page, 'T03-Invite.html').getByRole('button', { name: 'Board menu' }).click();
  await page.getByRole('menuitem', { name: 'Delete board' }).click();
  const dlg = page.getByRole('alertdialog', { name: 'Delete T03-Invite?' });
  await expect(dlg).toContainText('1 comment');
  await expect(dlg).toContainText('design/.trash/trailmate/');
  await expect(dlg.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await shot(page, testInfo, '13-confirm-board');
  await dlg.getByRole('button', { name: 'Delete' }).click();

  await expect(board(page, 'T03-Invite.html')).toHaveCount(0);
  const after = JSON.parse(fs.readFileSync(cj, 'utf8'));
  expect(Object.keys(after.boards)).not.toContain('T03-Invite.html');
  expect(after.links.some((l: any) => l.from === 'T03-Invite.html' || l.to === 'T03-Invite.html')).toBe(false);
  expect(fs.existsSync(path.join(sandbox.idea, 'boards', 'T03-Invite.html'))).toBe(false);
  const toast = page.locator('#toast');
  await expect(toast).toContainText('Deleted T03-Invite');
  await shot(page, testInfo, '13-toast-board');

  await toast.getByRole('button', { name: 'Undo' }).click();
  await expect(board(page, 'T03-Invite.html')).toHaveCount(1);
  await expect(toast).toContainText('Restored T03-Invite');
  const back = JSON.parse(fs.readFileSync(cj, 'utf8'));
  expect(back.boards['T03-Invite.html']).toEqual(before.boards['T03-Invite.html']);
  expect(new Set(back.links.map((l: any) => JSON.stringify(l)))).toEqual(new Set(before.links.map((l: any) => JSON.stringify(l))));
  expect(fs.existsSync(path.join(sandbox.idea, 'boards', 'T03-Invite.html'))).toBe(true);
  expect(consoleErrors).toEqual([]);
});

test('Delete a collection, then Undo; share pages have no delete', async ({ page, sandbox, consoleErrors }) => {
  const srv = await sandbox.serveRegistry();
  const file = path.join(sandbox.data, 'roots.json');
  const cols = () => JSON.parse(fs.readFileSync(file, 'utf8')).collections;
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  fs.writeFileSync(file, JSON.stringify({ ...data, collections: { Lily: ['alpha/trailmate'] } }));
  await page.goto(srv.origin + '/?col=Lily');
  await page.getByRole('button', { name: 'Collection menu' }).click();
  await page.getByRole('menuitem', { name: 'Delete collection' }).click();
  const dlg = page.getByRole('alertdialog', { name: 'Delete the Lily collection?' });
  await expect(dlg).toContainText('stay where they are');
  await dlg.getByRole('button', { name: 'Delete' }).click();
  await expect(page.locator('nav.rail')).not.toContainText('Lily');
  expect(cols()).toBeUndefined();
  expect(fs.existsSync(sandbox.idea)).toBe(true);
  await page.locator('#toast').getByRole('button', { name: 'Undo' }).click();
  await expect(page.locator('nav.rail').getByRole('button', { name: /Lily/ })).toBeVisible();
  expect(cols()).toEqual({ Lily: ['alpha/trailmate'] });
  expect(consoleErrors).toEqual([]);

  // --share-edit lets a phone move boards, but never delete them
  const share = await sandbox.serve([sandbox.alphaDesign, '--share', '--share-edit', '--minutes', '5']);
  await page.goto(share.origin + '/?t=' + share.token);
  await expect(card(page, 'trailmate')).toBeVisible();
  await expect(page.getByRole('button', { name: /More actions/ })).toHaveCount(0);
  await openCanvas(page, share.origin + '/trailmate/');
  await expect(page.locator('.bar-more')).toHaveCount(0);
  await bar(page, 'T01-Home.html').click({ button: 'right' });
  await expect(page.locator('#board-menu')).toBeHidden();
});
