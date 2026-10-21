#!/usr/bin/env python3
"""Canvas viewer performance check (not part of the unit suite; needs Google Chrome).

Copies an idea folder into a temp design dir, serves it with `canvas.py serve` on a free port,
opens the viewer in headless Chrome over DevTools at 1440x900 (device pixel ratio 2 like a Mac
display; --dpr 1 for a plain one), and measures:

  fit        time from navigation start until the fit view is shown (loading screen gone)
  full       time until every board in the viewport shows its content (iframe or image loaded)
  pan-fit    3 s of continuous mouse pan at the fit zoom
  zoom       3 s of wheel zoom in and out around the viewport center (in-page wheel events, one per frame)
  pan-60     3 s of continuous pan at about 60% zoom (live boards)

Per interaction: average FPS of frames the compositor actually presented (trace events
Display::FrameDisplayed), p95 and max time between presented frames, dropped frames, long tasks
(count over 50 ms and the longest), plus requestAnimationFrame FPS and input-to-frame latency. Targets: FPS >= 55, p95 <= 25 ms,
no long task > 100 ms, fit <= 1.5 s.

Usage: python3 tests/perf_check.py [IDEA_DIR] [--json OUT] [--runs N] [--warm] [--canvas CANVAS_PY] [--dpr 2]
  IDEA_DIR defaults to examples/trailmate. --warm runs once untimed first (thumbnail cache).
  --canvas serves with another copy of canvas.py (and the viewer.html next to it), for before/after.
Everything runs in a temp dir (MOCKUP_CANVAS_HOME too); the server and Chrome are stopped at the end.
"""
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers import CANVAS_PY, REPO, canvas  # noqa: E402

W, H = 1440, 900
DPR = 2   # a Mac display; --dpr 1 for a plain one

INSTRUMENT = r'''
window.__perf = { longtasks: [], frames: [], collect: false, fit: null };
document.addEventListener('load', (e) => {
  const t = e.target;
  if (t && (t.tagName === 'IFRAME' || t.tagName === 'IMG')) t.__loaded = performance.now();
}, true);
try {
  new PerformanceObserver((l) => { for (const e of l.getEntries()) __perf.longtasks.push([e.startTime, e.duration]); })
    .observe({ type: 'longtask', buffered: true });
} catch (_) {}
document.addEventListener('DOMContentLoaded', () => {
  const ld = document.getElementById('loading');
  if (!ld) return;
  const done = () => { if (__perf.fit === null && ld.classList.contains('gone')) __perf.fit = performance.now(); };
  new MutationObserver(done).observe(ld, { attributes: true });
  done();
});
window.__visibleReady = () => {
  let ready = 0, total = 0;
  for (const b of document.querySelectorAll('.board')) {
    if (b.classList.contains('collapsed')) continue;
    const r = b.getBoundingClientRect();
    if (r.right < 0 || r.bottom < 0 || r.left > innerWidth || r.top > innerHeight) continue;
    total++;
    const el = b.querySelector('iframe, img');
    if (el && (el.__loaded || (el.tagName === 'IMG' && el.complete && el.naturalWidth > 0))) ready++;
  }
  return [ready, total];
};
window.__startFrames = () => {
  __perf.frames = []; __perf.collect = true; __perf.t0 = performance.now();
  const f = (t) => { __perf.frames.push(t); if (__perf.collect) requestAnimationFrame(f); };
  requestAnimationFrame(f);
};
window.__stopFrames = () => {
  __perf.collect = false;
  const t1 = performance.now();
  const lt = __perf.longtasks.filter(([s, d]) => s + d >= __perf.t0 && s <= t1).map(([, d]) => d);
  return { frames: __perf.frames, t0: __perf.t0, t1: t1, longtasks: lt };
};
window.__panPoint = () => {
  // A point where mousedown starts a pan (empty canvas or a group background)
  for (let y = 60; y < innerHeight - 80; y += 20) {
    for (let x = 20; x < innerWidth - 20; x += 20) {
      const el = document.elementFromPoint(x, y);
      if (el && (el.id === 'stage' || el.id === 'canvas' || el.closest('.grp-bg') || el.classList.contains('grp-bg'))) return [x, y];
    }
  }
  return null;
};
window.__wheelFor = (ms) => new Promise((done) => {
  // One synthetic wheel event per animation frame on the stage. Chrome aligns real continuous
  // input (wheel, mousemove, touchmove) to animation frames; DevTools input dispatch instead waits
  // for each event's ack and tops out near 30 events per second, which would cap the FPS.
  const stage = document.getElementById('stage');
  const n = window.__wheelSteps || 13;   // frames zooming in, then the same out (about 1.3x per step)
  let i = 0;
  const t0 = performance.now();
  const step = () => {
    const dy = (Math.floor(i / n) % 2 === 0) ? -120 : 120;
    stage.dispatchEvent(new WheelEvent('wheel', { deltaY: dy, clientX: innerWidth / 2, clientY: innerHeight / 2,
                                                   bubbles: true, cancelable: true }));
    i++;
    if (performance.now() - t0 < ms) requestAnimationFrame(step); else done(i);
  };
  requestAnimationFrame(step);
});
window.__zoom = () => { const m = /scale\(([\d.e-]+)\)/.exec(document.getElementById('canvas').style.transform); return m ? +m[1] : null; };
'''


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def ev(session, expr):
    session.cdp.deadline = time.monotonic() + 60
    r = session.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
    if 'exceptionDetails' in r:
        raise RuntimeError(f'{expr}: {r["exceptionDetails"]}')
    return r.get('result', {}).get('value')


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, max(0, int(math.ceil(len(v) * q)) - 1))] if v else float('inf')


