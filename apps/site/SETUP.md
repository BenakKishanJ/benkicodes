# BenKi Codes: Kanagawa pixel redesign

Astro 7 + Tailwind 4 + React islands. Requires **Node >= 22.23.4**.

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # static output in dist/
```

## What changed vs. the previous version
Folder structure, routes, content collections/schemas, progress storage and the RSS/sitemap/JSON-LD setup are unchanged,
so the content pipeline keeps working. Everything visual was rebuilt.

| Area | Where |
|---|---|
| Palettes (wave / dragon / lotus), tones, all component CSS, animations | `src/styles/global.css` |
| Theme registry (JS side) | `src/lib/themes.ts` |
| Pixel sprites (icons, BK logo) | `src/lib/sprites.ts` |
| Procedural pixel art (hero art, post covers, dissolve edges) | `src/lib/art.ts` |
| Pixel effects (wipe transition, dissolve, confetti, sparks) | `src/scripts/pixelfx.ts` |
| Page behaviour (reveal, parallax, section dots, mobile menu) | `src/scripts/fx.ts` |
| Pixel components | `src/components/pixel/` (was `rice/`) |
| Cursor SVGs, favicon | `public/cursors/`, `public/favicon.svg` |

## Design system
- **Fonts**: Press Start 2P (headings), Martian Mono (body), JetBrains Mono (code). All self-hosted via Fontsource.
- **Themes**: `wave` (default), `dragon`, `lotus`. Official Kanagawa colours. Code blocks use Shiki's matching `kanagawa-*` themes.
- **Tones**: every section is `tone-a` or `tone-b` and pages alternate them (dark/light in wave and dragon, light/dark in lotus).
  Between sections, `<PixelEdge to="a|b" />` draws the pixel-dither dissolve.
- **Snap scrolling**: `<BaseLayout snap="mandatory | proximity | none">`. Mandatory is used on home, roadmaps and about.
  Mobile always falls back to proximity. Sections that should fill the screen use `sec-full`.
- **Parallax**: add `data-parallax="0.1"` (vertical) or `data-parallax-x="0.1"` (horizontal). Movement snaps to a 4px grid.
- **Reveal**: add `data-reveal` for the stepped pop-in. Siblings stagger automatically.
- **Section dots**: any element with `data-title="..."` appears in the right-hand section dots (desktop).

## Replacing the placeholder hero art
Drop PNGs into `public/art/` named `hero-wave.png`, `hero-dragon.png`, `hero-lotus.png`.
`HeroArt.astro` detects them at build time and uses them instead of the generated SVG.
Post covers: set `cover: { src, alt }` in a post's frontmatter to replace the generated cover.

## Effects
Everything is on by default. Users can turn effects off with the "fx" button in the footer or the command palette (Ctrl K);
`prefers-reduced-motion` also disables all motion. To soften things later, the main knobs are the `data-parallax` values,
the `wipeCover()` durations in `pixelfx.ts`, and the keyframes at the bottom of `global.css`.

## Custom cursor
`public/cursors/arrow.svg` and `pointer.svg`, applied in `global.css` under `@media (pointer: fine)`. Touch devices keep the native cursor.

## Still to do before launch
Replace the TODO author details in `src/site.config.ts` and `src/pages/about.astro`, add `public/og-default.png`,
and review `src/pages/privacy.astro` against the services you enable.
