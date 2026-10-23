// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, openCanvas, board, bar, settled, zoomInOn, shot, xform, Sandbox } from './fixtures';
import { decodePng } from './png';
import { blockFont } from './font';

test.describe('Export', () => {
  test('Static export renders boards and arrows, read-only', async ({ page, sandbox, consoleErrors }, testInfo) => {
    // 1. canvas export
    const out = path.join(sandbox.root, 'export-out');
    const log = sandbox.cli('export', sandbox.idea, out);
    expect(log).toContain('Check OK');
    expect(fs.existsSync(path.join(out, 'index.html'))).toBe(true);
    // 2. Serve it with a plain static server
    const srv = await sandbox.serveStatic(out);
    await openCanvas(page, srv.origin + '/');
    await settled(page);
    await expect(page.locator('.board')).toHaveCount(6);
    await expect(page.locator('#arrow-svg > path')).toHaveCount(4);
    await expect(page.locator('#ro-badge')).toBeVisible();
    // 3. Zoom in and check content
    await zoomInOn(page, 'T01-Home.html', 0.6);
    await expect(page.frameLocator('.board[data-file="T01-Home.html"] iframe').getByText('Pine Ridge Loop').first()).toBeVisible();
    await shot(page, testInfo, '09-export');
    // Drag does nothing
    const left = await board(page, 'T01-Home.html').evaluate((e) => (e as HTMLElement).style.left);
    const box = (await bar(page, 'T01-Home.html').boundingBox())!;
    await page.mouse.move(box.x + 20, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 220, box.y + 120, { steps: 8 });
    await page.mouse.up();
    expect(await board(page, 'T01-Home.html').evaluate((e) => (e as HTMLElement).style.left)).toBe(left);
    testInfo.annotations.push({ type: 'console', description: JSON.stringify(consoleErrors) });
    expect(consoleErrors).toEqual([]);
  });
});

test.describe('Security smoke', () => {
  test('A board script cannot call the registry API or reach the parent', async ({ page, sandbox }, testInfo) => {
    // 1. A board with a hostile script
    const file = path.join(sandbox.idea, 'boards', 'T01-Home.html');
    const addTarget = sandbox.makeBeta();
    const script = `<div id="qa-sec" style="position:fixed;top:0;left:0;right:0;background:#fee;font:20px monospace;z-index:9">pending</div>
<script>
(async function(){
  var out = [];
  async function hit(p, body){
    try {
      var r = await fetch(p, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      var t = await r.text();
      out.push(p + ' ' + r.status + ' ' + t.slice(0, 80));
    } catch (e) { out.push(p + ' blocked ' + e.name); }
  }
  await hit('/api/roots/scan', {dirs:['~']});
  await hit('/api/roots/add', {path: ${JSON.stringify(addTarget)}, name: 'pwned'});
  try { out.push('parent ' + parent.document.title); } catch (e) { out.push('parent blocked ' + e.name); }
  try { out.push('cookie ' + JSON.stringify(document.cookie)); } catch (e) { out.push('cookie blocked ' + e.name); }
  document.getElementById('qa-sec').textContent = 'DONE ' + out.join(' | ');
})();
</script>`;
    fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace('</body>', script + '</body>'));
    const srv = await sandbox.serveRegistry();
    // 2. Open the idea zoomed in on that board
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
    await zoomInOn(page, 'T01-Home.html', 0.6);
    const result = page.frameLocator('.board[data-file="T01-Home.html"] iframe').locator('#qa-sec');
    await expect(result).toHaveText(/^DONE /, { timeout: 15_000 });
    const text = (await result.textContent())!;
    testInfo.annotations.push({ type: 'board-script-result', description: text });
    await shot(page, testInfo, '10-sandbox');
    expect(text).not.toContain('"ok": true');
    expect(text).toMatch(/\/api\/roots\/scan (blocked|403)/);
    expect(text).toMatch(/\/api\/roots\/add (blocked|403)/);
    expect(text).toContain('parent blocked');
    expect(sandbox.rootsFile().map((r) => r.name)).toEqual(['alpha']);
  });

  test('Host header spoofing is rejected', async ({ playwright, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    const api = await playwright.request.newContext();
    // 1. Foreign Host
    const spoof = await api.get(srv.origin + '/', { headers: { Host: `evil.example:${srv.port}` } });
    expect(spoof.status()).toBe(421);
    const spoof2 = await api.get(srv.origin + '/alpha/trailmate/canvas.json', { headers: { Host: 'evil.example' } });
    expect(spoof2.status()).toBe(421);
    const local = await api.get(srv.origin + '/', { headers: { Host: `localhost:${srv.port}` } });
    expect(local.status()).toBe(200);
    // 2. Foreign Origin on a state-changing API
    const csrf = await api.post(srv.origin + '/api/roots/scan', {
      headers: { Origin: 'http://evil.example', 'Content-Type': 'application/json' }, data: { dirs: ['~'] } });
    expect(csrf.status()).toBe(403);
    const csrfLayout = await api.post(srv.origin + '/alpha/trailmate/api/layout', {
      headers: { Origin: 'http://evil.example', 'Content-Type': 'application/json' }, data: { board: 'T01-Home.html', x: 1, y: 1 } });
    expect(csrfLayout.status()).toBe(403);
    // A text/plain body (the CORS-simple type) is refused even from the right Origin
    const simple = await api.post(srv.origin + '/api/roots/scan', {
      headers: { Origin: srv.origin, 'Content-Type': 'text/plain' }, data: JSON.stringify({ dirs: ['~'] }) });
    expect(simple.status()).toBe(400);
    await api.dispose();
  });
});