def start_trace(session):
    session.cdp.sink = []
    session.cdp.deadline = time.monotonic() + 60
    session.call('Tracing.start', transferMode='ReportEvents', traceConfig={'includedCategories': [
        'disabled-by-default-devtools.timeline.frame', 'benchmark', 'input']})


def stop_trace(session):
    session.cdp.deadline = time.monotonic() + 120
    session.cdp.events.clear()
    session.call('Tracing.end')
    session.cdp.wait_event('Tracing.tracingComplete')
    evs = [e for m in session.cdp.sink if m['method'] == 'Tracing.dataCollected' for e in m['params']['value']]
    session.cdp.sink = None
    return evs


def stats(res, trace):
    """Presented frames come from the trace (Display::FrameDisplayed): requestAnimationFrame alone
    keeps ticking at 60 Hz while the compositor drops frames, so it hides the stutter users see."""
    t0, t1 = res['t0'], res['t1']
    shown = sorted(e['ts'] for e in trace if e['name'] == 'Display::FrameDisplayed')
    dur = (t1 - t0) / 1000
    deltas = [(b - a) / 1000 for a, b in zip(shown, shown[1:])]
    lat_b = {}
    lats = []
    for e in trace:
        if e['name'] != 'EventLatency':
            continue
        k = (e.get('id2') or {}).get('local') or e.get('id')
        if e['ph'] == 'b':
            lat_b[k] = e['ts']
        elif e['ph'] == 'e' and k in lat_b:
            lats.append((e['ts'] - lat_b.pop(k)) / 1000)
    fr = res['frames']
    lt = res['longtasks']
    return {'fps': round(len(shown) / dur, 1) if dur else 0,
            'p95_ms': round(pct(deltas, 0.95), 1), 'max_ms': round(max(deltas), 1) if deltas else None,
            'dropped': sum(1 for e in trace if e['name'] == 'DroppedFrame'),
            'raf_fps': round(max(0, len(fr) - 1) / dur, 1) if dur else 0,
            'input_latency_p95_ms': round(pct(lats, 0.95), 1) if lats else None,
            'longtasks': len(lt), 'longest_ms': round(max(lt), 1) if lt else 0}


def mouse(session, kind, x, y, **kw):
    session.cdp.deadline = time.monotonic() + 60
    session.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, **kw)


def pan(session, seconds=3.0):
    pt = ev(session, '__panPoint()')
    if not pt:
        return {'error': 'no empty spot to start a pan'}
    x0, y0 = pt
    start_trace(session)
    ev(session, '__startFrames()')
    mouse(session, 'mousePressed', x0, y0, button='left', buttons=1, clickCount=1)
    t = time.monotonic()
    end = t + seconds
    while time.monotonic() < end:
        k = (time.monotonic() - t) * 2 * math.pi / 1.5          # back and forth every 1.5 s
        mouse(session, 'mouseMoved', x0 + 300 * math.sin(k), y0 + 120 * math.sin(k / 2),
              button='left', buttons=1)
        time.sleep(0.004)
    mouse(session, 'mouseReleased', x0, y0, button='left', buttons=0, clickCount=1)
    res = ev(session, '__stopFrames()')
    return stats(res, stop_trace(session))


def wheel(session, x, y, dy):
    session.cdp.deadline = time.monotonic() + 60
    session.call('Input.dispatchMouseEvent', type='mouseWheel', x=x, y=y, deltaX=0, deltaY=dy)


def zoom(session, seconds=3.0):
    start_trace(session)
    ev(session, '__startFrames()')
    n = ev(session, f'__wheelFor({int(seconds * 1000)})')
    res = ev(session, '__stopFrames()')
    out = stats(res, stop_trace(session))
    out['events'] = n
    return out


def wait_full(session, t_limit=60):
    """ms from navigation start until every visible board shows content (None on timeout)."""
    end = time.monotonic() + t_limit
    while time.monotonic() < end:
        ready, total = ev(session, '__visibleReady()')
        if total and ready >= total:
            return round(ev(session, 'performance.now()'), 0), total
        time.sleep(0.05)
    ready, total = ev(session, '__visibleReady()')
    return None, f'{ready}/{total}'


