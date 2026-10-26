# 02. PRD: The Site (Astro, in the pnpm monorepo)

**Version:** 2.0 · **Date:** 26 Oct 2026 · **Owner:** Ben · **Status:** Draft for review
**Companions:** `01-marketing-seo-strategy.md`, `03-prd-content-pipeline.md`
**Builds on:** the delivered Astro site (themes, pixel-art backdrops, home and about scroll stories, blog, roadmaps with quizzes, command palette, dev-only admin page v1)

---

## 1. Overview

### 1.1 Purpose
The public face of the project: a fast, distinctive, SEO-ready static site that hosts **blog posts** and **hands-on roadmaps**. A roadmap is a guided project: each part (module) is a lesson plus exercises and a short quiz, tied to a tagged commit in a public GitHub repository. Content arrives as Markdown from the local pipeline and goes live when it is committed to `main`.

### 1.2 Decisions this PRD is built on

| Topic | Decision |
|---|---|
| Workspace | pnpm workspace in one git repo: `apps/site`, `apps/pipeline`, `packages/content-schema` |
| Hosting | GitHub → Cloudflare Pages (Git integration). The site is plain static output |
| Staging then launch | Deploy early to a `pages.dev` URL with `noindex`. Public launch flips indexing on and attaches the domain |
| Admin page | `/admin/` exists in `pnpm dev` only. It is never in a production build |
| Roadmaps | Hands-on: guided project, one module at a time, live as each is approved. Unfinished modules are not in the repo |
| Code in lessons | Comes from the project repo at a Git tag, linked by GitHub URLs. Never invented |
| Launch content | 1 flagship roadmap (6 parts) + 4 to 5 blog posts |
| Monetization | Off at launch. The ads flag stays in the config |

### 1.3 Goals

| # | Goal | Measure |
|---|---|---|
| G1 | A reader can follow a roadmap end to end with the repo | Every part shows start tag, end tag, commit list and a compare link |
| G2 | Eligible for Google Search and Discover | Passes the SEO checklist in §7 and `01` §7.1 |
| G3 | Fast | Lighthouse ≥ 90 mobile, ≥ 95 desktop on key pages |
| G4 | One content contract | Site and pipeline validate against the same schema package |
| G5 | Frictionless publishing | A pipeline commit to `main` becomes a live page in about a minute |
| G6 | Portable and sellable | Brand, ads, analytics and indexing are config flags |

### 1.4 Non-goals (this version)
Accounts, comments, server-side code, certificates, a code-submission system, a CLI verifier, multi-language, a paywall, search backed by a server (client-side Pagefind is P1).

### 1.5 Personas
Switcher Sam (developer learning agents), Fresher Fiona (student wanting a portfolio project), recruiters reading About, Projects and the repo. See `01` §2.

---

## 2. Workspace and repository

### 2.1 Layout (site-relevant part)

```
benki/                                   # git root, hosted on GitHub
├─ pnpm-workspace.yaml                   # packages: ["apps/*", "packages/*"]
├─ package.json                          # root scripts, packageManager pin, engines
├─ pnpm-lock.yaml
├─ .github/workflows/
│  ├─ site-ci.yml                        # schema, check, build, link check, admin-not-shipped guard
│  └─ pipeline-ci.yml                    # pytest (see 03)
├─ packages/
│  └─ content-schema/
│     ├─ package.json                    # name: @benki/content-schema
│     ├─ src/ blog.ts roadmap.ts module.ts project.ts index.ts
│     └─ scripts/emit-json-schema.ts     # writes dist/*.schema.json for Python
└─ apps/
   ├─ site/                              # THIS DOCUMENT (full tree in §11)
   └─ pipeline/                          # see 03
```

### 2.2 Tooling
- Node ≥ 22.23.4 (required by Astro 7.4), pnpm pinned via the `packageManager` field and Corepack. Python and uv are only for `apps/pipeline`.
- `packages/content-schema` is the single source of truth for frontmatter. The site's `content.config.ts` imports it. A script emits JSON Schema (Zod 4's `z.toJSONSchema`) that the pipeline validates against.

