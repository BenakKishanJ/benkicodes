// Guard that keeps the pipeline and admin page out of production builds
// (PRD 02 §8.2). Run after `astro build`; exits non-zero on any violation.
// §7 SE-6..SE-9 and §10 SEO regressions are checked further below.
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
// Thin tag archives self-regulate: they stay noindex below 3 posts (SE-4).
const indexFiles = walk(dist).filter((f) => f.endsWith('.html'));
const isTagPage = (rel) => rel.replaceAll('\\', '/').startsWith('blog/tags/');
if (indexFiles.length === 0) {
  failed.push('dist has no HTML pages');
} else {
  for (const f of indexFiles) {
    const rel = relative(dist, f);
    const html = readFileSync(f, 'utf8');
    const hasNoindex = /<meta name="robots" content="[^"]*noindex/.test(html);
    if (!indexingOn && !hasNoindex) {
      failed.push(`${rel} is missing noindex while staging (PUBLIC_SITE_INDEXING != on)`);
    }
    if (indexingOn && hasNoindex && rel !== '404.html' && !(isTagPage(rel) && postsTagged(html) < 3)) {
      failed.push(`${rel} is noindex while PUBLIC_SITE_INDEXING=on`);
    }
  }
}

// ---------- SE guards (03-prd §10 / 02-prd §7) ----------

// Thin-tag rule re-check: count PostCard-like links on a tag page.
function postsTagged(html) {
  return (html.match(/href="\/blog\/[^"]+"\s+class="card-link"/g) ?? []).length;
}

// 5. Canonical URL on every HTML page (SE-2).
for (const f of indexFiles) {
  const rel = relative(dist, f);
  if (!/rel="canonical"/.test(readFileSync(f, 'utf8'))) {
    failed.push(`SEO: ${rel} has no canonical link`);
  }
}

// 6. Exactly one <h1> per page (SE-1 / Lighthouse SEO).
for (const f of indexFiles) {
  const rel = relative(dist, f);
  const count = (readFileSync(f, 'utf8').match(/<h1[\s>]/g) ?? []).length;
  if (count !== 1) failed.push(`SEO: ${rel} has ${count} <h1> elements (want 1)`);
}

// 7. JSON-LD: only heartbeats we allow, and they must parse (SE-7).
const ALLOWED_TYPES = new Set(['BlogPosting', 'Article', 'BreadcrumbList', 'Person', 'WebSite']);
const FORBIDDEN_TYPES = new Set(['Course', 'FAQPage', 'HowTo']);
const jsonldOk = (html, type) => new RegExp(`"@type"\\s*:\\s*"${type}"`).test(html);
const jsonldPages = { count: 0 };
for (const f of indexFiles) {
  const rel = relative(dist, f);
  const html = readFileSync(f, 'utf8');
  const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  if (blocks.length === 0) {
    // Home carries WebSite via inline? then every content page must still have some.
    jsonldPages[rel] = 0;
    continue;
  }
  jsonldPages[rel] = blocks.length;
  jsonldPages.count += blocks.length;
  for (const [i, block] of blocks.entries()) {
    let ld;
    try {
      ld = JSON.parse(block[1]);
    } catch {
      failed.push(`SEO: ${rel} JSON-LD block ${i + 1} does not parse`);
      continue;
    }
    const items = Array.isArray(ld) ? ld : [ld];
    for (const item of items) {
      if (!item || typeof item !== 'object') continue;
      const t = item['@type'];
      if (FORBIDDEN_TYPES.has(t)) {
        failed.push(`SEO: ${rel} emits forbidden ${t} structured data`);
      }
      if (t && !ALLOWED_TYPES.has(t)) {
        failed.push(`SEO: ${rel} emits unexpected @type ${t}`);
      }
    }
  }
}
// SE-7: posts and parts must carry article markup; all non-home pages breadcrumbs.
for (const f of indexFiles) {
  const rel = relative(dist, f).replaceAll('\\', '/');
  const n = jsonldPages[rel] ?? 0;
  if (rel === 'index.html' || rel === '404.html') continue;
  if (n === 0) failed.push(`SEO: ${rel} has no JSON-LD`);
  if ((rel.startsWith('blog/') && !rel.startsWith('blog/tags/') && !rel.startsWith('blog/index')) || rel.startsWith('roadmaps/') && rel !== 'roadmaps/index.html') {
    const html = readFileSync(f, 'utf8');
    if (!jsonldOk(html, 'BreadcrumbList')) {
      failed.push(`SEO: ${rel} is missing BreadcrumbList JSON-LD`);
    }
    // Course hub + parts carry Article; posts carry BlogPosting.
    if (rel.startsWith('roadmaps/') && rel !== 'roadmaps/index.html') {
      if (!jsonldOk(html, 'Article') && !jsonldOk(html, 'BlogPosting')) {
        failed.push(`SEO: ${rel} is missing Article/BlogPosting JSON-LD`);
      }
    }
  }
}

// 8. Meta descriptions 120-155 chars on frontmatter-driven content pages (SE-1).
for (const f of indexFiles) {
  const rel = relative(dist, f).replaceAll('\\', '/');
  if (!rel.startsWith('blog/') || rel.startsWith('blog/tags/') || rel.includes('_seed')) continue;
  if (rel.startsWith('roadmaps/') && /\/roadmaps\/[^/]+\/?$/.test(rel)) continue; // hub copy is hand-written
  const html = readFileSync(f, 'utf8');
  const m = /<meta name="description" content="([^"]+)"/.exec(html);
  if (!m) {
    failed.push(`SEO: ${rel} has no meta description`);
    continue;
  }
  const len = m[1].length;
  if (len < 120 || len > 155) {
    failed.push(`SEO: ${rel} meta description is ${len} chars (want 120-155)`);
  }
}

