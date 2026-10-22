// Helpers for 09-ux-feel.spec.ts: an in-page recorder (installed before the viewer runs) and
// image metrics. Measurement only; nothing here changes the viewer.
import { execFileSync } from 'node:child_process';
import { decodePng } from './png';

/** Runs in the page before any viewer script (page.addInitScript). Exposes window.__ux. */
export function uxInit() {
  const W: any = window;
  if (W.__ux) return;
  const S: any = (W.__ux = {
    lastInput: 0, down: false, ifr: [] as any[], thumbs: {} as Record<string, number>, thumbEvents: [] as any[],
    writes: [] as any[], inputs: [] as any[], watchStyle: false, recInputs: false, trackIfr: true,
  });
  const recOf = new WeakMap<Element, any>();
  const mark = (e: Event) => {
    if (e.type === 'mousedown') S.down = true;
    if (e.type === 'mousemove' && !S.down) return;
    S.lastInput = performance.now();
    if (S.recInputs) S.inputs.push({ type: e.type, ts: e.timeStamp, now: performance.now() });
    if (e.type === 'mouseup') S.down = false;
  };
  for (const t of ['wheel', 'mousedown', 'mousemove', 'mouseup']) addEventListener(t, mark, true);

  const fileOf = (n: Element) => (n.closest('.board') as HTMLElement | null)?.dataset.file
    || (n.parentElement as HTMLElement | null)?.dataset?.file || '';
  const mo = new MutationObserver((muts) => {
    const now = performance.now();
    for (const m of muts) {
      if (m.type === 'childList') {
        m.addedNodes.forEach((n: any) => {
          if (n.tagName === 'IFRAME' && S.trackIfr) {
            const rec = { file: fileOf(n), src: n.getAttribute('src'), created: now, loaded: 0, revealed: 0, removed: 0 };
            S.ifr.push(rec); recOf.set(n, rec);
            n.addEventListener('load', () => { if (!rec.loaded) rec.loaded = performance.now(); });
          } else if (n.tagName === 'IMG' && n.classList && n.classList.contains('thumb')) {
            const file = fileOf(n);
            if (!S.thumbs[file]) S.thumbs[file] = now;
            S.thumbEvents.push({ file, t: now, src: n.getAttribute('src') });
          }
        });
        m.removedNodes.forEach((n: any) => {
          if (n.tagName === 'IFRAME') { const r = recOf.get(n); if (r && !r.removed) r.removed = now; }
        });
      } else if (m.type === 'attributes') {
        const t = m.target as HTMLElement;
        if (t.tagName === 'IFRAME' && m.attributeName === 'class' && !t.classList.contains('pending')) {
          const r = recOf.get(t); if (r && !r.revealed) r.revealed = now;
        } else if (m.attributeName === 'style' && S.watchStyle && (t.id === 'canvas' || t.classList.contains('board'))) {
          S.writes.push({ id: t.id || t.dataset.file, now, v: t.style.transform });
        }
      }
    }
  });
  mo.observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style'] });

  const raf = () => new Promise<number>((r) => requestAnimationFrame(r));
  S.raf = raf;
  S.recOf = (el: Element) => recOf.get(el);
  S.scale = () => {
    const m = (document.getElementById('canvas') as HTMLElement).style.transform.match(/scale\(([-\d.e]+)\)/);
    return m ? +m[1] : 1;
  };
  /** Boards that cover at least 20x20 px of the viewport above the toolbar, with what they show. */
  S.vis = () => {
    const H = innerHeight - 70, out: any[] = [];
    document.querySelectorAll('.board').forEach((d: any) => {
      if (d.classList.contains('collapsed')) return;
      const r = d.getBoundingClientRect();
      const w = Math.min(r.right, innerWidth) - Math.max(r.left, 0), h = Math.min(r.bottom, H) - Math.max(r.top, 0);
      if (w < 20 || h < 20) return;
      const f = d.querySelector('iframe:not(.pending)');
      const img = d.querySelector('img.thumb');
      out.push({ file: d.dataset.file, state: f ? 'live' : img ? 'thumb' : 'card', x: r.left, y: r.top, w: r.width, h: r.height,
        revealed: f ? (recOf.get(f)?.revealed || 0) : 0 });
    });
    return out;
  };
  S.counts = () => ({
    iframes: document.querySelectorAll('.board iframe').length,
    revealed: document.querySelectorAll('.board iframe:not(.pending)').length,
    thumbs: document.querySelectorAll('.board img.thumb').length,
  });
  /** Resolves once every visible board shows a revealed iframe; times are from the last input. */
  S.waitSharp = (timeout = 20000) => new Promise((res) => {
    const t0 = S.lastInput, start = performance.now();
    const step = () => {
      const v = S.vis();
      const all = v.length > 0 && v.every((b: any) => b.state === 'live');
      if (all || performance.now() - start > timeout) {
        const doneAt = Math.max(t0, ...v.map((b: any) => b.revealed || t0));
        const mounted = S.ifr.filter((r: any) => r.created >= t0);
        const visFiles = new Set(v.map((b: any) => b.file));
        const visRecs = mounted.filter((r: any) => visFiles.has(r.file));
        const med = (a: number[]) => { const s = a.filter((x) => x > 0).sort((p, q) => p - q); return s.length ? Math.round(s[Math.floor(s.length / 2)]) : null; };
        const mx = (a: number[]) => { const s = a.filter((x) => x > 0); return s.length ? Math.round(Math.max(...s)) : null; };
        res({
          ok: all, ms: all ? Math.round(doneAt - t0) : -1, checkedMs: Math.round(performance.now() - t0), visible: v.length,
          notLive: all ? [] : v.filter((b: any) => b.state !== 'live').map((b: any) => b.file + ':' + b.state),
          mountedTotal: mounted.length, mountedVisible: visRecs.length,
          createdMed: med(visRecs.map((r: any) => r.created - t0)), loadedMed: med(visRecs.map((r: any) => r.loaded - t0)),
          loadedMax: mx(visRecs.map((r: any) => r.loaded - t0)), revealedMax: mx(visRecs.map((r: any) => r.revealed - t0)),
          zoom: Math.round(S.scale() * 1000) / 1000,
        });
        return;
      }
      requestAnimationFrame(step);
    };
    step();
  });
  /** Zooms to `target` around (cx, cy) with `steps` wheel events, one per frame. */
  S.zoom = async (target: number, cx = innerWidth / 2, cy = (innerHeight - 70) / 2, steps = 8) => {
    const stage = document.getElementById('stage')!;
    for (let i = 0; i < steps; i++) {
      const s = S.scale();
      const dy = -Math.log(target / s) / 0.002 / (steps - i);
      stage.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaMode: 0, deltaY: dy, clientX: cx, clientY: cy }));
      await raf();
    }
  };
  /** Drags the stage by (dx, dy) over `frames` frames (the stage is the event target, as on an empty spot). */
  S.pan = async (dx: number, dy: number, frames = 12, sx = innerWidth / 2, sy = innerHeight / 2) => {
    const stage = document.getElementById('stage')!;
    stage.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0, buttons: 1, clientX: sx, clientY: sy }));
    for (let i = 1; i <= frames; i++) {
      await raf();
      dispatchEvent(new MouseEvent('mousemove', { bubbles: true, buttons: 1, clientX: sx + dx * i / frames, clientY: sy + dy * i / frames }));
    }
    await raf();
    dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: sx + dx, clientY: sy + dy }));
  };
  S.boardEl = (file: string) => document.querySelector(`.board[data-file="${CSS.escape(file)}"]`) as HTMLElement;
  /** Zooms toward a board and pans it to the middle of the view, as one continuous gesture. */
  S.goto = async (file: string, zoom: number, steps = 8) => {
    const d = S.boardEl(file);
    let r = d.getBoundingClientRect();
    const cl = (v: number, a: number, b: number) => Math.min(Math.max(v, a), b);
    await S.zoom(zoom, cl(r.left + r.width / 2, 5, innerWidth - 5), cl(r.top + r.height / 2, 5, innerHeight - 75), steps);
    r = d.getBoundingClientRect();
    const ty = (innerHeight - 70) / 2;
    const by = r.height > innerHeight - 100 ? r.top + (innerHeight - 100) / 2 : r.top + r.height / 2;
    await S.pan(innerWidth / 2 - (r.left + r.width / 2), ty - by, 12);
  };
  /** Records frame gaps until stopFrames(). */
  S.startFrames = () => {
    S.frameTimes = []; S.framesOn = true;
    const step = (t: number) => { if (!S.framesOn) return; S.frameTimes.push(t); requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };
  S.stopFrames = () => {
    S.framesOn = false;
    const t = S.frameTimes as number[], g = t.slice(1).map((x, i) => x - t[i]);
    const s = [...g].sort((a, b) => a - b);
    return { frames: t.length, worst: Math.round(s[s.length - 1] || 0), p95: Math.round(s[Math.floor(s.length * 0.95)] || 0),
      over50: g.filter((x) => x > 50).length, gaps50: g.map((x, i) => [i, Math.round(x)]).filter(([, x]) => x > 50).slice(0, 8) };
  };
}