### 2.3 Root scripts

| Script | Does |
|---|---|
| `pnpm setup` | `pnpm install` + `pnpm --filter pipeline setup` (uv sync) |
| `pnpm dev` | Runs the Astro dev server (`:4321`) and the pipeline API (`:8787`) in parallel |
| `pnpm dev:site` | Site only |
| `pnpm schema` | Builds the schema package and emits JSON Schema |
| `pnpm build` | `pnpm schema && pnpm --filter site build` (what Cloudflare runs) |
| `pnpm check` | `astro check` + schema tests |
| `pnpm test` | All workspace tests |

---

## 3. Information architecture and URLs

```
/                                   Home (scroll story)
/about/                             About (scroll story)
/projects/   /projects/<slug>/      Portfolio projects (hand-written)
/blog/       /blog/page/<n>/        Index (paginated); /blog/<slug>/ posts; /blog/tags/<tag>/
/roadmaps/                          Roadmap index
/roadmaps/<course>/                 Course hub: overview, project panel, parts list, progress
/roadmaps/<course>/<part>/          A part: lesson, code panel, exercises, resources, quiz
/editorial-policy/  /privacy/  /contact/  /terms/
/rss.xml            /roadmaps/rss.xml
/sitemap-index.xml  /robots.txt  /og/<...>.png
/404
/admin/                             DEV ONLY (not built for production)
```

URL rules: lowercase, no dates, stable slugs. A published slug is never changed without a 301 in `public/_redirects`.

---

## 4. Functional requirements

Priority: **P0** launch blocker · **P1** launch target · **P2** later.

### 4.1 Global shell (delivered, with changes)

| ID | Requirement | Pri | Status |
|---|---|---|---|
| GL-1 | Fluid, full-width responsive layout (rem-based scale) | P0 | Delivered |
| GL-2 | 4 theme families × light/dark, pixel-art backdrop per theme, no flash on load | P0 | Delivered |
| GL-3 | Header, status-bar footer, theme and effects menu, command palette | P0 | Delivered |
| GL-4 | Reduced-motion and "effects off" respected everywhere | P0 | Delivered |
| GL-5 | Indexing toggle: `PUBLIC_SITE_INDEXING` (`on`/`off`) controls the robots meta tag and `robots.txt` | P0 | **New** |
| GL-6 | Cookie consent banner, shown only when ads or non-essential cookies are enabled | P1 | New |
| GL-7 | Skip link, visible focus, keyboard-operable menus | P0 | Delivered |

### 4.2 Home and About (delivered)
Scroll stories with the workspace rail. **Changes:** the home page features the flagship course as the primary call to action; the roadmaps section shows the course's latest published parts; the About page uses real copy (no TODO text) and links to GitHub and the course repo.

### 4.3 Blog

| ID | Requirement | Pri |
|---|---|---|
| BL-1 | Index with featured post, tag chips (links to tag pages), pagination | P0 |
| BL-2 | Post: title, author, published and **last reviewed** dates, reading time, tags, TOC, body, **Sources**, AI-assistance disclosure, related posts, report-an-error link | P0 |
| BL-3 | Code blocks with language and copy button; optional filename caption | P0 |
| BL-4 | **Link to the course part** the post supports (frontmatter `relatedPart`) shown as a callout under the intro | P1 |
| BL-5 | Breadcrumbs and `BlogPosting` + `BreadcrumbList` JSON-LD | P0 |
| BL-6 | RSS feed | P0 |
| BL-7 | Draft posts excluded from production | P0 |
| BL-8 | Thin tag pages (<3 posts) are `noindex, follow` | P1 |

### 4.4 Roadmaps (hands-on)

**Course hub (`/roadmaps/<course>/`)**

