// Prunes build artifacts that belong to the dev-only admin suite and are not
// referenced by anything that ships (PRD 02 §8.2). Runs BEFORE check-dist.mjs:
// if a forbidden-string file IS referenced by live output, it is left in place
// and check-dist fails the build, keeping the guard a real backstop.
import { readdirSync, readFileSync, statSync, existsSync, unlinkSync, rmSync } from 'node:fs';
import { join, relative } from 'node:path';

const dist = new URL('../dist/', import.meta.url).pathname;
const ADMIN_STRINGS = ['X-Admin-Token', '127.0.0.1:8787', 'localhost:8787'];

const walk = (dir) => {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
};
const readable = (p) => {
  try {
    if (statSync(p).size > 5 * 1024 * 1024) return null;
    return readFileSync(p, 'utf8');
  } catch { return null; }
};

if (!existsSync(dist)) process.exit(0);

// 1. an admin/ directory is never wanted in dist, referenced or not
const adminDir = join(dist, 'admin');
if (existsSync(adminDir)) {
  rmSync(adminDir, { recursive: true, force: true });
  console.log('prune-admin: removed dist/admin');
}

const files = walk(dist);
// 2. orphaned bundles: contain admin strings and no other shipped file links them
for (const f of files.filter((p) => p.endsWith('.js'))) {
  const text = readable(f);
  if (!text || !ADMIN_STRINGS.some((s) => text.includes(s))) continue;
  const name = f.split('/').pop();
  const referenced = files.some((o) => {
    if (o === f) return false;
    const t = readable(o);
    return t ? t.includes(name) : false;
  });
  if (referenced) continue; // live graph -> let check-dist fail loudly
  unlinkSync(f);
  console.log(`prune-admin: removed unreferenced admin bundle ${relative(dist, f)}`);
}