/** Grayscale sharpness of a PNG (screenshot crop): Laplacian variance and mean gradient magnitude. */
export function sharpness(buf: Buffer) {
  const { w, h, ch, px } = decodePng(buf);
  const g = new Float64Array(w * h);
  for (let i = 0; i < w * h; i++) g[i] = 0.299 * px[i * ch] + 0.587 * px[i * ch + 1] + 0.114 * px[i * ch + 2];
  let n = 0, sum = 0, sum2 = 0, grad = 0;
  for (let y = 2; y < h - 2; y++) for (let x = 2; x < w - 2; x++) {
    const i = y * w + x;
    const lap = g[i - 1] + g[i + 1] + g[i - w] + g[i + w] - 4 * g[i];
    sum += lap; sum2 += lap * lap; n++;
    grad += Math.hypot(g[i + 1] - g[i - 1], g[i + w] - g[i - w]) / 2;
  }
  const mean = sum / n;
  return { w, h, lapVar: Math.round(sum2 / n - mean * mean), grad: Math.round((grad / n) * 100) / 100 };
}

/** Fraction of pixels within `tol` of an RGB color. */
export function colorFraction(buf: Buffer, rgb: [number, number, number], tol = 60) {
  const { w, h, ch, px } = decodePng(buf);
  let hit = 0;
  for (let i = 0; i < w * h; i++) {
    const d = Math.abs(px[i * ch] - rgb[0]) + Math.abs(px[i * ch + 1] - rgb[1]) + Math.abs(px[i * ch + 2] - rgb[2]);
    if (d < tol) hit++;
  }
  return hit / (w * h);
}

/** Resident memory (MB) of the browser processes this worker started (python servers and their Chrome excluded). */
export function browserRssMb(): number {
  const out = execFileSync('ps', ['-axo', 'pid=,ppid=,rss=,comm='], { encoding: 'utf8' });
  const rows = out.trim().split('\n').map((l) => {
    const m = l.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/);
    return m ? { pid: +m[1], ppid: +m[2], rss: +m[3], comm: m[4] } : null;
  }).filter(Boolean) as { pid: number; ppid: number; rss: number; comm: string }[];
  const kids = new Map<number, typeof rows>();
  for (const r of rows) { if (!kids.has(r.ppid)) kids.set(r.ppid, []); kids.get(r.ppid)!.push(r); }
  let total = 0;
  const walk = (pid: number) => {
    for (const c of kids.get(pid) || []) {
      if (/python/i.test(c.comm)) continue;   // canvas.py and its thumbnail Chrome
      total += c.rss; walk(c.pid);
    }
  };
  walk(process.pid);
  return Math.round(total / 1024);
}