| ID | Requirement | Pri |
|---|---|---|
| RM-1 | Header: title, description, level, estimated hours, version, last reviewed, status (`in-progress` or `complete`) | P0 |
| RM-2 | **Project panel:** what you will build, prerequisites, repo link, "Use this template" link (if enabled), how to follow along (clone, check out a tag, compare), license | P0 |
| RM-3 | Parts list as the git-graph timeline with local progress; planned-but-unpublished parts shown locked as "coming soon" | P0 |
| RM-4 | **Inspired by** box: courses, roadmaps and articles that shaped the structure, each with a link and a short note | P0 |
| RM-5 | Progress saved in the browser; export and import as JSON | P1 |
| RM-6 | `Article` JSON-LD for the hub page and `BreadcrumbList`. No `Course` rich-result markup (retired by Google in 2025) | P0 |

**A part (`/roadmaps/<course>/<part>/`)**

| ID | Requirement | Pri |
|---|---|---|
| RM-10 | Objectives box, "what we add in this part", estimated time, last reviewed | P0 |
| RM-11 | Lesson body (Markdown). Code snippets are static text with a caption linking to the exact file and lines at the part's tag | P0 |
| RM-12 | **Code panel:** start tag and end tag, the commit list with links, a **Compare on GitHub** link, a copy-able `git checkout part-N` snippet, list of changed files | P0 |
| RM-13 | **Exercises** (FSO style): numbered, each with a goal, acceptance criteria and collapsed hints | P0 |
| RM-14 | **Resources:** curated links with a one-line reason, a type tag, and an "illustrated" badge where applicable | P0 |
| RM-15 | **Sources:** numbered citations to official docs used for the lesson | P0 |
| RM-16 | Concept quiz (4 to 6 questions) with explanations; pass threshold 70%; result saved locally | P0 |
| RM-17 | Previous and next part navigation; sticky part list and TOC on wide screens; reading-progress bar | P0 |
| RM-18 | `Article` + `BreadcrumbList` JSON-LD | P0 |

### 4.5 Projects (portfolio)
Index and detail pages for your own projects (hand-written). Includes the course project as a featured entry that links to the course and repo. P0.

### 4.6 Search
Client-side search with Pagefind over blog, parts and projects, integrated with the command palette. P1. (The delivered palette already searches titles.)

### 4.7 Trust pages
Editorial policy, Privacy, Contact, Terms/disclaimer, 404. Real content, no placeholders. P0.

### 4.8 Monetization and analytics

| ID | Requirement | Pri |
|---|---|---|
| MN-1 | `ads.enabled` flag controls all ad scripts and slots; default off; ad slots reserve height | P1 |
| MN-2 | Analytics: Cloudflare Web Analytics via a token in config; off when empty | P1 |
| MN-3 | Affiliate link component with automatic disclosure | P2 |
| MN-4 | Newsletter: RSS now; form action configurable later | P2 |

---

## 5. Content model (`packages/content-schema`)

All schemas below live in the shared package. The pipeline validates its output against the generated JSON Schema before it writes a file.

### 5.1 Blog

```ts
// packages/content-schema/src/blog.ts
export const source = z.object({
  title: z.string(), url: z.url(), publisher: z.string().optional(), accessed: z.coerce.date().optional(),
});
export const blog = z.object({
  title: z.string().max(70),
  description: z.string().min(70).max(160),
  pubDate: z.coerce.date(),
  updatedDate: z.coerce.date().optional(),
  lastReviewed: z.coerce.date(),
  tags: z.array(z.string()).min(1).max(6),
  category: z.enum(['news', 'guide', 'tutorial', 'opinion', 'tooling']),
  cover: z.object({ src: z.string(), alt: z.string() }).optional(),
  relatedPart: z.object({ course: z.string(), part: z.string() }).optional(),   // NEW: links post to a course part
  draft: z.boolean().default(false),
  featured: z.boolean().default(false),
  sources: z.array(source).min(1),
  aiAssisted: z.boolean().default(true),
  reviewedBy: z.string().default('Ben'),
  pipelineRunId: z.string().optional(),
  canonical: z.url().optional(),
});
```

