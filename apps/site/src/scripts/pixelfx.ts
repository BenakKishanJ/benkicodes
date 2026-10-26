// Pixel effects shared by the whole site: wipe transition, dissolve reveal, confetti, click sparks.
export const fxOn = (): boolean =>
  document.documentElement.dataset.fx !== 'off' && !matchMedia('(prefers-reduced-motion: reduce)').matches;

function animate(dur: number, frame: (t: number) => void): Promise<void> {
  return new Promise((res) => {
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / dur);
      frame(t);
      t < 1 ? requestAnimationFrame(step) : res();
    };
    requestAnimationFrame(step);
  });
}

/**
 * Covers the screen with pixel blocks. Resolves once fully covered and returns a
 * `reveal()` that dissolves the blocks away. Callers swap their content in between.
 */
export async function wipeCover(color: string, accent?: string, dur = 420): Promise<() => Promise<void>> {
  if (!fxOn()) return async () => {};
  const size = innerWidth < 768 ? 24 : 40;
  const c = document.createElement('canvas');
  c.className = 'pxwipe';
  c.width = innerWidth; c.height = innerHeight;
  document.body.append(c);
  const ctx = c.getContext('2d')!;
  const cols = Math.ceil(c.width / size), rows = Math.ceil(c.height / size), n = cols * rows;
  const rank = new Float32Array(n), accented = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const x = i % cols, y = (i / cols) | 0;
    rank[i] = (x / cols + y / rows) * 0.2 + Math.random() * 0.6;
    accented[i] = Math.random() < 0.1 ? 1 : 0;
  }
  const done = new Uint8Array(n);
  await animate(dur, (t) => {
    for (let i = 0; i < n; i++) if (!done[i] && rank[i] <= t * 0.8) {
      done[i] = 1;
      ctx.fillStyle = accented[i] && accent ? accent : color;
      ctx.fillRect((i % cols) * size, ((i / cols) | 0) * size, size, size);
    }
  });
  ctx.fillStyle = color; ctx.fillRect(0, 0, c.width, c.height);
  return async () => {
    const gone = new Uint8Array(n);
    await animate(dur, (t) => {
      for (let i = 0; i < n; i++) if (!gone[i] && rank[i] <= t * 0.8) {
        gone[i] = 1;
        ctx.clearRect((i % cols) * size, ((i / cols) | 0) * size, size, size);
      }
      if (t === 1) ctx.clearRect(0, 0, c.width, c.height);
    });
    c.remove();
  };
}

/** Image-frame reveal: a layer of blocks in the frame's own colour dissolves to show the art. */
export function dissolveEl(el: HTMLElement, dur = 900): void {
  if (!fxOn() || el.dataset.dissolved) return;
  el.dataset.dissolved = '1';
  const r = el.getBoundingClientRect();
  if (!r.width) return;
  const size = 12;
  const c = document.createElement('canvas');
  c.className = 'dissolve-layer';
  c.width = Math.ceil(r.width); c.height = Math.ceil(r.height);
  el.append(c);
  const ctx = c.getContext('2d')!;
  const color = getComputedStyle(el).backgroundColor;
  const cols = Math.ceil(c.width / size), rows = Math.ceil(c.height / size), n = cols * rows;
  ctx.fillStyle = color; ctx.fillRect(0, 0, c.width, c.height);
  const rank = Float32Array.from({ length: n }, (_, i) => ((i / cols | 0) / rows) * 0.35 + Math.random() * 0.65);
  const gone = new Uint8Array(n);
  animate(dur, (t) => {
    const steps = Math.floor(t * 8) / 8; // stepped, like a sprite sheet
    for (let i = 0; i < n; i++) if (!gone[i] && rank[i] <= steps) {
      gone[i] = 1;
      ctx.clearRect((i % cols) * size, ((i / cols) | 0) * size, size, size);
    }
    if (t === 1) c.remove();
  });
}

/** Pixel confetti burst, used when a quiz is passed. */
export function pixelConfetti(x = innerWidth / 2, y = innerHeight / 2): void {
  if (!fxOn()) return;
  const cs = getComputedStyle(document.documentElement);
  const cols = ['--a-blue', '--a-green', '--a-pink', '--a-yellow', '--a-violet', '--a-orange'].map((v) => cs.getPropertyValue(v).trim() || '#fff');
  const c = document.createElement('canvas');
  c.className = 'pxwipe';
  c.width = innerWidth; c.height = innerHeight;
  document.body.append(c);
  const ctx = c.getContext('2d')!;
  const ps = Array.from({ length: 90 }, () => {
    const a = Math.random() * Math.PI * 2, s = 4 + Math.random() * 10;
    return { x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 7, s: [6, 8, 10, 12][(Math.random() * 4) | 0], c: cols[(Math.random() * cols.length) | 0] };
  });
  animate(1900, (t) => {
    ctx.clearRect(0, 0, c.width, c.height);
    ps.forEach((p) => {
      p.x += p.vx; p.y += p.vy; p.vy += 0.38; p.vx *= 0.985;
      ctx.globalAlpha = t > 0.7 ? 1 - (t - 0.7) / 0.3 : 1;
      ctx.fillStyle = p.c;
      ctx.fillRect(Math.round(p.x / 4) * 4, Math.round(p.y / 4) * 4, p.s, p.s);
    });
    if (t === 1) c.remove();
  });
}

const SPARK_COLORS = ['--a-yellow', '--a-pink', '--a-blue', '--a-green', '--a-orange'];
/** Tiny square burst under the pointer on every click. */
export function sparks(x: number, y: number): void {
  if (!fxOn()) return;
  for (let i = 0; i < 8; i++) {
    const s = document.createElement('i');
    s.className = 'spark';
    const a = (i / 8) * Math.PI * 2 + Math.random() * 0.4, d = 18 + Math.random() * 18;
    s.style.cssText = `left:${x}px;top:${y}px;--dx:${Math.round(Math.cos(a) * d / 4) * 4}px;--dy:${Math.round(Math.sin(a) * d / 4) * 4}px;background:var(${SPARK_COLORS[i % SPARK_COLORS.length]})`;
    document.body.append(s);
    setTimeout(() => s.remove(), 520);
  }
}
