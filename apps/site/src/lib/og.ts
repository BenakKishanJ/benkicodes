// SE-6: build-time OG image generation (1200x630) with Satori + resvg.
// One PNG per page, rendered during `astro build` by the /og/[...route].png
// endpoint, so dist ships real .png files (no edge runtime needed).
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import type { ReactNode } from 'react';
import satori from 'satori';
import { Resvg, initWasm } from '@resvg/resvg-wasm';

const resolve = (spec: string) => createRequire(import.meta.url).resolve(spec);

const fontData = readFileSync(
  resolve('@fontsource/press-start-2p/files/press-start-2p-latin-400-normal.woff'),
);

let wasmReady: Promise<void> | null = null;
const ensureWasm = () => {
  wasmReady ??= initWasm(readFileSync(resolve('@resvg/resvg-wasm/index_bg.wasm')));
  return wasmReady;
};

// Satori only ships glyphs the pixel font covers; frontmatter can carry
// typographic quotes and dashes, so normalise to plain ASCII.
const ascii = (s: string) =>
  s
    .replace(/[’‘]/g, "'")
    .replace(/[“”"]/g, '"')
    .replace(/[−–—·]/g, '-')
    .replace(/[^\x20-\x7E]/g, '-');

const WIDTH = 1200;
const HEIGHT = 630;

function wrap(text: string, maxChars: number, maxLines: number) {
  const words = ascii(text).split(/\s+/);
  const lines: string[] = [];
  let line = '';
  for (const w of words) {
    const next = line ? `${line} ${w}` : w;
    if (next.length > maxChars && line) {
      lines.push(line);
      line = w;
      if (lines.length === maxLines) break;
    } else {
      line = next;
    }
  }
  if (lines.length < maxLines && line) lines.push(line);
  if (lines.join(' ').length < ascii(text).length && lines.length === maxLines) {
    lines[maxLines - 1] = `${lines[maxLines - 1].slice(0, maxChars - 1)}+`;
  }
  return lines;
}

// Kanagawa wave palette, mirroring src/lib/themes.ts (dark default theme).
const C = { bg: '#1F1F28', fg: '#DCD7BA', dim: '#727169', accent: '#7E9CD8', accent2: '#957FB8' };

export interface OgInput {
  title: string;
  description?: string;
  /** Small chip in the top-right, e.g. "blog", "roadmap", "part 2/5". */
  label?: string;
}

interface SatoriNode {
  type: 'div';
  props: { style: Record<string, unknown>; children?: unknown };
}

const div = (style: Record<string, unknown>, children?: unknown): SatoriNode => ({
  type: 'div',
  props: { style, children },
});

const asTree = (node: unknown) => node as unknown as ReactNode;

export async function generateOg({ title, description, label }: OgInput): Promise<Buffer> {
  await ensureWasm();
  const size = 40;
  const maxChars = Math.floor((WIDTH - 160) / size); // 2x80px side padding
  const lines = wrap(title, maxChars, 4);

  // Yoga treats width as the content box, so padding lives on an inner
  // flex:1 wrapper - padding on the 100%-wide root would overflow the canvas.
  const root = div(
    {
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: C.bg,
    },
    [
      div(
        {
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          flex: 1,
          padding: '64px 80px',
        },
        [
          div(
            { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
            [
              div({ display: 'flex', color: C.accent2, fontSize: 18 }, 'benki-codes'),
              label &&
                div(
                  {
                    display: 'flex',
                    color: C.bg,
                    background: C.accent,
                    fontSize: 16,
                    padding: '6px 12px',
                  },
                  ascii(label),
                ),
            ].filter(Boolean),
          ),
          div(
            {
              display: 'flex',
              flexDirection: 'column',
              gap: 24,
              marginTop: 24,
              color: C.fg,
              fontSize: size,
              lineHeight: '1.4em',
            },
            lines.map((l) => div({ display: 'flex' }, l)),
          ),
          description &&
            div(
              { display: 'flex', color: C.dim, fontSize: 19, lineHeight: '1.7em', maxWidth: '980px' },
              wrap(description, 78, 2).join(' '),
            ),
          div({ display: 'flex', alignItems: 'flex-end', gap: 12 }, [
            div({ display: 'flex', width: 60, height: 8, background: C.accent }),
            div({ display: 'flex', width: 24, height: 8, background: C.accent2 }),
            div({ display: 'flex', width: 8, height: 8, background: C.fg }),
          ]),
        ].filter(Boolean),
      ),
    ],
  );

  const svg = await satori(asTree(root), {
    width: WIDTH,
    height: HEIGHT,
    fonts: [{ name: 'press-start-2p', data: fontData, weight: 400, style: 'normal' }],
  });
  return Buffer.from(new Resvg(svg).render().asPng());
}
