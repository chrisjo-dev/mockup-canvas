/**
 * A tiny valid TrueType font for tests: the letter "A" is a solid square that fills the em box
 * (ascent 800, descent 200 of 1000 units), every other character falls back. Text set in it with
 * line-height 1 draws a solid black block, which is easy to find in a screenshot and impossible to
 * mistake for a fallback font.
 */
function table(parts: Array<[string, number]>): Buffer {
  // [kind, value]: 'u16' | 'i16' | 'u32' | 'i32'
  const size = parts.reduce((n, [k]) => n + (k.endsWith('16') ? 2 : 4), 0);
  const b = Buffer.alloc(size);
  let o = 0;
  for (const [k, v] of parts) {
    if (k === 'u16') b.writeUInt16BE(v & 0xffff, o);
    else if (k === 'i16') b.writeInt16BE(v, o);
    else if (k === 'u32') b.writeUInt32BE(v >>> 0, o);
    else b.writeInt32BE(v, o);
    o += k.endsWith('16') ? 2 : 4;
  }
  return b;
}
const u16 = (v: number): [string, number] => ['u16', v];
const i16 = (v: number): [string, number] => ['i16', v];
const u32 = (v: number): [string, number] => ['u32', v];

function checksum(b: Buffer): number {
  const p = Buffer.concat([b, Buffer.alloc((4 - (b.length % 4)) % 4)]);
  let s = 0;
  for (let i = 0; i < p.length; i += 4) s = (s + p.readUInt32BE(i)) >>> 0;
  return s;
}

function nameTable(family: string): Buffer {
  const names: Array<[number, string]> = [[1, family], [2, 'Regular'], [3, family + '-Regular'],
    [4, family], [5, 'Version 1.0'], [6, family]];
  const strings = names.map(([, s]) => Buffer.from(s, 'utf16le').swap16());
  const head = table([u16(0), u16(names.length), u16(6 + 12 * names.length)]);
  let off = 0;
  const recs = names.map(([id], i) => {
    const r = table([u16(3), u16(1), u16(0x409), u16(id), u16(strings[i].length), u16(off)]);
    off += strings[i].length;
    return r;
  });
  return Buffer.concat([head, ...recs, ...strings]);
}

export function blockFont(family = 'QaBlock'): Buffer {
  const glyph = Buffer.concat([
    table([i16(1), i16(0), i16(-200), i16(1000), i16(800)]),   // 1 contour, bbox
    table([u16(3), u16(0)]),                                   // endPts [3], no instructions
    Buffer.from([1, 1, 1, 1]),                                 // 4 on-curve points, 16-bit deltas
    table([i16(0), i16(0), i16(1000), i16(0)]),                // x: 0, 0, 1000, 1000
    table([i16(-200), i16(1000), i16(0), i16(-1000)]),         // y: -200, 800, 800, -200
  ]);
  const glyf = Buffer.concat([glyph, Buffer.alloc((4 - (glyph.length % 4)) % 4)]);
  const tables: Record<string, Buffer> = {
    'OS/2': table([u16(3), i16(1000), u16(400), u16(5), u16(0),
      i16(650), i16(700), i16(0), i16(140), i16(650), i16(700), i16(0), i16(480), i16(50), i16(300), i16(0),
      u32(0), u32(0), u16(0),                                  // panose (10 bytes)
      u32(1), u32(0), u32(0), u32(0), u32(0x4e4f4e45),         // unicode ranges, vendor 'NONE'
      u16(0x40), u16(0x41), u16(0x41), i16(800), i16(-200), i16(0), u16(800), u16(200),
      u32(1), u32(0), i16(500), i16(700), u16(0), u16(0x20), u16(1)]),
    cmap: Buffer.concat([table([u16(0), u16(1), u16(3), u16(1), u32(12)]),
      table([u16(4), u16(32), u16(0), u16(4), u16(4), u16(1), u16(0),
        u16(0x41), u16(0xffff), u16(0), u16(0x41), u16(0xffff), u16(1 - 0x41), u16(1), u16(0), u16(0)])]),
    glyf,
    head: table([u32(0x00010000), u32(0x00010000), u32(0), u32(0x5f0f3cf5), u16(0x000b), u16(1000),
      u32(0), u32(0), u32(0), u32(0), i16(0), i16(-200), i16(1000), i16(800), u16(0), u16(8), i16(2), i16(0), i16(0)]),
    hhea: table([u32(0x00010000), i16(800), i16(-200), i16(0), u16(1000), i16(0), i16(0), i16(1000),
      i16(1), i16(0), i16(0), i16(0), i16(0), i16(0), i16(0), i16(0), u16(2)]),
    hmtx: table([u16(1000), i16(0), u16(1000), i16(0)]),
    loca: table([u16(0), u16(0), u16(glyf.length / 2)]),
    maxp: table([u32(0x00010000), u16(2), u16(4), u16(1), u16(0), u16(0), u16(2), u16(0), u16(0),
      u16(0), u16(0), u16(0), u16(0), u16(0), u16(0)]),
    name: nameTable(family),
    post: table([u32(0x00030000), u32(0), i16(-100), i16(50), u32(0), u32(0), u32(0), u32(0), u32(0)]),
  };
  const tags = Object.keys(tables).sort();
  const n = tags.length;
  const es = Math.floor(Math.log2(n)), sr = 16 * 2 ** es;
  const header = table([u32(0x00010000), u16(n), u16(sr), u16(es), u16(n * 16 - sr)]);
  let off = 12 + 16 * n;
  const dir: Buffer[] = [], data: Buffer[] = [];
  for (const tag of tags) {
    const t = tables[tag];
    const rec = Buffer.alloc(16);
    rec.write(tag, 0, 'latin1');
    rec.writeUInt32BE(checksum(t), 4);
    rec.writeUInt32BE(off, 8);
    rec.writeUInt32BE(t.length, 12);
    dir.push(rec);
    const padded = Buffer.concat([t, Buffer.alloc((4 - (t.length % 4)) % 4)]);
    data.push(padded);
    off += padded.length;
  }
  const font = Buffer.concat([header, ...dir, ...data]);
  // head.checkSumAdjustment
  const headOff = 12 + 16 * n + data.slice(0, tags.indexOf('head')).reduce((a, b) => a + b.length, 0);
  font.writeUInt32BE((0xb1b0afba - checksum(font)) >>> 0, headOff + 8);
  return font;
}
