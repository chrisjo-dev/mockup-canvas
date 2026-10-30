// spec: D-B26 to D-B29 (design/canvas-dashboard), issue #15: pins point at a spot so the agent knows what to change
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { test, expect, openCanvas, board, settled, zoomInOn, shot } from './fixtures';

const pins = (cj: string, file: string) =>
  (JSON.parse(fs.readFileSync(cj, 'utf8')).boards[file].comments || []).filter((c: any) => /^p[0-9a-f]{8}$/.test(c.id || ''));

test('Point at a spot, the server finds the element, copy it for the AI, resolve', async ({ page, context, sandbox, consoleErrors, browserName }, testInfo) => {
  const cj = path.join(sandbox.idea, 'canvas.json');
  const srv = await sandbox.serveRegistry();
  await openCanvas(page, srv.origin + '/alpha/trailmate/');
  await settled(page);
  await zoomInOn(page, 'T01-Home.html', 0.5);

  // Point mode: toolbar button, crosshair, hint
  await page.getByRole('button', { name: /Point/ }).click();
  await expect(page.getByRole('button', { name: /Point/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#pin-hint')).toBeVisible();
  const b = (await board(page, 'T01-Home.html').boundingBox())!;
  const { s } = await page.locator('#canvas').evaluate((el) => ({ s: +((el as HTMLElement).style.transform.match(/scale\(([\d.]+)\)/) || [0, 1])[1] }));
  await page.mouse.click(b.x + 195 * s, b.y + 330 * s);   // the quick actions row of the sample board

  const note = page.getByRole('textbox', { name: 'Note' });
  await expect(note).toBeFocused();
  await expect(page.locator('#pin-cmp')).toContainText('Point');
  await page.keyboard.type('Make these buttons bigger');
  await shot(page, testInfo, '14-compose');
  await page.keyboard.press('Enter');

  await expect(page.locator('#toast')).toContainText('Pin 1 saved');
  await expect(page.locator('#pin-hint')).toBeHidden();
  const pop = page.locator('#pin-pop');
  await expect(pop).toContainText('Make these buttons bigger');
  // The server's Chrome fills in the element and the crop
  await expect(pop.locator('.sel')).not.toBeEmpty({ timeout: 20_000 });
  await expect(pop.locator('img')).toHaveJSProperty('complete', true);
  const [p] = pins(cj, 'T01-Home.html');
  expect(p).toMatchObject({ text: 'Make these buttons bigger', state: 'found', at: { w: 0, h: 0 } });
  expect(Math.abs(p.at.x - 195) + Math.abs(p.at.y - 330)).toBeLessThanOrEqual(3);   // board px, rounded
  expect(p.target.selector.length).toBeGreaterThan(0);
  expect(fs.existsSync(path.join(sandbox.idea, 'render', '.pins', p.img))).toBe(true);
  await shot(page, testInfo, '14-details');

  if (browserName === 'chromium') {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await pop.getByRole('button', { name: 'Copy for AI' }).click();
    await expect(page.locator('#toast')).toContainText('Copied pin 1 for the AI');
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text).toBe(`trailmate/T01-Home.html pin 1: "Make these buttons bigger" -> ${p.target.selector}` +
      (p.target.text ? ` "${p.target.text.slice(0, 60)}"` : '') + ' (see canvas pins)');
  }

  // Resolve, then the marker turns gray; P hides the pins
  await pop.getByRole('button', { name: 'Resolve' }).click();
  await expect(pop).toContainText('Pin 1, resolved');
  await expect(board(page, 'T01-Home.html').locator('.pin')).toHaveClass(/done/);
  expect(pins(cj, 'T01-Home.html')[0].resolved).toBeTruthy();
  await page.keyboard.press('Escape');
  await expect(pop).toBeHidden();
  await page.keyboard.press('p');
  await expect(board(page, 'T01-Home.html').locator('.pin')).toHaveCount(0);
  await page.keyboard.press('p');
  await expect(board(page, 'T01-Home.html').locator('.pin')).toHaveCount(1);

  // An area pin by dragging, Esc in the note box throws it away
  await page.keyboard.press('c');
  const b2 = (await board(page, 'T01-Home.html').boundingBox())!;
  await page.mouse.move(b2.x + 150 * s, b2.y + 600 * s);   // inside the window (the board's left edge can be off screen)
  await page.mouse.down();
  await page.mouse.move(b2.x + 330 * s, b2.y + 680 * s, { steps: 6 });
  await expect(page.locator('.pin-dim')).toContainText(' x ');
  // a live reload mid-drag (canvas.json changed elsewhere) keeps the area being drawn
  sandbox.cli('status', sandbox.idea, 'T02-TrailDetail.html', 'approved');
  await page.waitForTimeout(1600);
  await expect(page.locator('.pin-dim')).toContainText(' x ');
  await page.mouse.up();
  await expect(page.locator('#pin-cmp')).toContainText('Area');
  await page.keyboard.press('Escape');
  await expect(page.locator('#pin-cmp')).toBeHidden();
  expect(pins(cj, 'T01-Home.html')).toHaveLength(1);
  expect(consoleErrors).toEqual([]);
});

test('Share links have no pins', async ({ page, sandbox }) => {
  sandbox.cli('comment', sandbox.idea, 'T01-Home.html', 'a pin', '--at', '10,10');
  const srv = await sandbox.serve([sandbox.alphaDesign, '--share', '--minutes', '5']);
  await openCanvas(page, srv.origin + '/trailmate/?t=' + srv.token);
  await expect(page.locator('#pin-btn')).toHaveCount(0);
  await expect(page.locator('.pin')).toHaveCount(0);
  await page.keyboard.press('c');
  await expect(page.locator('#pin-hint')).toBeHidden();
});
