// Config-time scan of content frontmatter so the sitemap can carry an
// accurate per-page `lastmod` (PRD 02 §7 SE-4: lastReviewed/updatedDate).
// Astro config cannot import TS content modules, so frontmatter is parsed
// with a bounded regex instead — values are plain `2026-11-07` dates.

import { readdirSync, readFileSync } from 'node:fs';
import { join, basename, extname, sep } from 'node:path';

const ROOT = new URL('./src/content/', import.meta.url).pathname;

/** Returns a Map: content URL path (trailing slash) -> ISO date (YYYY-MM-DD). */
export function buildLastmodMap() {
  const map = new Map();
  const walk = (dir, rel = '') => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      if (e.name.startsWith('_seed')) continue; // template content, not shipped
      const relPath = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) walk(join(dir, e.name), relPath);
      else if (/\.(md|mdx)$/.test(e.name)) scan(join(dir, e.name), relPath, map);
    }
  };
  walk(ROOT);
  return map;
}

function dateOrUndefined(raw) {
  if (!raw) return undefined;
  const d = new Date(raw);
  return Number.isNaN(d.valueOf()) ? undefined : d.toISOString().slice(0, 10);
}

function scan(file, relPath, map) {
  const text = readFileSync(file, 'utf8');
  if (!text.startsWith('---')) return;
  const end = text.indexOf('\n---');
  if (end === -1) return;
  const fm = text.slice(3, end);
  if (/^\s*draft:\s*true/m.test(fm)) return; // drafts stay unlisted (SE-4)
  // The publish flow emits YAML anchors (`pubDate: &id001 2026-10-28`,
  // `lastReviewed: *id001`) - resolve them before reading the date.
  const anchors = new Map();
  for (const m of fm.matchAll(/(?:^|\n)[^:\n]+:\s*&([\w.]+)\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/g)) {
    anchors.set(m[1], m[2]);
  }
  const resolve = (raw) => {
    if (!raw) return undefined;
    if (raw.startsWith('&')) return dateOrUndefined(raw.slice(1).trim());
    if (raw.startsWith('*')) return dateOrUndefined(anchors.get(raw.slice(1).trim()));
    return dateOrUndefined(raw);
  };
  const value = (key) => new RegExp(`(?:^|\n)${key}:\\s*(\\S+)`).exec(fm)?.[1];
  const lastmod = resolve(value('updatedDate')) ?? resolve(value('lastReviewed'));
  if (!lastmod) return;
  map.set(pathFor(relPath), lastmod);
}

/** Content file path -> public URL path (trailing slash, PRD URL shape). */
export function pathFor(relPath) {
  const ext = extname(relPath);
  const parts = relPath.split(sep).map((p) => basename(p, ext));
  const isIndex = parts[parts.length - 1] === 'index';
  // blog/<slug>.md        -> /blog/<slug>/
  // roadmaps/<slug>/index -> /roadmaps/<slug>/
  // roadmaps/<slug>/modules/<m>.md -> /roadmaps/<slug>/<m>/
  if (parts[0] === 'blog' && !isIndex) return `/blog/${parts[1]}/`;
  if (parts[0] === 'roadmaps') {
    if (isIndex) return `/roadmaps/${parts[1]}/`;
    const moduleParts = parts.slice(2);
    const last = moduleParts[moduleParts.length - 1];
    return `/roadmaps/${parts[1]}/${last}/`;
  }
  return null;
}
