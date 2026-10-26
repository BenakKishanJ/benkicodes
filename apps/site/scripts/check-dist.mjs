// Guard that keeps the pipeline and admin page out of production builds
// (PRD 02 §8.2). Run after `astro build`; exits non-zero on any violation.
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

const dist = new URL('../dist/', import.meta.url).pathname;
const failed = [];

const walk = (dir) => {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
};

// 1. The admin route and pipeline API must not be shipped.
if (existsSync(join(dist, 'admin'))) {
  failed.push('dist/admin exists - the admin route leaked into this build');
}

const FORBIDDEN_STRINGS = ['X-Admin-Token', '127.0.0.1:8787', 'localhost:8787'];

// 2. No shipped file may reference the admin token or the pipeline API.
for (const file of walk(dist)) {
  if (statSync(file).size > 5 * 1024 * 1024) continue; // images aren't scanned
  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch {
    continue; // binary
  }
  for (const needle of FORBIDDEN_STRINGS) {
    if (text.includes(needle)) {
      failed.push(`${relative(dist, file)} contains forbidden string "${needle}"`);
    }
  }
}

// 3. robots.txt must match the PUBLIC_SITE_INDEXING state for this build.
const robots = readFileSync(join(dist, 'robots.txt'), 'utf8');
const indexingOn = process.env.PUBLIC_SITE_INDEXING === 'on';
if (indexingOn) {
  if (/Disallow:\s*\/\s*$/m.test(robots) || !/Sitemap:/.test(robots)) {
    failed.push('PUBLIC_SITE_INDEXING=on but robots.txt does not allow crawling with a Sitemap line');
  }
} else if (!/Disallow:\s*\/\s*(\n|$)/.test(robots)) {
  failed.push('PUBLIC_SITE_INDEXING is not "on" but robots.txt does not Disallow: /');
}

// 4. Every page in dist must carry the robots meta consistent with the flag.
const indexFiles = walk(dist).filter((f) => f.endsWith('.html'));
if (indexFiles.length === 0) {
  failed.push('dist has no HTML pages');
} else {
  for (const f of indexFiles) {
    const rel = relative(dist, f);
    const html = readFileSync(f, 'utf8');
    const hasNoindex = /<meta name="robots" content="[^"]*noindex/.test(html);
    if (indexingOn && hasNoindex && rel !== '404.html') {
      failed.push(`${rel} is noindex while PUBLIC_SITE_INDEXING=on`);
    }
    if (!indexingOn && !hasNoindex) {
      failed.push(`${rel} is missing noindex while staging (PUBLIC_SITE_INDEXING != on)`);
    }
  }
}

if (failed.length) {
  console.error(`check-dist: ${failed.length} problem(s):`);
  for (const m of failed) console.error(`  - ${m}`);
  process.exit(1);
}
console.log(`check-dist: ${indexFiles.length} pages OK (indexing: ${indexingOn ? 'on' : 'off'})`);