// Every static file is sent with the sandbox CSP, and fonts get CORS only for Origin: null (a
// sandboxed board) and the server's own origins. A board's local font, SVG image, and SVG
// background must still load, live (sandboxed iframe, local and share mode) and in thumbnails.
function resourceBoard(sandbox: Sandbox) {
  fs.mkdirSync(path.join(sandbox.idea, 'assets'), { recursive: true });
  fs.writeFileSync(path.join(sandbox.idea, 'assets', 'qa-block.ttf'), blockFont());
  fs.writeFileSync(path.join(sandbox.idea, 'assets', 'qa.svg'),
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="#f00"/></svg>');
  fs.writeFileSync(path.join(sandbox.idea, 'boards', 'T01-Home.html'), `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=390">
<style>@font-face{font-family:QaBlock;src:url(../assets/qa-block.ttf) format('truetype')}
body{margin:0;background:#fff}
#f{position:absolute;left:0;top:0;font:120px/1 QaBlock,serif;color:#000;white-space:nowrap}
#s{position:absolute;left:0;top:200px;width:200px;height:100px}
#b{position:absolute;left:0;top:400px;width:200px;height:100px;background:url(../assets/qa.svg)}</style>
</head><body><div id="f">AAA</div><img id="s" src="../assets/qa.svg" alt=""><div id="b"></div></body></html>`);
}

/** Share of pixels in the rectangle that match `want` (dark or red). */
function share(png: Buffer, x0: number, y0: number, x1: number, y1: number, want: 'dark' | 'red', scale = 1) {
  const { w, ch, px } = decodePng(png);
  let hit = 0, n = 0;
  for (let y = Math.round(y0 * scale); y < Math.round(y1 * scale); y++) {
    for (let x = Math.round(x0 * scale); x < Math.round(x1 * scale); x++) {
      const i = (y * w + x) * ch, r = px[i], g = px[i + 1], b = px[i + 2];
      n++;
      if (want === 'dark' ? r + g + b < 120 : r > 200 && g < 60 && b < 60) hit++;
    }
  }
  return hit / n;
}

async function checkLive(page: Page) {
  await zoomInOn(page, 'T01-Home.html', 0.6);
  // Pan the whole board into view (an element screenshot is clipped to the viewport)
  const box = (await board(page, 'T01-Home.html').boundingBox())!;
  const p = (await page.evaluate(() => {
    for (let y = 30; y < innerHeight - 60; y += 10) {
      for (let x = 10; x < innerWidth - 10; x += 10) {
        const e = document.elementFromPoint(x, y);
        if (e && (e.id === 'stage' || e.id === 'canvas')) return { x, y };
      }
    }
    return null;
  }))!;
  await page.mouse.move(p.x, p.y);
  await page.mouse.down();
  await page.mouse.move(p.x + 40 - box.x, p.y + 40 - box.y, { steps: 6 });
  await page.mouse.up();
  await settled(page);
  const frame = page.frameLocator('.board[data-file="T01-Home.html"] iframe');
  await expect(frame.locator('#f')).toBeVisible();
  const state = await frame.locator('body').evaluate(async () => {
    await document.fonts.load('120px QaBlock');
    await document.fonts.ready;
    const img = document.getElementById('s') as HTMLImageElement;
    if (!img.complete) await new Promise((r) => { img.onload = img.onerror = r; });
    return { font: [...document.fonts].map((f) => f.family.replace(/"/g, '') + ':' + f.status),
             img: img.naturalWidth, origin: String(self.origin) };
  });
  expect(state.origin).toBe('null');   // still sandboxed
  expect(state.font).toContain('QaBlock:loaded');
  expect(state.img).toBe(200);
  const shotPng = await board(page, 'T01-Home.html').locator('iframe').screenshot();
  const s = (await xform(page)).s * await page.evaluate(() => devicePixelRatio);   // screenshot px per board px
  expect(share(shotPng, 10, 10, 350, 110, 'dark', s), 'font block').toBeGreaterThan(0.9);
  expect(share(shotPng, 10, 210, 190, 290, 'red', s), 'svg image').toBeGreaterThan(0.9);
  expect(share(shotPng, 10, 410, 190, 490, 'red', s), 'svg background').toBeGreaterThan(0.9);
}

async function checkThumb(page: Page, url: string) {
  let png: Buffer | null = null;
  for (let i = 0; i < 60 && !png; i++) {
    const r = await page.request.get(url);
    if (r.status() === 200) png = await r.body();
    else await page.waitForTimeout(500);
  }
  expect(png, 'thumbnail rendered').not.toBeNull();
  expect(share(png!, 10, 10, 350, 110, 'dark'), 'thumbnail font block').toBeGreaterThan(0.9);
  expect(share(png!, 10, 210, 190, 290, 'red'), 'thumbnail svg image').toBeGreaterThan(0.9);
  expect(share(png!, 10, 410, 190, 490, 'red'), 'thumbnail svg background').toBeGreaterThan(0.9);
}

test.describe('Board resources under the sandbox CSP', () => {
  test('Local fonts and SVG render live and in thumbnails', async ({ page, sandbox, consoleErrors }, testInfo) => {
    resourceBoard(sandbox);
    const srv = await sandbox.serveRegistry();
    const font = await page.request.get(srv.origin + '/alpha/trailmate/assets/qa-block.ttf', { headers: { Origin: 'https://evil.example' } });
    expect(font.headers()['access-control-allow-origin']).toBeUndefined();
    expect(font.headers()['content-security-policy']).toMatch(/^sandbox /);
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await settled(page);
    await checkLive(page);
    await shot(page, testInfo, '11-fonts-svg-live');
    await checkThumb(page, srv.origin + '/alpha/trailmate/thumbs/T01-Home.png?s=1');
    expect(consoleErrors).toEqual([]);
  });

  test('Local fonts and SVG render in share mode', async ({ page, sandbox, consoleErrors }) => {
    resourceBoard(sandbox);
    const srv = await sandbox.serve([sandbox.alphaDesign, '--share', '--minutes', '5']);
    await page.goto(`${srv.origin}/?t=${srv.token}`);
    await page.getByRole('link', { name: /trailmate/ }).click();
    await page.waitForURL(`${srv.origin}/trailmate/`);
    await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
    await settled(page);
    await checkLive(page);
    await expect(board(page, 'T01-Home.html').locator('iframe')).toHaveAttribute('src', /^\/_k\/[0-9a-f]+\/trailmate\//);
    await checkThumb(page, srv.origin + '/trailmate/thumbs/T01-Home.png?s=1');
    expect(consoleErrors).toEqual([]);
  });
});
