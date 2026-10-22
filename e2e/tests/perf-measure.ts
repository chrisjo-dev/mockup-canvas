import { Page } from '@playwright/test';

/** Pans for `ms` with one synthetic mousemove per frame and measures the gaps between frames. */
export async function measurePan(page: Page, ms = 3000) {
  return page.evaluate(async (dur) => {
    const stage = document.getElementById('stage')!;
    const sx = 400, sy = 300;
    const pendingAtStart = document.querySelectorAll('.board iframe.pending').length;
    stage.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0, clientX: sx, clientY: sy }));
    const times: number[] = [];
    const t0 = performance.now();
    await new Promise<void>((resolve) => {
      function step(t: number) {
        times.push(t);
        const k = (t - t0) / dur;
        const x = sx + Math.sin(k * Math.PI * 2) * 300;
        const y = sy + Math.sin(k * Math.PI * 4) * 100;
        window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
        if (t - t0 < dur) requestAnimationFrame(step); else resolve();
      }
      requestAnimationFrame(step);
    });
    window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: sx, clientY: sy }));
    const raw = times.slice(1).map((t, i) => t - times[i]);
    const gaps = [...raw].sort((a, b) => a - b);
    const slow = raw.map((g, i) => [i, Math.round(g)]).filter(([, g]) => g > 50);
    const total = times[times.length - 1] - times[0];
    const r1 = (v: number) => Math.round(v * 10) / 10;
    return {
      fps: r1(((times.length - 1) / total) * 1000),
      worstMs: r1(gaps[gaps.length - 1]),
      p95Ms: r1(gaps[Math.floor(gaps.length * 0.95)]),
      over50: slow.length,
      slowFrames: slow.slice(0, 5),   // [frame index, ms]: index 0 is the first frame of the pan
      live: document.querySelectorAll('.board iframe').length,
      pendingAtStart,
      thumbs: document.querySelectorAll('.board img.thumb').length,
    };
  }, ms);
}

/** Zooms to exactly `target` around the viewport centre with one synthetic wheel event. */
export async function zoomTo(page: Page, target: number) {
  await page.evaluate((t) => {
    const m = (document.getElementById('canvas') as HTMLElement).style.transform.match(/scale\(([-\d.e]+)\)/);
    const s = m ? +m[1] : 1;
    const stage = document.getElementById('stage')!;
    // The viewer zooms by exp(-deltaY * 0.002) per wheel event
    stage.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaMode: 0,
      deltaY: -Math.log(t / s) / 0.002, clientX: innerWidth / 2, clientY: innerHeight / 2 }));
  }, target);
}