### 5.2 Roadmap (course) index

```ts
const gh = z.url().refine((u) => u.startsWith('https://github.com/'), 'must be a GitHub URL');
export const roadmap = z.object({
  title: z.string(), description: z.string().max(160),
  level: z.enum(['beginner', 'intermediate', 'advanced']),
  estimatedHours: z.number(),
  prerequisites: z.array(z.string()).default([]),
  outcomes: z.array(z.string()).min(3),
  tags: z.array(z.string()).default([]),
  status: z.enum(['in-progress', 'complete']).default('in-progress'),       // NEW
  planned: z.array(z.object({ slug: z.string(), title: z.string(), estimatedMinutes: z.number() })).default([]),  // NEW: coming soon
  project: z.object({                                                       // NEW: the guided project
    repo: gh,                       // https://github.com/<user>/<repo>
    defaultBranch: z.string().default('main'),
    template: z.boolean().default(false),
    license: z.string().optional(),
    stack: z.array(z.string()).default([]),
    summary: z.string().max(240),   // what you will build
  }),
  inspiredBy: z.array(z.object({ title: z.string(), url: z.url(), author: z.string().optional(), note: z.string().optional() })).default([]),
  lastReviewed: z.coerce.date(), version: z.string().default('1.0'),
  draft: z.boolean().default(false), featured: z.boolean().default(false),
  pipelineRunId: z.string().optional(),
});
```

### 5.3 Module (part)

```ts
export const resource = z.object({
  title: z.string(), url: z.url(),
  type: z.enum(['docs', 'video', 'article', 'repo', 'interactive', 'book']),
  why: z.string().max(200),                        // NEW: one-line reason, written by the pipeline
  illustrated: z.boolean().default(false),         // NEW
});
export const module = z.object({
  title: z.string(), order: z.number(), estimatedMinutes: z.number(),
  objectives: z.array(z.string()).min(2),
  sources: z.array(source).min(1),                 // NEW: official docs cited in the lesson
  resources: z.array(resource).default([]),
  code: z.object({                                 // NEW: ties the lesson to the project repo
    startTag: z.string(), endTag: z.string(),
    compareUrl: gh, treeUrl: gh,
    commits: z.array(z.object({ sha: z.string().min(7), message: z.string(), url: gh })).min(1),
    files: z.array(z.string()),
  }),
  quiz: z.array(quizQuestion).min(3),
  lastReviewed: z.coerce.date(), draft: z.boolean().default(false),
  pipelineRunId: z.string().optional(),
});
```

### 5.4 Body conventions (authoring contract)
- Lessons are Markdown. Allowed raw HTML is limited to `<details>` and `<summary>` (for hints). The pipeline lints everything else out.
- **Code snippets** are fenced code blocks followed by a one-line caption in italics: `*From [`src/agent/graph.py` L10 to L34 at `part-2`](https://github.com/<user>/<repo>/blob/part-2/src/agent/graph.py#L10-L34)*`. The site styles an italic-only paragraph directly after a code block as a caption (CSS `:has`).
- **Exercises** use a fixed shape so the site can style them:

```markdown
## Exercises

### Exercise 2.1: Add a fetch tool
**Goal:** one sentence.

**Acceptance criteria**
- criterion
- criterion

<details><summary>Hint 1</summary>

hint text

</details>
```
- Inline citations are numbered links to the Sources list (`[[1]](#sources-h)`), produced by the pipeline.

---

## 6. Design system (delivered, summary)
Four theme families (Kanagawa, Tokyo Night, Rosé Pine, Gruvbox) with light and dark variants, a generated pixel-art parallax backdrop per theme, JetBrains Mono everywhere, Pixelify Sans for headings, glass panes on home and about, **calm solid panels on reading pages**, fluid rem-based scale, scroll-driven reveals on home and about only. **Additions for roadmaps:** styles for the project panel, code panel, exercise blocks (`h3` starting "Exercise"), `<details>` hints, code captions, and locked "coming soon" parts in the git-graph.

