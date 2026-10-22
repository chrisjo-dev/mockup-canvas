// spec: specs/mockup-canvas-journeys.md (7. Large canvas: does virtualization feel slow or stale?)
// Measures what a user would notice from the level-of-detail optimizations: time until boards are
// sharp after a gesture, thumbnail blur, stale content after edits, cold first open, nudge pans,
// input latency, and memory over a long session. Opt-in and measurement first: most tests record
// numbers (metrics.jsonl with MC_E2E_SHOTS) and assert only loose limits.
//
//   MC_E2E_UX=1 MC_E2E_LARGE_IDEA=/path/to/design/<idea> MC_E2E_SHOTS=/tmp/ux \
//   MC_UX_TEMPLATE=/tmp/ux-template MC_UX_VP=1440x900 npx playwright test tests/09-ux-feel.spec.ts --workers=1
//
// MC_UX_TEMPLATE holds a copy of the large idea with every thumbnail rendered (the warm cache). The
// first test creates it when it is missing. Cold runs use the same copy without render/.thumbs.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { Page, BrowserContext } from '@playwright/test';
import { test, expect, openCanvas, record, Sandbox, Server } from './fixtures';
import { uxInit, sharpness, colorFraction, browserRssMb } from './ux-helpers';

const LARGE = process.env.MC_E2E_LARGE_IDEA || '';
const TEMPLATE = process.env.MC_UX_TEMPLATE || '';
const [VW, VH] = (process.env.MC_UX_VP || '1440x900').split('x').map(Number);
const VP = `${VW}x${VH}`;
const IDEA = path.basename(LARGE);
const FIXED_MTIME = 1767225600;   // 2026-01-01: copies keep the thumbnail cache key (board mtime)

test.use({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2 });