def navigate(session, url):
    session.cdp.deadline = time.monotonic() + 60
    session.call('Emulation.setDeviceMetricsOverride', width=W, height=H, deviceScaleFactor=DPR, mobile=False)
    session.cdp.events.clear()
    session.call('Page.navigate', url=url)
    session.cdp.wait_event('Page.loadEventFired')


def run_once(session, url):
    navigate(session, url)
    t_end = time.monotonic() + 30
    fit = None
    while time.monotonic() < t_end:
        fit = ev(session, '__perf.fit')
        if fit is not None:
            break
        time.sleep(0.02)
    full, visible = wait_full(session)
    out = {'fit_ms': round(fit) if fit is not None else None, 'full_ms': full, 'visible_boards': visible,
           'fit_zoom': ev(session, '__zoom()')}
    time.sleep(1.0)
    out['pan_fit'] = pan(session)
    time.sleep(1.0)
    out['zoom'] = zoom(session)
    time.sleep(1.0)
    # zoom to about 60% around the center, let boards load, then pan
    z = ev(session, '__zoom()')
    steps = 0
    while z and not 0.55 <= z <= 0.7 and steps < 80:
        wheel(session, W / 2, H / 2, -40 if z < 0.55 else 40)
        z = ev(session, '__zoom()')
        steps += 1
    time.sleep(0.4)
    full60, _ = wait_full(session, 20)
    out['zoom_60'] = round(z, 3) if z else None
    out['pan_60_ready'] = full60 is not None
    time.sleep(1.0)
    out['pan_60'] = pan(session)
    return out


def main():
    args = sys.argv[1:]
    json_out = None
    runs, warm = 1, False
    if '--json' in args:
        i = args.index('--json'); json_out = args[i + 1]; del args[i:i + 2]
    if '--runs' in args:
        i = args.index('--runs'); runs = int(args[i + 1]); del args[i:i + 2]
    if '--warm' in args:
        args.remove('--warm'); warm = True
    script = CANVAS_PY
    global DPR
    if '--dpr' in args:
        i = args.index('--dpr'); DPR = float(args[i + 1]); del args[i:i + 2]
    if '--canvas' in args:
        i = args.index('--canvas'); script = os.path.abspath(args[i + 1]); del args[i:i + 2]
    src = os.path.abspath(args[0]) if args else os.path.join(REPO, 'examples', 'trailmate')
    idea = os.path.basename(src.rstrip('/'))
    tmp = tempfile.mkdtemp(prefix='mc-perf-')
    server = None
    try:
        design = os.path.join(tmp, 'design')
        shutil.copytree(src, os.path.join(design, idea), ignore=shutil.ignore_patterns('render', 'compare'))
        env = dict(os.environ, MOCKUP_CANVAS_HOME=os.path.join(tmp, 'home'))
        port = free_port()
        server = subprocess.Popen([sys.executable, script, 'serve', design, '--port', str(port)],
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        line = server.stdout.readline()
        if 'Server started' not in line:
            raise SystemExit(f'server did not start: {line}')
        url = f'http://127.0.0.1:{port}/{idea}/'
        n_boards = len(json.load(open(os.path.join(design, idea, 'canvas.json')))['boards'])
        results = []
        with canvas._CdpSession() as s:
            s.call('Page.addScriptToEvaluateOnNewDocument', source=INSTRUMENT)
            if warm:
                run_once(s, url)
            for _ in range(runs):
                results.append(run_once(s, url))
        report = {'idea': idea, 'boards': n_boards, 'viewport': f'{W}x{H}@{DPR:g}x', 'runs': results}
        for i, r in enumerate(results):
            print(f'run {i + 1} ({W}x{H}@{DPR:g}x): {n_boards} boards, fit {r["fit_ms"]} ms, all visible boards shown {r["full_ms"]} ms '
                  f'({r["visible_boards"]} visible, fit zoom {r["fit_zoom"]:.3f})')
            for k in ('pan_fit', 'zoom', 'pan_60'):
                m = r[k]
                if 'error' in m:
                    print(f'  {k:8s} {m["error"]}'); continue
                ok = m['fps'] >= 55 and m['p95_ms'] <= 25 and m['longest_ms'] <= 100
                print(f'  {k:8s} {m["fps"]:5.1f} fps  p95 {m["p95_ms"]:5.1f} ms  max {m["max_ms"]} ms  '
                      f'dropped {m["dropped"]}  long tasks {m["longtasks"]} (longest {m["longest_ms"]} ms)  '
                      f'rAF {m["raf_fps"]} fps  input p95 {m["input_latency_p95_ms"]} ms  {"OK" if ok else "MISS"}')
            print(f'  pan_60 at zoom {r["zoom_60"]}, boards loaded before pan: {r["pan_60_ready"]}')
        if json_out:
            with open(json_out, 'w') as f:
                json.dump(report, f, indent=2)
    finally:
        if server:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
