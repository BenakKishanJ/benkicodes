# PRD — BenKi Codes Blog Site (Astro)

**Version:** 1.0 · **Date:** 23 Oct 2026
**Owner:** Ben
**Status:** Draft for review
**Related:** `01-market-seo-monetization-strategy.md`, `03-prd-langgraph-content-pipeline.md`

---

## 1. Overview

### 1.1 Purpose
Build a fast, SEO-optimized, Arch-Linux-rice-themed website that hosts:
- a **blog** (news, trending topics, build-along guides),
- **roadmaps** (structured learning paths with modules and quizzes),
- **projects**, **about**, and a **homepage** that surfaces the latest content.

Content for blog and roadmaps is produced by a separate Python/LangGraph pipeline and delivered to this site as **Markdown/MDX files in Git**. The site has no runtime dependency on the pipeline.

### 1.2 Goals
| # | Goal | Success measure |
|---|---|---|
| G1 | Portfolio-quality design and engineering | Distinctive identity; clean public repo; Lighthouse ≥ 95 desktop / ≥ 90 mobile |
| G2 | AdSense- and SEO-ready | Passes the checklist in Strategy §5.3 and §6.5 |
| G3 | Interactive learning experience | Roadmap progress and quizzes work without login |
| G4 | Sellable/portable | Niche, brand, ads, analytics all config-driven; site runs without the pipeline |
| G5 | Frictionless publishing | Merging a content PR deploys the site automatically |