// 9. Open Graph image: every page references a real shipped PNG (SE-6).
if (!existsSync(join(dist, 'og-default.png'))) {
  failed.push('SEO: dist/og-default.png is missing');
}
const ogDir = join(dist, 'og');
if (existsSync(ogDir)) {
  for (const f of indexFiles) {
    const rel = relative(dist, f).replaceAll('\\', '/');
    const html = readFileSync(f, 'utf8');
    const og = /<meta property="og:image" content="([^"]+)"/.exec(html)?.[1];
    if (!og) {
      failed.push(`SEO: ${rel} has no og:image`);
      continue;
    }
    const ogRel = og.startsWith('http') ? new URL(og).pathname : og;
    const ogFile = join(dist, ogRel.replace(/^\//, ''));
    if (!existsSync(ogFile)) {
      failed.push(`SEO: ${rel} og:image ${og} is not shipped`);
    }
  }
} else {
  failed.push('SEO: dist/og/ folder is missing (generated OG images did not ship)');
}

// 10. Feeds + sitemap (SE-4/SE-5, indexing builds only: staging ships the same files but a
// noindex site does not publish feeds to the world - they are harmless here).
if (indexingOn) {
  const tree = walk(dist);
  if (!tree.some((p) => p.endsWith('sitemap-index.xml'))) failed.push('SEO: sitemap-index.xml is missing');
  const sitemapPage = tree.find((p) => p.endsWith('sitemap-0.xml') || p.endsWith('sitemap.xml'));
  if (sitemapPage) {
    const xml = readFileSync(sitemapPage, 'utf8');
    if (xml.includes('/blog/tags/')) failed.push('SEO: sitemap lists tag pages');
    if (xml.includes('/admin/')) failed.push('SEO: sitemap lists admin');
    if ((xml.match(/<lastmod>/g) ?? []).length < 3) {
      failed.push('SEO: sitemap carries fewer than 3 lastmod entries');
    }
  } else {
    failed.push('SEO: no sitemap-0.xml/sitemap.xml page file found');
  }
  if (!tree.some((p) => p.endsWith('rss.xml'))) failed.push('SEO: /rss.xml is missing');
  if (!tree.some((p) => p.endsWith(join('roadmaps', 'rss.xml')))) failed.push('SEO: /roadmaps/rss.xml is missing');
}

if (failed.length) {
  console.error(`check-dist: ${failed.length} problem(s):`);
  for (const m of failed) console.error(`  - ${m}`);
  process.exit(1);
}
console.log(`check-dist: ${indexFiles.length} pages OK (indexing: ${indexingOn ? 'on' : 'off'})`);
