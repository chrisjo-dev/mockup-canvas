import { test as base, expect, Page, TestInfo, Locator } from '@playwright/test';
import { spawn, execFileSync, ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';

export const REPO = path.resolve(__dirname, '..', '..');
export const CANVAS_PY = path.join(REPO, 'skills', 'mockup-canvas', 'scripts', 'canvas.py');
export const EXAMPLE_IDEA = path.join(REPO, 'examples', 'trailmate');
const PYTHON = process.env.MC_E2E_PYTHON || 'python3';
// Ports other sessions use; never take them even when free
const RESERVED = new Set([4400, 8080, 8787, 5173]);
const TMP_ROOT = process.env.MC_E2E_TMP || path.join(os.tmpdir(), 'mockup-canvas-e2e');

export async function freePort(): Promise<number> {
  for (;;) {
    const port = await new Promise<number>((resolve, reject) => {
      const srv = net.createServer();
      srv.once('error', reject);
      srv.listen(0, '127.0.0.1', () => {
        const p = (srv.address() as net.AddressInfo).port;
        srv.close(() => resolve(p));
      });
    });
    if (!RESERVED.has(port)) return port;
  }
}

export type Server = {
  port: number;
  origin: string;      // http://127.0.0.1:<port>
  token: string;       // share token, '' when not sharing
  output: () => string;
  stop: () => Promise<void>;
};

export class Sandbox {
  readonly root: string;
  readonly home: string;
  readonly data: string;
  readonly work: string;
  readonly alphaDesign: string;
  readonly idea: string;          // alpha/design/trailmate
  readonly betaDesign: string;
  private servers: Server[] = [];

  constructor(name: string) {
    fs.mkdirSync(TMP_ROOT, { recursive: true });
    this.root = fs.realpathSync(fs.mkdtempSync(path.join(TMP_ROOT, name.replace(/[^a-z0-9]+/gi, '-').slice(0, 40) + '-')));
    this.home = path.join(this.root, 'home');
    this.data = path.join(this.home, '.mcdata');
    this.work = path.join(this.home, 'work');
    this.alphaDesign = path.join(this.work, 'alpha', 'design');
    this.betaDesign = path.join(this.work, 'beta', 'design');
    this.idea = path.join(this.alphaDesign, 'trailmate');
    fs.mkdirSync(this.data, { recursive: true });
    fs.cpSync(EXAMPLE_IDEA, this.idea, { recursive: true });
  }

  /** A second registrable design folder (a copy of trailmate named "second"). */
  makeBeta(): string {
    fs.cpSync(EXAMPLE_IDEA, path.join(this.betaDesign, 'second'), { recursive: true });
    return this.betaDesign;
  }

  env(): NodeJS.ProcessEnv {
    // HOME is the sandbox: the server only accepts design folders under HOME, and the user's
    // real registry (~/.mockup-canvas) is never read or written.
    return { ...process.env, HOME: this.home, MOCKUP_CANVAS_HOME: this.data, PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1' };
  }

  cli(...args: string[]): string {
    return execFileSync(PYTHON, [CANVAS_PY, ...args], { env: this.env(), encoding: 'utf8', timeout: 60_000 });
  }

  rootsFile(): any[] {
    const p = path.join(this.data, 'roots.json');
    if (!fs.existsSync(p)) return [];
    const d = JSON.parse(fs.readFileSync(p, 'utf8'));
    return Array.isArray(d) ? d : (d.roots || []);
  }

  canvasJson(idea = this.idea): any {
    return JSON.parse(fs.readFileSync(path.join(idea, 'canvas.json'), 'utf8'));
  }

  /** Starts a process in its own process group and waits until `ready` matches its output. */
  async spawn(cmd: string, args: string[], ready: RegExp, cwd?: string): Promise<{ proc: ChildProcess; out: () => string; match: RegExpMatchArray }> {
    const proc = spawn(cmd, args, { env: this.env(), cwd, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let buf = '';
    proc.stdout!.on('data', (d) => { buf += d.toString(); });
    proc.stderr!.on('data', (d) => { buf += d.toString(); });
    const deadline = Date.now() + 20_000;
    while (Date.now() < deadline) {
      const m = buf.match(ready);
      if (m) return { proc, out: () => buf, match: m };
      if (proc.exitCode !== null) break;
      await new Promise((r) => setTimeout(r, 100));
    }
    killGroup(proc);
    throw new Error(`process did not become ready (${cmd} ${args.join(' ')}):\n${buf}`);
  }

  private track(proc: ChildProcess, port: number, token: string, out: () => string): Server {
    const s: Server = {
      port, token, origin: `http://127.0.0.1:${port}`, output: out,
      stop: async () => { await stopGroup(proc); },
    };
    this.servers.push(s);
    return s;
  }

  /** canvas.py serve [args]; resolves once the URL is printed. */
  async serve(args: string[] = []): Promise<Server> {
    const port = await freePort();
    const { proc, out, match } = await this.spawn(PYTHON, [CANVAS_PY, 'serve', ...args, '--port', String(port)],
      /(?:Server started[^:]*: http:\/\/127\.0\.0\.1:(\d+)\/)|(?:Share URL: http:\/\/[^:]+:(\d+)\/\?t=([A-Za-z0-9_-]+))/);
    const actual = Number(match[1] || match[2]);
    if (RESERVED.has(actual)) throw new Error('server took a reserved port ' + actual);
    return this.track(proc, actual, match[3] || '', out);
  }

  /** Registry mode with the alpha project registered. */
  async serveRegistry(extraRoots: Array<[string, string]> = []): Promise<Server> {
    this.cli('roots', 'add', this.alphaDesign, '--name', 'alpha');
    for (const [dir, name] of extraRoots) this.cli('roots', 'add', dir, '--name', name);
    return this.serve();
  }

  /** A plain static server for an exported folder. */
  async serveStatic(dir: string): Promise<Server> {
    const port = await freePort();
    const { proc, out } = await this.spawn(PYTHON, ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', dir],
      /Serving HTTP/);
    return this.track(proc, port, '', out);
  }

  async dispose(keep: boolean) {
    for (const s of this.servers) await s.stop();
    this.servers = [];
    if (!keep && !process.env.MC_E2E_KEEP) fs.rmSync(this.root, { recursive: true, force: true });
  }
}

function killGroup(proc: ChildProcess, sig: NodeJS.Signals = 'SIGTERM') {
  if (proc.pid === undefined || proc.exitCode !== null) return;
  try { process.kill(-proc.pid, sig); } catch { /* already gone */ }
}

async function stopGroup(proc: ChildProcess) {
  if (proc.exitCode !== null || proc.signalCode !== null) return;
  const done = new Promise((r) => proc.once('exit', r));
  killGroup(proc, 'SIGTERM');
  const t = setTimeout(() => killGroup(proc, 'SIGKILL'), 3000);
  await Promise.race([done, new Promise((r) => setTimeout(r, 5000))]);
  clearTimeout(t);
  // Also stop anything left in the group (the server's background Chrome for thumbnails)
  if (proc.pid !== undefined) { try { process.kill(-proc.pid, 'SIGKILL'); } catch { /* none left */ } }
}

type Fixtures = { sandbox: Sandbox; consoleErrors: string[] };

export const test = base.extend<Fixtures>({
  sandbox: async ({}, use, testInfo) => {
    const sb = new Sandbox(testInfo.project.name + '-' + testInfo.title);
    await use(sb);
    await sb.dispose(testInfo.status !== testInfo.expectedStatus);
  },
  consoleErrors: async ({ page }, use) => {
    const errors: string[] = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
    await use(errors);
  },
});
export { expect };

// ── Screenshots for the report (not committed) ──
export async function shot(page: Page, testInfo: TestInfo, name: string) {
  const dir = process.env.MC_E2E_SHOTS
    ? path.join(process.env.MC_E2E_SHOTS, testInfo.project.name)
    : testInfo.outputDir;
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, name + '.png');
  await page.screenshot({ path: file });
  return file;
}

export function record(testInfo: TestInfo, name: string, value: unknown) {
  testInfo.annotations.push({ type: name, description: JSON.stringify(value) });
  if (process.env.MC_E2E_SHOTS) {
    fs.mkdirSync(process.env.MC_E2E_SHOTS, { recursive: true });
    fs.appendFileSync(path.join(process.env.MC_E2E_SHOTS, 'metrics.jsonl'),
      JSON.stringify({ project: testInfo.project.name, test: testInfo.title, name, value }) + '\n');
  }
}

// ── Viewer helpers ──
export async function openCanvas(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator('#loading')).toHaveClass(/gone/, { timeout: 15_000 });
  await expect(page.locator('.board').first()).toBeAttached();
}

export function board(page: Page, file: string): Locator {
  return page.locator(`.board[data-file="${file}"]`);
}
export function bar(page: Page, file: string): Locator {
  return board(page, file).locator('.board-bar');
}

export type Xform = { x: number; y: number; s: number };
export async function xform(page: Page): Promise<Xform> {
  const t = await page.locator('#canvas').evaluate((el) => (el as HTMLElement).style.transform);
  const m = t.match(/translate\(([-\d.e]+)px,\s*([-\d.e]+)px\)\s*scale\(([-\d.e]+)\)/);
  if (!m) throw new Error('unexpected transform: ' + t);
  return { x: +m[1], y: +m[2], s: +m[3] };
}

/** Waits until the transform stops changing (the viewer settles about 300 ms after input). */
export async function settled(page: Page) {
  let prev = '';
  for (let i = 0; i < 40; i++) {
    const cur = JSON.stringify(await xform(page));
    if (cur === prev) break;
    prev = cur;
    await page.waitForTimeout(150);
  }
  await page.waitForTimeout(450);
}

/** Wheel-zooms in over the centre of a board until the zoom is at least `target`. */
export async function zoomInOn(page: Page, file: string, target = 0.6) {
  for (let i = 0; i < 30; i++) {
    const { s } = await xform(page);
    if (s >= target) break;
    const box = await board(page, file).boundingBox();
    if (!box) throw new Error('board not laid out: ' + file);
    const vp = page.viewportSize()!;
    const cx = Math.min(Math.max(box.x + box.width / 2, 5), vp.width - 5);
    const cy = Math.min(Math.max(box.y + Math.min(box.height / 2, 200), 5), vp.height - 60);
    await page.mouse.move(cx, cy);
    await page.mouse.wheel(0, -120);
    await page.waitForTimeout(60);
  }
  await settled(page);
}

/** A viewport point where only the stage or the canvas element is under the pointer. */
export async function emptyPoint(page: Page): Promise<{ x: number; y: number }> {
  const p = await page.evaluate(() => {
    const stage = document.getElementById('stage');
    const cvs = document.getElementById('canvas');
    for (let y = 30; y < innerHeight - 80; y += 25) {
      for (let x = 30; x < innerWidth - 30; x += 25) {
        const ok = (px: number, py: number) => { const e = document.elementFromPoint(px, py); return e === stage || e === cvs; };
        if (ok(x, y) && ok(x + 160, y + 90) && ok(x + 80, y + 45)) return { x, y };
      }
    }
    return null;
  });
  if (!p) throw new Error('no empty point on the stage');
  return p;
}

export async function arrowPaths(page: Page): Promise<string[]> {
  return page.locator('#arrow-svg > path').evaluateAll((els) => els.map((e) => e.getAttribute('d') || ''));
}