---

## 7. SEO implementation (site side)

Strategy is in `01` §5. This section lists what the site must implement.

| ID | Requirement | Pri |
|---|---|---|
| SE-1 | Unique `<title>` (≈60 chars) and meta description (120 to 155) per page from frontmatter | P0 |
| SE-2 | Canonical URL on every page; `frontmatter.canonical` overrides | P0 |
| SE-3 | **Indexing toggle** (`PUBLIC_SITE_INDEXING`): off → `noindex` meta on every page and `Disallow: /` in robots.txt; on → normal, with `Sitemap:` line | P0 |
| SE-4 | `sitemap-index.xml` with accurate `lastmod` (from `lastReviewed`/`updatedDate`); excludes drafts, `/admin/`, and thin tag pages | P0 |
| SE-5 | RSS: `/rss.xml` (posts) and `/roadmaps/rss.xml` (published parts) with auto-discovery links | P0 |
| SE-6 | Open Graph and Twitter cards with a **generated 1200×630 image per page** (build-time, Satori + resvg) and `max-image-preview:large` robots directive | P1 |
| SE-7 | JSON-LD (visible-content only): `BlogPosting` (posts), `Article` (course hub and parts), `BreadcrumbList` (all non-home pages), `Person` (author, About), `WebSite` (home). **No** `Course`, `FAQPage` or `HowTo` markup | P0 |
| SE-8 | Breadcrumb navigation component on blog, roadmap and part pages | P0 |
| SE-9 | Internal linking: related posts, part ↔ part navigation, post → part callout, part → related posts, course ↔ repo | P0 |
| SE-10 | Semantic HTML (`article`, `nav`, `main`, `time`), one H1, heading order, descriptive link text | P0 |
| SE-11 | Images: alt text required, width/height set, modern formats, lazy below the fold | P0 |
| SE-12 | `_redirects` for any changed slug; clean 404 that is `noindex` | P0 |
| SE-13 | Security and cache headers in `_headers` (hashed assets cached long-term) | P0 |
| SE-14 | Core Web Vitals budgets (see §10), enforced in CI | P1 |

`lib/seo.ts` exposes `buildMeta()`, `articleJsonLd()`, `breadcrumbJsonLd()`, and `personJsonLd()`. `BaseLayout.astro` is the only place that emits head tags.

---

## 8. Admin page (dev-only, works with the local pipeline)

### 8.1 How it fits
`/admin/` is a React island in the same Astro dev server. It talks to the pipeline API at `http://127.0.0.1:8787` with an `X-Admin-Token` header. It exists only when `import.meta.env.DEV` is true.

```
getStaticPaths() { return import.meta.env.DEV ? [{ params: { slug: undefined } }] : []; }
```

### 8.2 Guards that keep it out of production
1. The route returns no paths in production builds.
2. `scripts/check-dist.mjs` (run by `site-ci.yml` and by `pnpm build`) fails if `dist/admin` exists, if any file contains the string `X-Admin-Token`, or if any bundle contains the pipeline API base URL.
3. Admin components are imported only from the admin route, so they are tree-shaken out of production bundles.

### 8.3 Screens (lean; full behaviour and API in `03` §9)

| Screen | Purpose |
|---|---|
| Connect | Token and API address; environment checks from the API |
| Runs | List of blog runs and courses with status; **New blog**, **New course** |
| Blog review | Activity, tabs (Draft, Sources, Checks, Diff, Metadata), approve, request changes, reject |
| Course workspace | Plan review (references, modules), per-part stepper: **Code → Lesson → Publish** |
| Code review | Commit list, diffs, run tests, ask the agent for changes, accept |
| Lesson review | Rendered lesson, exercises, quiz, resources, sources, checks, approve |
| Settings | Models per task, budgets, paths, publish mode |
| Library | Read-only list of what is published, with commit ids |