### 1.3 Non-goals (v1)
- User accounts, comments, or server-side databases
- Paid subscriptions or paywalls
- Multi-language content
- In-browser content editor (review happens in the pipeline's review tool)

### 1.4 Personas
See Strategy §4. Primary: **Fresher Fiona**, **Switcher Sam**, **Rice Rahul**. Secondary: recruiters viewing About/Projects.

---

## 2. Information architecture

```
/                          Home
/about/                    About Ben
/projects/                 Project index
/projects/<slug>/          Project detail
/blog/                     Blog index (paginated, filter by tag)
/blog/<slug>/              Post
/blog/tags/<tag>/          Tag archive (noindex if < 3 posts)
/roadmaps/                 Roadmap index
/roadmaps/<roadmap>/       Roadmap overview (modules, progress)
/roadmaps/<roadmap>/<module>/   Module lesson + quiz
/editorial-policy/         How content is made (trust page)
/privacy/  /terms/  /contact/
/rss.xml  /roadmaps/rss.xml  /sitemap-index.xml  /robots.txt  /ads.txt
/404
```

Global navigation: **Home · Blog · Roadmaps · Projects · About**. Search is available via the command palette (`Ctrl/Cmd+K`) and a visible search button.

---

## 3. Functional requirements

Priority: **P0** = launch blocker, **P1** = launch target, **P2** = post-launch.

### 3.1 Global shell

| ID | Requirement | Pri |
|---|---|---|
| GL-1 | Responsive layout from 320px up; no horizontal scroll | P0 |
| GL-2 | Theme system: light and dark plus named rice palettes (§6.2). Persisted in `localStorage`. Respects `prefers-color-scheme` on first visit. No flash of wrong theme (inline script in `<head>`). | P0 |
| GL-3 | Header with nav, theme switcher, search trigger. Collapses to a drawer on mobile. | P0 |
| GL-4 | Footer styled as a status bar (waybar-style): site section, reading time or page info, theme name, RSS link, legal links | P1 |
| GL-5 | Command palette (`Ctrl/Cmd+K`): navigate pages, search content, switch theme, open latest post | P1 |
| GL-6 | Keyboard accessibility: skip link, visible focus ring, logical tab order | P0 |
| GL-7 | `prefers-reduced-motion` disables non-essential animation | P0 |
| GL-8 | Cookie consent banner, shown only when ads/analytics need consent, styled to match | P1 |
| GL-9 | Custom 404 as a "command not found" terminal screen with helpful links | P1 |

### 3.2 Homepage

| ID | Requirement | Pri |
|---|---|---|
| HM-1 | Hero: terminal-style intro (typewriter effect, respects reduced motion), tagline, primary CTAs: *Browse roadmaps*, *Read the blog* | P0 |
| HM-2 | "Latest posts" pane (3–6 items: title, excerpt, tags, date, reading time) | P0 |
| HM-3 | "Featured roadmap" and "Latest roadmap modules" panes | P0 |
| HM-4 | "Projects" teaser (2–3 featured) | P1 |
| HM-5 | Tiling-WM-style layout: bordered panes, collapse to a single column on mobile | P1 |
| HM-6 | Newsletter signup pane | P1 |
| HM-7 | Content is generated at build time from collections. No client-side fetching. | P0 |

### 3.3 Blog

| ID | Requirement | Pri |
|---|---|---|
| BL-1 | Index with pagination (10/page), tag filter, and featured post | P0 |
| BL-2 | Post page: title, author, published and **last reviewed** dates, reading time, tags, TOC (auto from headings), body, sources list, related posts | P0 |
| BL-3 | Code blocks: syntax highlighting (Shiki), language label, copy button, optional filename header, line highlight | P0 |
| BL-4 | Callout components (note, tip, warning) in rice style | P1 |
| BL-5 | Per-post OG image auto-generated at build time | P1 |
| BL-6 | Sources section rendered from frontmatter `sources[]` | P0 |
| BL-7 | AI-assistance disclosure line (configurable text) rendered from frontmatter flag | P0 |
| BL-8 | Prev/next and related posts (by shared tags) | P1 |
| BL-9 | RSS feed | P0 |
| BL-10 | Share links (copy link, X, LinkedIn). No third-party tracking scripts. | P2 |
| BL-11 | Draft posts (`draft: true`) excluded from production builds, visible in dev | P0 |

### 3.4 Roadmaps

| ID | Requirement | Pri |
|---|---|---|
| RM-1 | Roadmap index: cards with title, level, estimated duration, module count, last reviewed | P0 |
| RM-2 | Roadmap overview: description, prerequisites, outcomes, **module list as a vertical "git-graph"/timeline**, overall progress | P0 |
| RM-3 | Module page: lesson content (MDX), learning objectives, estimated time, resources list, **quiz at the end**, prev/next module | P0 |
| RM-4 | **Quiz component** (Astro island): multiple choice (single/multi-select), per-question explanation, hints optional, score summary, retry. Answers and explanations ship in the page payload (no server). | P0 |
| RM-5 | **Progress tracking** in `localStorage`: modules completed, quiz best scores. Graceful if storage is unavailable. Export/import progress as JSON. | P1 |
| RM-6 | Quiz question and option order shuffled per attempt | P1 |
| RM-7 | Optional visual roadmap diagram (SVG/Mermaid) on the overview page | P2 |
| RM-8 | "Last reviewed" date and version note on each roadmap | P0 |
| RM-9 | Roadmap RSS feed (new modules/updates) | P1 |
| RM-10 | Printable/PDF-friendly stylesheet for a roadmap | P2 |

### 3.5 Projects

| ID | Requirement | Pri |
|---|---|---|
| PR-1 | Index grid with cover, title, one-line summary, tech tags, status (active/shipped/archived) | P0 |
| PR-2 | Detail page: problem, approach, architecture (diagram), tech stack, outcomes, links (repo, live demo), screenshots, lessons learned | P0 |
| PR-3 | Projects are hand-written content (not pipeline-generated) | P0 |
| PR-4 | `SoftwareSourceCode`/`CreativeWork` JSON-LD optional | P2 |

### 3.6 About

| ID | Requirement | Pri |
|---|---|---|
| AB-1 | `neofetch`-style summary card (name, role, stack, location (optional), links) plus a human story section | P0 |
| AB-2 | Skills grouped by area, links to GitHub/LinkedIn/email, resume download | P0 |
| AB-3 | `Person` JSON-LD with `sameAs` links (E-E-A-T) | P1 |

### 3.7 Search

| ID | Requirement | Pri |
|---|---|---|
| SR-1 | Static, client-side search via **Pagefind** (built post-build), covering blog, roadmaps, projects | P1 |
| SR-2 | Results integrated in the command palette and a dedicated `/search` page | P1 |

### 3.8 Monetization & analytics

| ID | Requirement | Pri |
|---|---|---|
| MN-1 | Ad slot components (`<AdSlot id="in-article-1" />`) with reserved heights to avoid CLS | P1 |
| MN-2 | One config flag (`ads.enabled`) controls all ad scripts and slots. Disabled by default until approved. | P0 |
| MN-3 | Ad scripts load only after consent where required | P1 |
| MN-4 | `ads.txt` served from `public/` | P1 |
| MN-5 | Privacy-friendly analytics (Cloudflare Web Analytics or Plausible/Umami) toggled by config | P1 |
| MN-6 | Affiliate link component with automatic disclosure label | P2 |
| MN-7 | Newsletter form posting to a provider (Buttondown/Resend/etc.) via a small edge function or provider-hosted form | P1 |

### 3.9 Editorial / trust pages

| ID | Requirement | Pri |
|---|---|---|
| ED-1 | `/editorial-policy/` page explaining sources, AI assistance, human review, corrections | P0 |
| ED-2 | Privacy, Terms/Disclaimer, Contact pages | P0 |
| ED-3 | "Report an error" link on posts (mailto or GitHub issue template) | P1 |

---

## 4. Content model (Astro Content Collections)

Collections are validated with Zod at build time. **Invalid content fails the build.** This is also the contract with the pipeline.

### 4.1 `blog`

```ts
// src/content.config.ts (illustrative)
const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string().max(70),
    description: z.string().min(70).max(160),
    slug: z.string().optional(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    lastReviewed: z.coerce.date(),
    tags: z.array(z.string()).min(1).max(6),
    category: z.enum(["news", "guide", "tutorial", "opinion", "tooling"]),
    cover: z.object({ src: z.string(), alt: z.string() }).optional(),
    draft: z.boolean().default(false),
    featured: z.boolean().default(false),
    readingTime: z.number().optional(),          // computed if absent
    sources: z.array(z.object({
      title: z.string(), url: z.string().url(), publisher: z.string().optional(),
      accessed: z.coerce.date().optional()
    })).min(1),
    aiAssisted: z.boolean().default(true),
    reviewedBy: z.string().default("Ben"),
    pipelineRunId: z.string().optional(),         // traceability back to the run
    canonical: z.string().url().optional(),
  }),
});
```

### 4.2 `roadmaps` and `modules`

```ts
const roadmaps = defineCollection({
  loader: glob({ pattern: "*/index.md", base: "./src/content/roadmaps" }),
  schema: z.object({
    title: z.string(), description: z.string().max(160),
    level: z.enum(["beginner", "intermediate", "advanced"]),
    estimatedHours: z.number(),
    prerequisites: z.array(z.string()).default([]),
    outcomes: z.array(z.string()).min(3),
    tags: z.array(z.string()),
    lastReviewed: z.coerce.date(), version: z.string().default("1.0"),
    draft: z.boolean().default(false), featured: z.boolean().default(false),
    moduleOrder: z.array(z.string()),             // module slugs in order
    pipelineRunId: z.string().optional(),
  }),
});

const modules = defineCollection({
  loader: glob({ pattern: "*/modules/*.{md,mdx}", base: "./src/content/roadmaps" }),
  schema: z.object({
    title: z.string(), roadmap: z.string(),       // roadmap slug
    order: z.number(), estimatedMinutes: z.number(),
    objectives: z.array(z.string()).min(2),
    resources: z.array(z.object({ title: z.string(), url: z.string().url(), type: z.enum(["docs","video","article","repo","book"]) })).default([]),
    quiz: z.array(z.object({
      id: z.string(),
      question: z.string(),
      type: z.enum(["single", "multi"]).default("single"),
      options: z.array(z.object({ id: z.string(), text: z.string() })).min(3).max(6),
      correct: z.array(z.string()).min(1),
      explanation: z.string(),
      difficulty: z.enum(["easy","medium","hard"]).default("medium"),
      hint: z.string().optional(),
    })).min(3),
    lastReviewed: z.coerce.date(), draft: z.boolean().default(false),
    pipelineRunId: z.string().optional(),
  }),
});
```

### 4.3 `projects`
Fields: `title`, `summary`, `status`, `stack[]`, `repo`, `demo`, `cover`, `featured`, `order`, `startDate`.

> **Contract rule:** the pipeline's publisher validates its output against a copy of these schemas before opening a PR. Keep schemas in a shared, versioned file (`content-schema.json`, generated from Zod).

---

## 5. Technical architecture

### 5.1 Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | **Astro** (current major; Astro 6 requires `@astrojs/cloudflare` v13+ if the adapter is used) | Static output by default |
| Styling | Tailwind CSS + CSS variables for theme tokens | shadcn-style primitives re-implemented as Astro components (+ React islands only where needed) |
| Interactivity | Astro islands (React or Preact) for: Quiz, Command palette, Theme switcher, Progress tracker | Keep JS minimal; `client:visible`/`client:idle` |
| Content | Markdown/MDX + Content Collections | Git is the CMS |
| Code highlighting | Shiki (built into Astro) | Dual theme support |
| Search | Pagefind | Runs after build |
| OG images | Satori + resvg (build-time) or `astro-og-canvas` | |
| Icons | Lucide or Phosphor, plus Nerd Font glyph accents | |
| Fonts | A monospace display font (e.g., JetBrains Mono / Fira Code) plus a readable sans for body text. Self-host, `font-display: swap`, subset. | |
| Analytics | Cloudflare Web Analytics or Plausible/Umami | Config-driven |
| Hosting | **Cloudflare**. See §5.2. | |

### 5.2 Hosting decision: Pages vs Workers static assets

Your current site is on `*.pages.dev`. Cloudflare now recommends **Workers with static assets** for new projects and focuses new features there; Astro's deployment docs say the same. Pages still serves static sites well.

**Recommendation:**
- Build the site as **pure static output** (no adapter), which deploys equally well to Pages or Workers static assets.
- Start on whichever you already have working. Keep deployment config isolated so migrating is a config change, not a rewrite.
- Add the Cloudflare adapter only if you later need on-demand routes (e.g., a newsletter endpoint). A provider-hosted form avoids needing one.
- Use a **custom domain** before applying to AdSense.

### 5.3 Repository structure

```
benki-blog/
├─ src/
│  ├─ content/
│  │  ├─ blog/                      # pipeline output + manual posts
│  │  ├─ roadmaps/<roadmap>/index.md
│  │  ├─ roadmaps/<roadmap>/modules/*.mdx
│  │  └─ projects/
│  ├─ components/
│  │  ├─ ui/                        # Button, Card, Badge, Tabs, Dialog, Tooltip (shadcn-like)
│  │  ├─ rice/                      # TerminalWindow, StatusBar, Neofetch, TilingGrid, CmdPalette, Typewriter
│  │  ├─ content/                   # Callout, CodeBlock, TOC, SourcesList
│  │  ├─ learning/                  # Quiz, ProgressBar, ModuleTimeline
│  │  └─ ads/                       # AdSlot, ConsentBanner
│  ├─ layouts/
│  ├─ pages/
│  ├─ styles/ (tokens.css, themes.css, global.css)
│  ├─ lib/ (reading-time, schema, seo, progress)
│  └─ content.config.ts
├─ public/ (fonts, favicons, ads.txt, robots.txt)
├─ site.config.ts                   # niche, brand, nav, social, ads/analytics toggles
├─ scripts/ (validate-content, link-check, og-images)
└─ .github/workflows/ (ci.yml, content-pr-checks.yml)
```

### 5.4 Configuration (`site.config.ts`)
Single source for: site name, tagline, URL, author, social links, nav items, default theme, enabled themes, ads on/off + publisher ID, analytics provider, newsletter provider, AI-disclosure text, feature flags (search, command palette, progress tracking). **Nothing brand-specific is hard-coded elsewhere.** This is what makes the template sellable.

### 5.5 Deployment & CI/CD

1. Pipeline opens a **PR** to the site repo with content files plus a PR description (run ID, sources, critic scores).
2. CI runs: schema validation, Markdown/MDX lint, link checker, spell check (optional), build, Lighthouse CI on preview, accessibility checks (axe).
3. Cloudflare creates a **preview deployment** for the PR. Ben reviews the *rendered* page.
4. Merge to `main` → production deploy. Rollback = revert commit.

---

## 6. Design requirements

### 6.1 Design principles
1. **Rice, but readable.** Aesthetic personality never beats legibility. Body text has ≥ 4.5:1 contrast.
2. **Terminal as metaphor, not cosplay.** Use terminal motifs for chrome (headers, cards, status bars). Long-form content stays in clean typography.
3. **Performance is a feature.** Effects are CSS-first, GPU-friendly, and optional.
4. **Consistency through tokens.** Everything derives from design tokens, so themes are cheap to add.

### 6.2 Themes
Provide a theme switcher with at minimum:
- **Light** and **Dark** (default pair, auto by OS)
- Rice palettes: **Catppuccin (Mocha/Latte)**, **Gruvbox**, **Nord**, **Tokyo Night**, **Rosé Pine** *(ship 3 at launch, add the rest later)*

Themes are CSS variable sets on `[data-theme]`: `--bg`, `--surface`, `--surface-2`, `--border`, `--text`, `--text-muted`, `--accent`, `--accent-2`, `--success`, `--warning`, `--danger`, `--code-bg`, `--selection`. Each theme must pass WCAG AA for text on surfaces. Add an automated contrast check in CI.

### 6.3 Component inventory

**Primitives (shadcn-like):** Button, Badge, Card, Tabs, Accordion, Dialog/Drawer, Tooltip, Input, Select, Switch, Progress, Separator, Toast, Kbd.

**Rice components:**
| Component | Description |
|---|---|
| `TerminalWindow` | Title bar with traffic-light dots, prompt line, optional typewriter content |
| `StatusBar` | Waybar-style footer/header strip with segments |
| `Neofetch` | ASCII/logo plus key-value system-info card for About |
| `TilingGrid` | Bordered panes with gap, focus highlight on hover |
| `CommandPalette` | rofi/dmenu-style overlay |
| `PromptHeading` | `❯ heading` style with blinking cursor |
| `GitGraph` timeline | Roadmap module list drawn like a `git log --graph` |
| `PackageBadge` | `pacman`-style tags/badges |
| `WorkspaceSwitcher` | Optional "workspace 1–5" indicators for nav or pagination |
| `Callout` | Styled as `[INFO]`, `[WARN]`, `[TIP]` log lines |

### 6.4 Motion and effects
- Allowed: typewriter hero text, cursor blink, subtle hover glow, fade/slide-in on scroll (CSS `animation-timeline` or IntersectionObserver), scanline overlay (very low opacity, toggleable), smooth theme transitions.
- Budget: effects must not push LCP/INP out of target. No large JS animation libraries. No auto-playing heavy canvas backgrounds on mobile.
- All motion disabled under `prefers-reduced-motion`.
- Provide a **"Reduce effects"** toggle in the settings menu.

### 6.5 Typography and layout
- Monospace for UI chrome, headings optional mono; body in a readable sans or serif (≥ 17–18px on desktop, 16px minimum on mobile), line length 65–75 characters, generous line height.
- Content width: ~720px for reading, wider for tables/code (scroll inside container).
- Spacing and radii from a small scale; borders thin (1px) with accent on focus.

### 6.6 Brand decision (open)
The existing BenKi.dev identity is pixel/retro (Pixelify Sans, sticker badges). This site's Arch-rice direction is different. **Decide:** unify (rice-flavored pixel aesthetic) or keep separate brands. A mixed look will read as inconsistent.

---

## 7. SEO requirements (site-level)

Full strategy is in the Strategy report. Site-level must-haves:

| ID | Requirement | Pri |
|---|---|---|
| SE-1 | Unique `<title>` and meta description per page, driven by frontmatter | P0 |
| SE-2 | Canonical URL on every page | P0 |
| SE-3 | `sitemap-index.xml`, `robots.txt`; drafts excluded | P0 |
| SE-4 | Open Graph/Twitter metadata with generated images | P1 |
| SE-5 | JSON-LD: `BlogPosting`, `BreadcrumbList`, `Person`, `WebSite` | P1 |
| SE-6 | Breadcrumb navigation on blog, roadmap, module pages | P1 |
| SE-7 | Semantic HTML (`article`, `nav`, `main`, `time`), one H1 per page | P0 |
| SE-8 | Thin archive pages (tags with < 3 posts) are `noindex, follow` | P1 |
| SE-9 | Internal-link check in CI: no orphans, no broken links | P0 |
| SE-10 | Image requirements: alt text mandatory, dimensions set, modern formats | P0 |
| SE-11 | RSS auto-discovery `<link rel="alternate">` | P1 |

---

## 8. Accessibility requirements

- Target **WCAG 2.2 AA**.
- Keyboard-operable everything, including quiz and command palette (focus trap, `Esc` to close, ARIA roles).
- Quiz: labelled fieldsets, results announced via `aria-live`.
- Theme palettes pass contrast checks.
- Don't convey state by color alone (add icons or text).
- Automated axe checks in CI plus a manual keyboard pass before launch.

---

## 9. Performance requirements

| Metric | Target (mobile, 4G, mid-range device) |
|---|---|
| LCP | ≤ 2.5s (aim ≤ 1.8s) |
| INP | ≤ 200ms |
| CLS | ≤ 0.1 (including ad slots) |
| Lighthouse Performance | ≥ 90 mobile, ≥ 95 desktop |
| JS per content page (excluding ads) | ≤ ~50 KB gzipped |
| Fonts | ≤ 2 families, ≤ 4 files, preloaded, subset |

Enforced via Lighthouse CI budgets on every PR.

---

## 10. Security & privacy

- Security headers via `_headers`: CSP (allowing only required script hosts), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS on the custom domain.
- No third-party scripts except consented ads, analytics, and the newsletter form provider.
- `localStorage` only for theme, effects toggle, and learning progress. No personal data.
- Content from the pipeline is rendered as MDX. **Treat pipeline output as untrusted**: restrict allowed MDX components, disallow raw `<script>`/inline event handlers, sanitize embeds. CI rejects disallowed constructs.
- Dependabot/Renovate for dependency updates; pin versions.

---

## 11. Testing & quality

| Layer | Tooling |
|---|---|
| Content schema | Zod at build + custom validation script |
| Unit | Vitest (quiz scoring, progress storage, reading-time, schema helpers) |
| Component/E2E | Playwright (theme persistence, quiz flow, command palette, mobile nav) |
| A11y | axe-core in Playwright/CI |
| Performance | Lighthouse CI |
| Links | `lychee` or similar link checker |
| Visual regression (P2) | Playwright screenshots per theme |

---

## 12. Milestones

| Phase | Scope | Exit criteria |
|---|---|---|
| **P1 — Foundation** (~1 wk) | Astro project, tokens, theme system, layout shell, nav, footer, deploy pipeline on custom/preview domain | Themes switch without flash; deploys on push |
| **P2 — Core pages** (~1–2 wks) | Home, About, Projects, Blog (index + post), Roadmap (index + overview + module), content collections, 3 hand-written posts, 1 sample roadmap | All pages responsive; schemas enforced |
| **P3 — Learning & polish** (~1 wk) | Quiz island, progress tracking, command palette, Pagefind search, rice components, animations | RM-1…RM-6 done; a11y pass |
| **P4 — SEO & trust** (~1 wk) | Sitemap, RSS, OG images, JSON-LD, policy pages, editorial policy, analytics, consent | Strategy §5.3 checklist ≥ 80% |
| **P5 — Pipeline integration** (~1 wk) | PR-based publishing, preview deploys, CI checks, contract tests | A pipeline-produced post flows end to end |
| **P6 — Productize** (ongoing) | Config extraction, docs, template packaging, case study | New niche can be spun up by editing config only |

---

## 13. Acceptance criteria (launch)

- [ ] All P0 requirements implemented; ≥ 80% of P1
- [ ] Lighthouse targets met on Home, a post, a roadmap module
- [ ] Zero critical axe violations; keyboard-only walkthrough passes
- [ ] Light, dark, and ≥ 3 rice themes verified for contrast
- [ ] Content schema violations fail CI
- [ ] A pipeline-generated post and roadmap published via PR → preview → merge
- [ ] Legal/trust pages live; AI disclosure and sources render on posts
- [ ] `site.config.ts` fully controls branding, ads, analytics

---

## 14. Open questions

1. Final domain name?
2. Unify with the BenKi.dev brand or separate identity?
3. Which analytics provider?
4. Newsletter provider and whether to run an edge function for signups?
5. Comments (none vs. GitHub Discussions-based) for post-launch?
6. React vs. Preact for islands (bundle size vs. ecosystem familiarity)?
7. Will the review UI live inside this site (`/admin`, protected by Cloudflare Access) or only in the pipeline repo? (The Pipeline PRD assumes the latter for v1.)
