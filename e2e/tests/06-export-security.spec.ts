// spec: specs/mockup-canvas-journeys.md
// seed: seed.spec.ts
import fs from 'node:fs';
import path from 'node:path';
import { test, expect, openCanvas, board, bar, settled, zoomInOn, shot } from './fixtures';

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