Idea scouts (blog and course) arrive after launch (`03` §8).

### 8.3.1 Files

```
apps/site/src/components/admin/
  api.ts  types.ts
  PipelineConsole.tsx          # shell: connect, nav, polling/SSE
  runs/RunList.tsx  NewBlogForm.tsx  NewCourseForm.tsx
  blog/BlogReview.tsx          # extends delivered RunDetail
  course/CoursePlan.tsx  ModuleWorkspace.tsx  CodeReview.tsx  DiffView.tsx  LessonReview.tsx  PublishPanel.tsx
  settings/Settings.tsx  ModelPicker.tsx
  library/Library.tsx
```

### 8.4 UX rules
- A persistent strip shows API status, today's spend, and the publish mode, so it is always clear what **Approve** does (for example "commits to `main` and pushes tag part-3").
- Destructive actions confirm. Publishing always shows the exact files, commit message, tag and live URLs.
- Every error shows the cause and a retry.
- Keyboard accessible; follows the site's themes; no secrets stored beyond the token in local storage.

---

## 9. Deployment: GitHub and Cloudflare Pages

### 9.1 The flow

```
 Local: pnpm dev
   admin page ──▶ pipeline ──▶ git worktree ──commit──▶ origin/main (GitHub)
                                                          │
                                  Cloudflare Pages (Git integration) watches main
                                                          │  build: pnpm build  → apps/site/dist
                                                          ▼
                                  live site (staging URL, later custom domain)
```
- A failed Cloudflare build does not replace the live site; the previous deployment keeps serving.
- The pipeline validates content against the schema **before** it commits, so a schema-breaking commit should not reach `main`. CI is the second safety net.

### 9.2 Cloudflare Pages project settings (new project, separate from the old blog)

| Setting | Value |
|---|---|
| Git repository | `<user>/benki` (the monorepo) |
| Production branch | `main` |
| Root directory | repository root |
| Build command | `pnpm build` |
| Build output directory | `apps/site/dist` |
| Environment variables | `NODE_VERSION` (≥ 22.23.4, for example 24), `PUBLIC_SITE_INDEXING=off` for now, `PUBLIC_SITE_URL`, optional analytics token *(verify build-image Node versions)* |
| Build watch paths | **Include** `apps/site/*`, `packages/*`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `package.json`. **Exclude** `apps/pipeline/*` |
| Preview deployments | Enabled for non-production branches. The pipeline only ever pushes to `main`; your own feature branches get preview URLs |
| Custom domain | Added at launch; HTTPS automatic |

By default every push to a connected repository triggers a build, which is why the watch paths matter in a monorepo. Monorepo support needs Cloudflare's build system v2 or later *(it is the default for new projects; verify)*.

### 9.3 Staging → launch

| Step | Action |
|---|---|
| 1 | Create the Pages project; set `PUBLIC_SITE_INDEXING=off`; confirm the pipeline's first approve deploys |
| 2 | Produce launch content on staging (not indexed, not announced) |
| 3 | Run the launch checklist (`01` §7.1) |
| 4 | Attach the custom domain; set `PUBLIC_SITE_INDEXING=on` for production; redeploy |
| 5 | Verify in Search Console and Bing; submit the sitemap; request indexing for key pages |
| 6 | Switch the old `benkicodes.pages.dev` site to redirect or retire it |

### 9.4 GitHub Actions (`site-ci.yml`)
On pull requests and pushes: `corepack enable`, `pnpm install --frozen-lockfile`, `pnpm schema`, `pnpm check`, `pnpm build`, `node scripts/check-dist.mjs`, internal and external link check on `dist` (lychee), and optional Lighthouse CI against a static server on `dist`. Content-only commits from the pipeline run the same jobs.

### 9.5 Branching and rollback
- `main` is the deploy branch. Pipeline commits are small, labelled `content:`, and touch only content paths.
- Roll back by reverting the commit (the admin Library can do this) or using Cloudflare's deployment rollback.
- Course repo tags are immutable once pushed; corrections are new commits.