function shotsDir(project: string) {
  const d = path.join(process.env.MC_E2E_SHOTS || path.join(process.cwd(), 'ux-shots'), project, VP);
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function templateIdea() { return path.join(TEMPLATE, IDEA); }

/** Copies the idea into the sandbox (warm: with the rendered thumbnails) and serves it. */
async function serveLarge(sandbox: Sandbox, warm: boolean): Promise<{ srv: Server; url: string; dir: string; files: string[]; boards: any }> {
  const design = path.join(sandbox.work, 'large', 'design');
  fs.mkdirSync(design, { recursive: true });
  const dir = path.join(design, IDEA);
  execFileSync('cp', ['-Rp', templateIdea(), dir]);
  if (!warm) fs.rmSync(path.join(dir, 'render', '.thumbs'), { recursive: true, force: true });
  const srv = await sandbox.serveRegistry([[design, 'large']]);
  const cj = JSON.parse(fs.readFileSync(path.join(dir, 'canvas.json'), 'utf8'));
  return { srv, url: `${srv.origin}/large/${encodeURIComponent(IDEA)}/`, dir, files: Object.keys(cj.boards), boards: cj.boards };
}

async function newPage(ctx: BrowserContext) {
  const p = await ctx.newPage();
  await p.addInitScript(uxInit);
  return p;
}

async function open(page: Page, url: string) {
  await openCanvas(page, url);
  await page.waitForTimeout(400);
}

/** Phone-sized boards spread over the canvas from top to bottom (scenario targets). */
function pickTargets(boards: any, n: number): string[] {
  const phones = Object.entries(boards).filter(([, b]: any) => b.w === 390).sort((a: any, b: any) => a[1].y - b[1].y || a[1].x - b[1].x);
  const out: string[] = [];
  for (let i = 0; i < n; i++) out.push(phones[Math.floor(((i + 0.5) / n) * phones.length)][0]);
  return out;
}

async function boardClip(page: Page, file: string) {
  const r = await page.evaluate((f) => { const e = (window as any).__ux.boardEl(f).getBoundingClientRect(); return { x: e.left, y: e.top, w: e.width, h: e.height }; }, file);
  const x = Math.max(0, r.x), y = Math.max(0, r.y);
  return { x, y, width: Math.max(1, Math.min(r.x + r.w, VW) - x), height: Math.max(1, Math.min(r.y + r.h, VH - 70) - y) };
}

const ux = (page: Page, fn: string, ...args: any[]) =>
  page.evaluate(({ fn, args }) => (window as any).__ux[fn](...args), { fn, args });

test.describe(`UX feel of the large canvas (${VP}, DPR 2)`, () => {
  test.skip(!process.env.MC_E2E_UX || !LARGE || !TEMPLATE, 'set MC_E2E_UX=1, MC_E2E_LARGE_IDEA, and MC_UX_TEMPLATE');
  test.setTimeout(400_000);

  test('0. warm template (every thumbnail rendered)', async ({ sandbox, browserName }) => {
    if (fs.existsSync(path.join(templateIdea(), 'render', '.thumbs'))) return;
    test.skip(browserName !== 'chromium', 'created by the chromium run');
    const design = path.join(sandbox.work, 'large', 'design');
    const dir = path.join(design, IDEA);
    fs.cpSync(LARGE, dir, { recursive: true, filter: (s) => !s.includes(`${path.sep}render`) });
    for (const sub of ['boards', 'shared']) {
      const d = path.join(dir, sub);
      if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) fs.utimesSync(path.join(d, f), FIXED_MTIME, FIXED_MTIME);
    }
    const srv = await sandbox.serveRegistry([[design, 'large']]);
    const files = Object.keys(JSON.parse(fs.readFileSync(path.join(dir, 'canvas.json'), 'utf8')).boards);
    const done = new Set<string>();
    const t0 = Date.now();
    while (done.size < files.length && Date.now() - t0 < 300_000) {
      for (const f of files) {
        if (done.has(f)) continue;
        const r = await fetch(`${srv.origin}/large/${IDEA}/thumbs/${encodeURIComponent(f.replace(/\.html$/, ''))}.png`);
        if (r.status === 200) done.add(f);
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    expect(done.size).toBe(files.length);
    fs.mkdirSync(TEMPLATE, { recursive: true });
    execFileSync('cp', ['-Rp', dir, templateIdea()]);
  });

  // ── 1. Time to sharp ──
  for (const mode of ['cold', 'warm'] as const) {
    test(`1. time to sharp after pan or zoom (${mode})`, async ({ browser, sandbox }, testInfo) => {
      const { url, boards } = await serveLarge(sandbox, mode === 'warm');
      const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2 });
      let page = await newPage(ctx);
      const [a, b, c, d] = pickTargets(boards, 4);
      const scenarios: Array<[string, (p: Page) => Promise<void>]> = [
        ['fit -> zoom 60%', async (p) => { await ux(p, 'goto', a, 0.6); }],
        ['pan at 60%', async (p) => { await ux(p, 'goto', b, 0.6, 1); }],
        ['fit -> zoom 100%', async (p) => { await p.keyboard.press('f'); await p.waitForTimeout(1200); await ux(p, 'goto', c, 1.0); }],
        ['pan at 100%', async (p) => { await ux(p, 'goto', d, 1.0, 1); }],
      ];
      await open(page, url);
      if (mode === 'warm') {
        // Warm: every board has a thumbnail and the browser has loaded these boards before
        for (const [, run] of scenarios) { await run(page); await ux(page, 'waitSharp'); }
        await page.close();
        page = await newPage(ctx);
        await open(page, url);
      }
      const results: any[] = [];
      for (const [name, run] of scenarios) {
        await run(page);
        const r = await ux(page, 'waitSharp', 20_000);
        results.push({ name, ...r });
        record(testInfo, `sharp-${mode}-${VP}`, { name, ...r });
        await page.screenshot({ path: path.join(shotsDir(testInfo.project.name), `1-${mode}-${name.replace(/[^a-z0-9]+/gi, '_')}.png`) });
        await page.waitForTimeout(800);
      }
      // A mid-gesture frame: what the user sees 150 ms after a zoom to 60% stops
      await page.keyboard.press('f'); await page.waitForTimeout(1200);
      await ux(page, 'goto', a, 0.6);
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(shotsDir(testInfo.project.name), `1-${mode}-zoom60-at-150ms.png`) });
      await ctx.close();
      if (mode === 'warm') for (const r of results) expect.soft(r.ms, r.name).toBeLessThanOrEqual(600);
    });
  }

  // Small idea (6 boards) for comparison
  test('1b. time to sharp, small idea (trailmate)', async ({ page, sandbox }, testInfo) => {
    await page.addInitScript(uxInit);
    const srv = await sandbox.serve([sandbox.alphaDesign]);
    await open(page, `${srv.origin}/trailmate/`);
    // Boards show content: thumbnails, or live boards when the fit zoom is above the live threshold (2x screens)
    await expect.poll(() => page.locator('.board img.thumb, .board iframe:not(.pending)').count(), { timeout: 60_000 }).toBeGreaterThan(0);
    const files = await page.locator('.board').evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.file!));
    for (const mode of ['first', 'second']) {
      await page.keyboard.press('f'); await page.waitForTimeout(1200);
      await ux(page, 'goto', files[1], 0.6);
      const r = await ux(page, 'waitSharp', 20_000);
      record(testInfo, `sharp-small-${VP}`, { mode, ...r });
      if (mode === 'first') { await page.reload(); await openCanvas(page, page.url()); await page.waitForTimeout(400); }
    }
  });

  // ── 2. Thumbnail quality between the thumbnail and live zooms ──
  test('2. thumbnail sharpness vs live at 25, 30, 35%', async ({ page, sandbox }, testInfo) => {
    await page.addInitScript(uxInit);
    const { url, boards } = await serveLarge(sandbox, true);
    await open(page, url);
    const target = pickTargets(boards, 3)[1];
    const b = boards[target];
    const dir = shotsDir(testInfo.project.name);
    const out: any[] = [];
    for (const z of [0.25, 0.302, 0.35]) {
      // Thumbnail: arrive from the fitted zoom (below the live threshold)
      await page.keyboard.press('f'); await page.waitForTimeout(1200);
      await ux(page, 'goto', target, z);
      await page.waitForTimeout(1500);
      const st = await page.evaluate((f) => (window as any).__ux.vis().find((v: any) => v.file === f)?.state, target);
      const clip = await boardClip(page, target);
      const thumb = await page.screenshot({ clip });
      fs.writeFileSync(path.join(dir, `2-z${Math.round(z * 100)}-thumb.png`), thumb);
      // Live in the viewer: zoom in until live, then back (the band 30 to 40% keeps a live board live)
      let liveInViewer: Buffer | null = null;
      if (z >= 0.30) {
        await ux(page, 'goto', target, 0.6); await ux(page, 'waitSharp');
        await ux(page, 'zoom', z); await page.waitForTimeout(1500);
        const st2 = await page.evaluate((f) => (window as any).__ux.vis().find((v: any) => v.file === f)?.state, target);
        if (st2 === 'live') {
          liveInViewer = await page.screenshot({ clip: await boardClip(page, target) });
          fs.writeFileSync(path.join(dir, `2-z${Math.round(z * 100)}-live-viewer.png`), liveInViewer);
        }
      }
      // Reference: the same board in a test-only iframe scaled by z (what a live board would paint)
      await page.evaluate(({ f, w, h, z }) => {
        const base = location.pathname.replace(/\/$/, '');
        const ov = document.createElement('div');
        ov.id = 'ux-ref';
        ov.style.cssText = `position:fixed;left:40px;top:40px;width:${w * z}px;height:${h * z}px;overflow:hidden;z-index:99999;background:#fff`;
        const fr = document.createElement('iframe');
        fr.src = base + '/boards/' + encodeURIComponent(f);
        fr.width = String(w); fr.height = String(h);
        fr.setAttribute('sandbox', 'allow-scripts allow-forms allow-popups');
        fr.setAttribute('scrolling', 'no');
        fr.style.cssText = `border:0;display:block;transform-origin:0 0;transform:scale(${z})`;
        ov.appendChild(fr);
        document.body.appendChild(ov);
        return new Promise((r) => fr.addEventListener('load', r));
      }, { f: target, w: b.w, h: b.h, z: await page.evaluate(() => (window as any).__ux.scale()) });
      await page.waitForTimeout(1200);
      const refBox = await page.locator('#ux-ref').boundingBox();
      const ref = await page.screenshot({ clip: { x: refBox!.x, y: refBox!.y, width: refBox!.width, height: refBox!.height } });
      fs.writeFileSync(path.join(dir, `2-z${Math.round(z * 100)}-live-ref.png`), ref);
      await page.evaluate(() => document.getElementById('ux-ref')!.remove());
      const sT = sharpness(thumb), sR = sharpness(ref), sL = liveInViewer ? sharpness(liveInViewer) : null;
      const row = { zoom: z, shownAs: st, thumb: sT, liveRef: sR, liveViewer: sL,
        lapRatio: Math.round((sT.lapVar / sR.lapVar) * 100) / 100, gradRatio: Math.round((sT.grad / sR.grad) * 100) / 100 };
      out.push(row);
      record(testInfo, `thumb-sharpness-${VP}`, row);
    }
  });

  // ── 3. Freshness after edits ──
  test('3. freshness: edit visible, offscreen (live and evicted), zoom out after edit, edit at low zoom', async ({ page, sandbox }, testInfo) => {
    test.setTimeout(400_000);
    await page.addInitScript(uxInit);
    const { url, boards, dir: ideaDir } = await serveLarge(sandbox, true);
    await open(page, url);
    const [far1, e, far2] = pickTargets(boards, 3);
    const file = path.join(ideaDir, 'boards', e);
    const original = fs.readFileSync(file, 'utf8');
    const shots = shotsDir(testInfo.project.name);
    const edit = (rgb: [number, number, number]) => {
      const banner = `<div style="position:fixed;left:0;top:0;right:0;height:220px;background:rgb(${rgb.join(',')});z-index:2147483647"></div>`;
      fs.writeFileSync(file, original.replace(/<\/body>/i, banner + '</body>'));
      return Date.now();
    };
    /** Samples the board until the color covers part of it; returns timings and what was shown before. */
    async function until(rgb: [number, number, number], from: number, label: string, timeout = 30_000) {
      const seq: string[] = [];
      let n = 0;
      while (Date.now() - from < timeout) {
        const clip = await boardClip(page, e);
        const png = await page.screenshot({ clip });
        const frac = colorFraction(png, rgb);
        const st = await page.evaluate((f) => (window as any).__ux.vis().find((v: any) => v.file === f)?.state || 'offscreen', e);
        const tag = `${Date.now() - from}ms:${frac > 0.08 ? 'NEW' : 'old'}/${st}`;
        if (seq[seq.length - 1]?.split(':')[1] !== tag.split(':')[1]) seq.push(tag);
        if (n++ === 1) fs.writeFileSync(path.join(shots, `3-${label}-early.png`), png);
        if (frac > 0.08) {
          fs.writeFileSync(path.join(shots, `3-${label}-new.png`), png);
          // Exact times from the DOM (screenshots are slow while boards load)
          const dom = await page.evaluate((f) => {
            const S = (window as any).__ux, d = S.boardEl(f);
            const fr = d.querySelector('iframe:not(.pending)'), rec = fr && S.recOf(fr);
            const th = S.thumbEvents.filter((x: any) => x.file === f).pop();
            return { iframeShown: rec && rec.revealed ? performance.timeOrigin + rec.revealed : 0,
              thumbShown: th ? performance.timeOrigin + th.t : 0, shows: fr ? 'live' : 'thumb' };
          }, e);
          const at = dom.shows === 'live' ? dom.iframeShown : dom.thumbShown;
          return { ms: Date.now() - from, domMs: at ? Math.round(at - from) : null, seq };
        }
      }
      return { ms: -1, seq };
    }
    const liveState = () => page.evaluate((f) => { const d = (window as any).__ux.boardEl(f); return { iframe: !!d.querySelector('iframe'), img: !!d.querySelector('img.thumb') }; }, e);

    // a. visible live board
    await ux(page, 'goto', e, 0.6); await ux(page, 'waitSharp');
    let t = edit([255, 0, 255]);
    const a = await until([255, 0, 255], t, 'a-visible');
    record(testInfo, `fresh-visible-${VP}`, a);

    // b. off screen but still live (recently seen)
    await ux(page, 'pan', 0, -(VH + 200), 10); await page.waitForTimeout(1200);
    const bState = await liveState();
    t = edit([0, 200, 255]);
    await page.waitForTimeout(2500);
    await ux(page, 'goto', e, 0.6, 1);
    const tb = Date.now();
    const bRes = await until([0, 200, 255], tb, 'b-offscreen-live');
    record(testInfo, `fresh-offscreen-live-${VP}`, { stateWhenEdited: bState, msAfterPanBack: bRes.ms, seq: bRes.seq });

    // c. off screen and evicted (other regions loaded since)
    for (const f of [far1, far2, far1]) { await ux(page, 'goto', f, 0.6); await ux(page, 'waitSharp'); await page.waitForTimeout(500); }
    const cState = await liveState();
    t = edit([0, 220, 0]);
    await page.waitForTimeout(2500);
    await ux(page, 'goto', e, 0.6);
    const tc = Date.now();
    const cRes = await until([0, 220, 0], tc, 'c-offscreen-evicted');
    record(testInfo, `fresh-offscreen-evicted-${VP}`, { stateWhenEdited: cState, msAfterPanBack: cRes.ms, seq: cRes.seq });

    // d. zoom out right after an edit shows up live
    await ux(page, 'waitSharp');
    t = edit([255, 230, 0]);
    const dLive = await until([255, 230, 0], t, 'd-live');
    await ux(page, 'zoom', 0.2);
    const td = Date.now();
    const dRes = await until([255, 230, 0], td, 'd-zoomed-out');
    record(testInfo, `fresh-zoomout-after-edit-${VP}`, { editToLiveMs: dLive.ms, msAfterZoomOut: dRes.ms, seq: dRes.seq });

    // e. edit while zoomed out (thumbnail shown)
    await page.waitForTimeout(3000);
    t = edit([255, 120, 0]);
    const eRes = await until([255, 120, 0], t, 'e-edit-at-20pct', 60_000);
    record(testInfo, `fresh-edit-at-low-zoom-${VP}`, eRes);
    fs.writeFileSync(file, original);
  });

  // ── 4. Cold first open ──
  test('4. cold first open: title cards until thumbnails, and is the visible area first', async ({ browser, sandbox }, testInfo) => {
    const shots = shotsDir(testInfo.project.name);
    // a. fit view
    {
      const { url, files } = await serveLarge(sandbox, false);
      const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2 });
      const page = await newPage(ctx);
      await page.goto(url);
      const t0 = Date.now();
      for (const at of [2000, 8000]) {
        await page.waitForTimeout(at - (Date.now() - t0));
        await page.screenshot({ path: path.join(shots, `4-cold-fit-${at / 1000}s.png`) });
      }
      await expect.poll(() => page.evaluate(() => Object.keys((window as any).__ux.thumbs).length), { timeout: 240_000, intervals: [1000] }).toBe(files.length);
      await page.screenshot({ path: path.join(shots, `4-cold-fit-all.png`) });
      const times = Object.values(await page.evaluate(() => (window as any).__ux.thumbs) as Record<string, number>).sort((p, q) => p - q);
      const q = (f: number) => Math.round(times[Math.min(times.length - 1, Math.floor(f * times.length))]);
      const visibleAtFit = (await ux(page, 'vis')).length;
      record(testInfo, `cold-fit-${VP}`, { boards: files.length, visibleAtFit, firstMs: q(0), p50Ms: q(0.5), p90Ms: q(0.9), lastMs: q(1) });
      await ctx.close();
    }
    // b. open, then zoom to 25% on the boards the queue renders last (the first in canvas.json)
    {
      const sb2 = new Sandbox('ux-cold-b');
      try {
        const { url, files, dir } = await serveLarge(sb2, false);
        // Server render order: when each board's PNG appears in render/.thumbs
        const rendered = new Map<string, number>();
        const fileSet = new Set(files);
        const thumbsDir = path.join(dir, 'render', '.thumbs');
        const pollFs = () => {
          if (!fs.existsSync(thumbsDir)) return;
          for (const n of fs.readdirSync(thumbsDir)) {
            const f = n.replace(/-\d+x\d+-[0-9a-f-]+\.png$/, '.html');
            if (fileSet.has(f) && !rendered.has(f)) rendered.set(f, Date.now());
          }
        };
        const timer = setInterval(pollFs, 200);
        const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2 });
        const page = await newPage(ctx);
        await openCanvas(page, url);
        await page.waitForTimeout(1000);
        await ux(page, 'goto', files[0], 0.25);
        const tzWall = Date.now();
        const tz = await page.evaluate(() => (window as any).__ux.lastInput);
        await page.waitForTimeout(1500);
        const visible = (await ux(page, 'vis')).map((v: any) => v.file) as string[];
        await page.screenshot({ path: path.join(shots, `4-cold-zoom25-after-1.5s.png`) });
        const visThumbs = () => page.evaluate((vf) => { const t = (window as any).__ux.thumbs; return vf.filter((f: string) => t[f]).length; }, visible);
        await expect.poll(visThumbs, { timeout: 240_000, intervals: [500] }).toBe(visible.length);
        const th = await page.evaluate(() => (window as any).__ux.thumbs) as Record<string, number>;
        const visTimes = visible.map((f) => Math.round(th[f] - tz)).sort((p, q) => p - q);
        await page.screenshot({ path: path.join(shots, `4-cold-zoom25-visible-done.png`) });
        await expect.poll(() => { pollFs(); return rendered.size; }, { timeout: 240_000, intervals: [1000] }).toBe(files.length);
        clearInterval(timer);
        const order = [...rendered.entries()].sort((p, q) => p[1] - q[1]).map(([f]) => f);
        const ranks = visible.map((f) => order.indexOf(f) + 1).sort((p, q) => p - q);
        record(testInfo, `cold-zoom25-priority-${VP}`, { visible: visible.length, serverRenderRanksOfVisible: ranks,
          visibleShownMsAfterZoom: visTimes, allRenderedMsAfterZoom: rendered.get(order[order.length - 1])! - tzWall });
        await ctx.close();
      } finally { await sb2.dispose(false); }
    }
  });

  // ── 5. Nudge pans ──
  for (const [mode, gapMode] of [['warm', 'start-to-start'], ['warm', 'rest'], ['cold', 'start-to-start']] as const) {
    test(`5. ten nudge pans 400 ms apart at 60% (${mode}, ${gapMode})`, async ({ browser, sandbox }, testInfo) => {
      const { url, boards } = await serveLarge(sandbox, mode === 'warm');
      const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2 });
      const page = await newPage(ctx);
      await open(page, url);
      await page.waitForTimeout(1500);
      await ux(page, 'goto', pickTargets(boards, 3)[1], 0.6);
      const rows: string[] = [];
      for (let i = 0; i < 10; i++) {
        const t = Date.now();
        await ux(page, 'pan', i % 2 ? 40 : -40, 15, 6);
        if (gapMode === 'rest') await page.waitForTimeout(400);
        else await page.waitForTimeout(Math.max(0, 400 - (Date.now() - t)));
        const v = await ux(page, 'vis');
        const c = await ux(page, 'counts');
        rows.push(`${i + 1}: ${v.filter((b: any) => b.state === 'live').length}/${v.length} live (iframes ${c.iframes}, loading ${c.iframes - c.revealed})`);
      }
      const final = await ux(page, 'waitSharp', 20_000);
      record(testInfo, `nudge-${mode}-${gapMode}-${VP}`, { rows, finalSharpMs: final.ms, final });
      await ctx.close();
    });
  }

  // ── 6. Input latency ──
  test('6. input latency: title bar drag, wheel, pan while boards mount', async ({ page, sandbox, browserName }, testInfo) => {
    await page.addInitScript(uxInit);
    const { url, boards } = await serveLarge(sandbox, true);
    await open(page, url);
    const [t1, t2] = pickTargets(boards, 2);
    await ux(page, 'goto', t1, 0.6); await ux(page, 'waitSharp'); await page.waitForTimeout(800);
    const startRec = () => page.evaluate(() => { const S = (window as any).__ux; S.writes = []; S.inputs = []; S.watchStyle = true; S.recInputs = true; });
    const stopRec = () => page.evaluate(() => { const S = (window as any).__ux; S.watchStyle = false; S.recInputs = false; return { writes: S.writes, inputs: S.inputs }; });
    /** For each input, ms until the next transform write of `id` (the viewer writes once per frame). */
    const lat = ({ writes, inputs }: any, type: string, id: string) => {
      const out: number[] = [];
      for (const ev of inputs.filter((x: any) => x.type === type)) {
        const w = writes.find((x: any) => x.id === id && x.now >= ev.now);
        if (w) out.push(w.now - ev.ts);
      }
      const s = out.sort((p, q) => p - q);
      return { n: s.length, med: Math.round(s[Math.floor(s.length / 2)] || 0), max: Math.round(s[s.length - 1] || 0), over50: s.filter((x) => x > 50).length };
    };
    // a. drag a title bar
    const barBox = await page.locator(`.board[data-file="${t1}"] .board-bar`).boundingBox();
    await startRec();
    await page.mouse.move(barBox!.x + barBox!.width / 2, barBox!.y + barBox!.height / 2);
    await page.mouse.down();
    for (let i = 1; i <= 15; i++) { await page.mouse.move(barBox!.x + barBox!.width / 2 + i * 6, barBox!.y + barBox!.height / 2 + i * 3); await page.waitForTimeout(16); }
    const drag = await stopRec();
    await page.mouse.up();
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+z' : 'Control+z');
    const dragLat = lat(drag, 'mousemove', t1);
    // b. wheel over the boards
    await page.waitForTimeout(1000);
    await startRec();
    await page.mouse.move(VW / 2, VH / 2);
    for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, i < 4 ? -40 : 40); await page.waitForTimeout(30); }
    const wheel = await stopRec();
    const wheelLat = lat(wheel, 'wheel', 'canvas');
    // c. start a pan just as the boards of a new region mount (idle ~300 ms after a zoom)
    await page.keyboard.press('f'); await page.waitForTimeout(1500);
    await ux(page, 'goto', t2, 0.6);
    await page.waitForTimeout(330);
    await page.evaluate(() => (window as any).__ux.startFrames());
    await startRec();
    await ux(page, 'pan', -200, -80, 20);
    const pan = await stopRec();
    await page.waitForTimeout(1500);
    const frames = await page.evaluate(() => (window as any).__ux.stopFrames());
    const panLat = lat(pan, 'mousemove', 'canvas');
    // Event Timing (Chromium, Firefox): slowest discrete events in the session
    const evt = await page.evaluate(() => new Promise((res) => {
      try {
        const po = new PerformanceObserver(() => {});
        po.observe({ type: 'event', buffered: true, durationThreshold: 16 } as any);
        const list = (po.takeRecords() as any[]).map((e) => ({ name: e.name, dur: Math.round(e.duration), proc: Math.round(e.processingEnd - e.processingStart), delay: Math.round(e.processingStart - e.startTime) }));
        po.disconnect();
        res(list.sort((a, b) => b.dur - a.dur).slice(0, 5));
      } catch (e) { res('unsupported'); }
    }));
    const row = { dragLat, wheelLat, panDuringMountLat: panLat, framesDuringMount: frames, eventTiming: evt };
    record(testInfo, `latency-${VP}`, row);
  });

  // ── 7. Memory ──
  test('7. memory after 2 minutes of mixed panning and zooming', async ({ page, sandbox, browserName }, testInfo) => {
    test.setTimeout(400_000);
    await page.addInitScript(uxInit);
    const { url, files } = await serveLarge(sandbox, true);
    await open(page, url);
    await page.evaluate(() => { (window as any).__ux.trackIfr = false; });
    const cdp = browserName === 'chromium' ? await page.context().newCDPSession(page) : null;
    if (cdp) await cdp.send('Performance.enable');
    const heap = async () => {
      if (!cdp) return null;
      const m = (await cdp.send('Performance.getMetrics')).metrics as { name: string; value: number }[];
      return Math.round((m.find((x) => x.name === 'JSHeapUsedSize')!.value / 1048576) * 10) / 10;
    };
    const samples: any[] = [];
    const sample = async (label: string) => {
      const c = await ux(page, 'counts');
      samples.push({ t: label, heapMb: await heap(), rssMb: browserRssMb(), ...c });
    };
    await sample('start');
    let seed = 12345;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    const t0 = Date.now();
    let next = 10_000, maxIframes = 0, liveSamples = 0;
    while (Date.now() - t0 < 120_000) {
      // Mixed gestures that stay on the canvas: jump to a random board at a random zoom, or a
      // short pan, or a zoom around a random point
      const k = rnd();
      if (k < 0.35) {
        const z = Math.exp(Math.log(0.08) + rnd() * (Math.log(1.2) - Math.log(0.08)));
        await ux(page, 'goto', files[Math.floor(rnd() * files.length)], z, 4 + Math.floor(rnd() * 6));
      } else if (k < 0.7) {
        await ux(page, 'pan', (rnd() - 0.5) * 1200, (rnd() - 0.5) * 900, 8 + Math.floor(rnd() * 16));
      } else {
        const z = Math.exp(Math.log(0.08) + rnd() * (Math.log(1.2) - Math.log(0.08)));
        await ux(page, 'zoom', z, 200 + rnd() * (VW - 400), 150 + rnd() * (VH - 350), 4 + Math.floor(rnd() * 6));
      }
      await page.waitForTimeout(Math.floor(rnd() * 1200));
      const cn = await ux(page, 'counts'); maxIframes = Math.max(maxIframes, cn.iframes); if (cn.iframes) liveSamples++;
      if (Date.now() - t0 >= next) { await sample(`${Math.round(next / 1000)}s`); next += 10_000; }
    }
    await page.waitForTimeout(5000);
    await sample('idle+5s');
    if (cdp) { await cdp.send('HeapProfiler.enable'); await cdp.send('HeapProfiler.collectGarbage'); await page.waitForTimeout(500); await sample('after GC'); }
    record(testInfo, `memory-${VP}`, { maxIframes, liveSamples, samples });
    expect(maxIframes).toBeLessThan(60);
  });
});
