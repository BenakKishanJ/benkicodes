// Procedural pixel art, generated at build time as inline SVG.
// Colours are CSS variables, so every piece re-themes itself (wave / dragon / lotus).
// These are PLACEHOLDERS: drop real PNGs into /public/art/ (see HeroArt.astro) to replace them.

type Cell = string | null;
type Grid = Cell[][];

const V = (n: string, o?: number) => `var(--${n})` + (o ? `|${o}` : '');

export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

const makeGrid = (w: number, h: number): Grid => Array.from({ length: h }, () => Array<Cell>(w).fill(null));
const put = (g: Grid, x: number, y: number, c: Cell) => {
  if (y >= 0 && y < g.length && x >= 0 && x < g[0].length) g[y][x] = c;
};
const disc = (g: Grid, cx: number, cy: number, r: number, c: Cell) => {
  for (let y = 0; y < g.length; y++) for (let x = 0; x < g[0].length; x++)
    if ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r) g[y][x] = c;
};
const stamp = (g: Grid, x0: number, y0: number, rows: string[], map: Record<string, string>) =>
  rows.forEach((row, dy) => [...row].forEach((ch, dx) => { if (map[ch]) put(g, x0 + dx, y0 + dy, map[ch]); }));

/** Serialise a grid to an SVG string, merging horizontal runs per colour. */
export function gridToSvg(g: Grid, cls = 'art', label = ''): string {
  const h = g.length, w = g[0].length;
  const byFill = new Map<string, string>();
  g.forEach((row, y) => {
    let x = 0;
    while (x < w) {
      const c = row[x];
      if (!c) { x++; continue; }
      let n = 1;
      while (row[x + n] === c) n++;
      byFill.set(c, (byFill.get(c) ?? '') + `<rect x="${x}" y="${y}" width="${n}" height="1"/>`);
      x += n;
    }
  });
  let body = '';
  for (const [fill, rects] of byFill) {
    const [col, op] = fill.split('|');
    body += `<g fill="${col}"${op ? ` fill-opacity="${op}"` : ''}>${rects}</g>`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" class="${cls}" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${label}">${body}</svg>`;
}

/* ------------------------------------------------------------------ WAVE */
export function waveArt(): string {
  const W = 64, H = 44, g = makeGrid(W, H), r = rng(11);
  disc(g, 51, 10, 6.2, V('yellow'));
  for (let a = 0; a < 40; a++) { // sun halo dither
    const x = 43 + Math.floor(r() * 17), y = 2 + Math.floor(r() * 17);
    if (!g[y][x] && (x - 51) ** 2 + (y - 10) ** 2 < 90) g[y][x] = V('orange', 0.7);
  }
  // Fuji
  for (let y = 22; y < 36; y++) {
    const half = (y - 22) * 1.15 + 0.5;
    for (let x = Math.round(46 - half); x <= Math.round(46 + half); x++) put(g, x, y, y < 26 ? V('fg') : V('violet'));
  }
  // sea
  for (let x = 0; x < W; x++) {
    const sy = 35 + Math.round(Math.sin(x * 0.55) * 0.8);
    for (let y = sy; y < H; y++) put(g, x, y, (x + y) % 3 === 0 && y > sy + 1 ? V('aqua') : V('blue'));
  }
  // curling crest = big disc minus offset disc
  const c1 = [23.5, 32.5, 17.5], c2 = [31, 29.5, 11.2];
  for (let y = 0; y < 38; y++) for (let x = 0; x < W; x++) {
    const d1 = Math.hypot(x + 0.5 - c1[0], y + 0.5 - c1[1]);
    const d2 = Math.hypot(x + 0.5 - c2[0], y + 0.5 - c2[1]);
    if (d1 <= c1[2] && d2 > c2[2]) {
      const edge = c1[2] - d1, inner = d2 - c2[2];
      let col = V('blue');
      if (inner < 1.6) col = V('violet');
      else if (edge < 1.7) col = (x + y) % 2 === 0 || edge < 0.9 ? V('fg') : V('aqua');
      else if (edge < 4.5) col = V('aqua');
      put(g, x, y, col);
    }
  }
  // spray at the tip
  for (let k = 0; k < 70; k++) {
    const x = 28 + Math.floor(r() * 17), y = 9 + Math.floor(r() * 14);
    const near = Math.hypot(x - 34, y - 17);
    if (!g[y][x] && r() < 0.5 - near / 30) g[y][x] = V('fg');
  }
  // gulls
  stamp(g, 8, 6, ['#.#', '.#.'], { '#': V('fg') });
  stamp(g, 14, 3, ['#.#', '.#.'], { '#': V('fg') });
  return gridToSvg(g, 'art', 'Pixel art: a great wave curling in front of a mountain and a low sun');
}

/* ---------------------------------------------------------------- DRAGON */
export function dragonArt(): string {
  const W = 64, H = 44, g = makeGrid(W, H), r = rng(5);
  [[4, 8], [40, 5], [12, 34], [46, 36]].forEach(([x, y]) =>
    stamp(g, x, y, ['...####.....', '..########..', '.###########', '############'], { '#': V('line', 0.55) }));
  for (let i = 0; i < 26; i++) put(g, Math.floor(r() * W), Math.floor(r() * 20), V('fg', 0.8));
  put(g, 56, 7, V('fg')); put(g, 57, 7, V('fg')); put(g, 56, 8, V('fg')); put(g, 55, 7, V('fg')); put(g, 56, 6, V('fg'));
  // serpentine body
  const pts: [number, number, number][] = [];
  for (let i = 0; i <= 600; i++) {
    const t = i / 600;
    const x = 3 + t * 46;
    const y = 27 + 10 * Math.sin(t * Math.PI * 2.6 + 0.4) - t * 11;
    const th = 1.6 + 3.4 * Math.sin(Math.PI * Math.min(1, t * 1.15)) ** 0.6;
    pts.push([x, y, th]);
  }
  pts.forEach(([x, y, th], i) => {
    for (let dy = -Math.ceil(th); dy <= Math.ceil(th); dy++) for (let dx = -Math.ceil(th); dx <= Math.ceil(th); dx++) {
      if (dx * dx + dy * dy > th * th) continue;
      const px = Math.round(x + dx), py = Math.round(y + dy);
      let col = V('green');
      if (dy > th * 0.35) col = V('yellow');
      else if ((px + py) % 4 === 0) col = V('aqua');
      put(g, px, py, col);
    }
    if (i % 22 === 0) { put(g, Math.round(x), Math.round(y - th - 1), V('red')); put(g, Math.round(x), Math.round(y - th - 2), V('orange')); }
  });
  // head (faces right)
  stamp(g, 47, 5, [
    '.w...w......', '.ww..ww.....', '.ggggggg....', 'ggggeggggg..',
    'gggggggggggw', 'ggrrrrrrrrr.', '.ggwgwgwggg.', '..gggggggg..',
  ], { g: V('green'), w: V('fg'), e: V('yellow'), r: V('red') });
  for (let i = 0; i < 6; i++) { put(g, 59 + i, 11 + (i % 2), V('orange')); put(g, 58 - i, 14 + i, V('orange', 0.8)); }
  return gridToSvg(g, 'art', 'Pixel art: a serpentine dragon winding through clouds');
}

/* ----------------------------------------------------------------- LOTUS */
export function lotusArt(): string {
  const W = 64, H = 44, g = makeGrid(W, H), r = rng(3);
  const base: [number, number] = [32, 35];
  const petal = (deg: number, len: number, wid: number, col: string, hi?: string) => {
    const th = (deg * Math.PI) / 180;
    const u = [Math.sin(th), -Math.cos(th)], v = [Math.cos(th), Math.sin(th)];
    const c = [base[0] + u[0] * len / 2, base[1] + u[1] * len / 2];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - c[0], dy = y + 0.5 - c[1];
      const a = (dx * u[0] + dy * u[1]) / (len / 2), b = (dx * v[0] + dy * v[1]) / wid;
      if (a * a + b * b <= 1) put(g, x, y, hi && Math.abs(b) < 0.14 && a > -0.2 ? hi : col);
    }
  };
  for (let i = 0; i < 18; i++) put(g, Math.floor(r() * W), Math.floor(r() * 14), V('fg', 0.7));
  petal(-78, 24, 5.2, V('violet')); petal(78, 24, 5.2, V('violet'));
  petal(-44, 30, 6, V('pink', 0.85), V('fg')); petal(44, 30, 6, V('pink', 0.85), V('fg'));
  petal(-16, 34, 6.4, V('pink'), V('fg')); petal(16, 34, 6.4, V('pink'), V('fg'));
  petal(0, 36, 6.2, V('pink'), V('fg'));
  for (let y = 2; y < 8; y++) put(g, 32 + (y % 2 ? 0 : -1), y + 1, V('fg'));
  disc(g, 32, 34.5, 2.4, V('yellow'));
  // lily pad with a notch
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const dx = (x + 0.5 - 32) / 28, dy = (y + 0.5 - 38.5) / 3.6;
    if (dx * dx + dy * dy <= 1 && !(x > 41 && x < 49 && y <= 38)) put(g, x, y, y > 39 ? V('green', 0.8) : V('green'));
  }
  for (let x = 4; x < 60; x++) if (r() < 0.45) put(g, x, 42 + (x % 2), V('blue'));
  disc(g, 32, 34.5, 2.4, V('yellow'));
  return gridToSvg(g, 'art', 'Pixel art: a pink lotus flower on a lily pad');
}

/* ----------------------------------------------- generative post covers */
const COVER_COLORS = ['blue', 'green', 'pink', 'violet', 'aqua', 'orange', 'yellow', 'red'];
export function coverArt(seed: string): string {
  const W = 32, H = 18, g = makeGrid(W, H), r = rng(hash(seed));
  const pick = () => COVER_COLORS[Math.floor(r() * COVER_COLORS.length)];
  const [c1, c2, c3] = [pick(), pick(), pick()];
  const sun = pick();
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) g[y][x] = V('surface2');
  for (let k = 0; k < 14; k++) put(g, Math.floor(r() * W), Math.floor(r() * 7), V('fg', 0.8));
  disc(g, 4 + r() * 24, 4 + r() * 3, 2 + r() * 1.4, V(sun));
  const layers: [string, number, number, number][] = [[c1, 0.5, 9, 3], [c2, 0.75, 12, 3], [c3, 1, 15, 2.2]];
  layers.forEach(([c, o, baseY, amp]) => {
    const ph = r() * 6, fr = 0.18 + r() * 0.25;
    for (let x = 0; x < W; x++) {
      const top = Math.round(baseY - amp * Math.sin(x * fr + ph) - amp * 0.6 * Math.sin(x * fr * 2.3 + ph * 2));
      for (let y = top; y < H; y++) put(g, x, y, V(c, o));
    }
  });
  if (r() > 0.4) { // a tiny hut / tree on the front ridge
    const x = 3 + Math.floor(r() * 26);
    for (let y = 0; y < H; y++) if (g[y][x]?.startsWith(`var(--${c3})`)) {
      put(g, x, y - 1, V('fg')); put(g, x, y - 2, V('fg')); put(g, x + 1, y - 1, V('fg')); break;
    }
  }
  return gridToSvg(g, 'cover-art', '');
}

/* ----------------------------------------------- dissolve edge (dither) */
export function edgeSvg(cols: number, rows: number, seed = 1, flip = false): string {
  const r = rng(seed * 977 + cols);
  const g = makeGrid(cols, rows);
  for (let y = 0; y < rows; y++) {
    const p = Math.pow((y + 1) / rows, 1.7);
    for (let x = 0; x < cols; x++) if (y === rows - 1 || r() < p) g[y][x] = 'currentColor';
  }
  if (flip) g.reverse();
  return gridToSvg(g, 'edge-svg').replace('preserveAspectRatio="xMidYMid slice"', 'preserveAspectRatio="none"');
}