---

## 10. Performance, accessibility, privacy

**Performance budgets (mobile, 4G):** LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1; JS per reading page (excluding ads) ≤ ~60 KB gzipped; two font families; hero shader only on home. Reading pages use no shader and no backdrop-filter.

**Accessibility:** WCAG 2.2 AA target; every theme passes contrast checks; quiz and palette are keyboard-operable with proper roles; code captions and exercise blocks are real headings and lists.

**Privacy:** the browser stores only theme, effects preference, quiz progress and the dev-only admin token. No third-party scripts unless ads or analytics are enabled.

---

## 11. Folder and file structure (`apps/site`)

Legend: **D** delivered · **C** changed · **N** new

```
apps/site/
├─ package.json                              C  (name: "site"; imports @benki/content-schema)
├─ astro.config.mjs                          C  (site URL from env; sitemap filter + lastmod)
├─ tsconfig.json
├─ public/
│  ├─ favicon.svg  D
│  ├─ art/<theme>/{sky,far,mid,near}.png     D
│  ├─ _headers                               C  (cache + security headers)
│  ├─ _redirects                             N
│  └─ fonts/ (OG-image font files)           N
├─ scripts/
│  └─ check-dist.mjs                         N  (admin-not-shipped guard)
├─ tools/                                    D  (pixel-art generator)
└─ src/
   ├─ content/
   │  ├─ blog/*.md
   │  ├─ roadmaps/<course>/index.md
   │  ├─ roadmaps/<course>/modules/*.md
   │  └─ projects/*.md
   ├─ content.config.ts                      C  (re-exports from @benki/content-schema)
   ├─ site.config.ts                         C  (indexing flag, repo links)
   ├─ lib/
   │  ├─ content.ts  utils.ts  themes.ts  progress.ts   D
   │  ├─ seo.ts                              N  (meta + JSON-LD builders)
   │  └─ github.ts                           N  (blob/compare URL helpers, caption parsing)
   ├─ scripts/ theme.ts  hero-fx.ts          D
   ├─ styles/ global.css  art.css            C  (+ exercise, caption, details, panel styles)
   ├─ layouts/BaseLayout.astro               C  (indexing toggle, canonical, OG, JSON-LD)
   ├─ components/
   │  ├─ layout/ Header Footer ThemeSwitcher CommandPalette WorkspaceRail Backdrop   D
   │  ├─ rice/ TerminalWindow Mascot HeroDesktop                                   D
   │  ├─ content/ PostCard TOC SourcesList Callout                                 D
   │  ├─ content/ Breadcrumbs  SeriesNav  RelatedPosts  PartCallout                N
   │  ├─ roadmap/ ProjectPanel  CodePanel  ResourcesList  InspiredBy  PlannedParts N
   │  ├─ learning/ Quiz RoadmapProgress ProgressRing                               D
   │  ├─ ads/ AdSlot                                                               D
   │  └─ admin/ …                                                                  C (see §8.3.1)
   └─ pages/
      ├─ index.astro about.astro 404.astro editorial-policy.astro privacy.astro    C
      ├─ contact.astro  terms.astro                                                N
      ├─ blog/[...page].astro  blog/[slug].astro  blog/tags/[tag].astro            C
      ├─ roadmaps/index.astro  roadmaps/[roadmap]/index.astro  …/[module].astro    C
      ├─ projects/index.astro  projects/[slug].astro                               D
      ├─ rss.xml.ts                                                                D
      ├─ roadmaps/rss.xml.ts                                                       N
      ├─ robots.txt.ts                                                             N  (indexing toggle)
      ├─ og/[...slug].png.ts                                                       N  (Satori + resvg)
      └─ admin/[...slug].astro                                                     D
```

### 11.1 Concrete changes to the delivered site
1. Remove the `Course` JSON-LD from the roadmap hub; use `Article` + `BreadcrumbList`.
2. Replace the static `public/robots.txt` with `robots.txt.ts` driven by `PUBLIC_SITE_INDEXING`.
3. Move schemas into `packages/content-schema`; extend roadmap and module schemas (§5).
4. Add `ProjectPanel`, `CodePanel`, `ResourcesList`, `InspiredBy`, `PlannedParts`, `Breadcrumbs`, `SeriesNav`, `RelatedPosts`, `PartCallout`.
5. Add exercise, caption and details styles; keep reading pages calm.
6. Add OG image route, roadmap RSS, sitemap `lastmod`, `_redirects`, `check-dist.mjs`.
7. Replace About placeholders; write the policy pages; add Contact.

---

## 12. Implementation phases

| Phase | Scope | Exit criteria | Est. |
|---|---|---|---|
| **S0 Monorepo** | Move into `apps/site`; add `packages/content-schema`; root scripts; Node and pnpm pins | `pnpm setup && pnpm dev && pnpm build` work | 1 to 2 d |
| **S1 Staging deploy** | GitHub repo; Cloudflare Pages project per §9.2; `PUBLIC_SITE_INDEXING` toggle; `check-dist.mjs`; `site-ci.yml` | A commit to `main` deploys; staging is `noindex`; admin not in `dist` | 1 d |
| **S2 Hands-on roadmap UI** | Schema extensions; project panel, code panel, exercises, resources, sources, inspired-by, planned parts; styles | A hand-written sample part renders every block; schema rejects bad data | 2 to 3 d |
| **S3 SEO build-out** | `lib/seo.ts`; BaseLayout head; breadcrumbs; JSON-LD per §7; sitemap `lastmod`; RSS ×2; OG images; `_redirects`; internal-link components | Rich Results Test passes for post and part; Lighthouse SEO 100 | 2 to 3 d |
| **S4 Admin page** | Lean admin per §8 in step with pipeline phases P1 to P4 (`03`) | Blog review and course workspace work against the local API | 3 to 4 d |
| **S5 Pages and polish** | About copy, Contact, Terms, Privacy, Editorial; a11y and performance pass | Launch checklist (`01` §7.1) site items done | 2 d |
| **S6 Launch** | Custom domain; indexing on; Search Console; Bing; announce | Domain verified; sitemap submitted; key URLs requested | 1 d |

S0 and S1 come first because they prove the publish-and-deploy path before there is anything to lose.

---

## 13. Testing and CI

| Layer | Tooling |
|---|---|
| Content schema | Zod at build + JSON Schema tests (valid and invalid fixtures) shared with the pipeline |
| Type and template check | `astro check` |
| Build | `pnpm build` on every push |
| Admin guard | `check-dist.mjs` |
| Links | lychee on `dist` (internal always; external as a warning) |
| SEO | Rich Results Test on one post and one part (manual at launch); script checks canonical, title/description lengths, one H1, JSON-LD parseable |
| Accessibility | axe in Playwright on home, a post, a part, the quiz |
| Performance | Lighthouse CI against budgets (optional but recommended) |
| Interaction | Playwright: theme persistence, command palette, quiz and progress, part navigation |

---

## 14. Risks and open questions

| Risk | Mitigation |
|---|---|
| Wrong Cloudflare watch paths cause wasted or missed builds | Set per §9.2; test with a pipeline-only commit (no build) and a content commit (build) |
| Content commit breaks the build | Pipeline pre-validates; failed builds do not replace production; CI and revert |
| Effects hurt performance | Reading pages stay calm; budgets in CI |
| GitHub links 404 if a tag is missing | The pipeline pushes the tag **before** committing the part (`03` §7.6) |
| Schema drift between site and pipeline | One schema package; contract tests |

**Open questions**
1. Final domain and Cloudflare project name.
2. Course repo name and whether "Use this template" is enabled.
3. Whether to ship Pagefind search at launch (P1) or after.
4. Whether to show planned parts publicly (this PRD assumes yes, as "coming soon").
