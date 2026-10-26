# 01. Marketing, SEO and Launch Strategy

**Version:** 2.0 · **Date:** 26 Oct 2026 · **Owner:** Ben · **Status:** Draft for review
**Companions:** `02-prd-blog-site.md` (the site), `03-prd-content-pipeline.md` (the pipeline)

> **How to read this.** Policy and platform facts (Google structured data, Cloudflare Pages monorepos, AdSense) were checked in Oct 2026. Revenue and traffic numbers are scenarios, not forecasts. Items marked *(verify)* need a quick check against the live product before you act on them.

---

## 1. Summary

**What you are launching:** a technical site with **one flagship hands-on course** (a guided project: "build a LangGraph deep-research agent, piece by piece") and **4 to 5 high-quality blog posts**. The course is the hub. The blog posts feed it.

**Decisions this document is built on**

| Topic | Decision |
|---|---|
| Launch content | 1 flagship roadmap (6 parts, with a public GitHub project repo) + 4 to 5 blog posts |
| Pipeline | Lean, local, OpenRouter. Humans review everything that goes live |
| Hosting | Cloudflare Pages from a GitHub monorepo. Pipeline and admin page never deployed |
| Staging first | Deploy early on a `pages.dev` URL with `noindex`; public launch = flip indexing on and attach the custom domain |
| Monetization | Not at launch. AdSense is a later layer (see §8) |
| Search goal | Be eligible and discoverable in Google Search, autocomplete-style long-tail queries, and Discover, built on real quality rather than tricks |

**The honest picture**
- Developer education is crowded (Full Stack Open, official docs, YouTube, vendor academies). A generic "learn LangGraph" page will not rank. A **guided, tagged, runnable project** is a real differentiator, because each part has a repo state you can check out and diff.
- A new domain usually needs weeks to months before search traffic appears. Plan for a slow start and measure leading indicators (indexing, impressions) before clicks.
- AI-assisted content is acceptable to Google when it is useful, original in value, and reviewed. Your pipeline's human review, source citations and real code repo are exactly the signals that matter.

---

## 2. Positioning

> **Hands-on AI engineering courses where you build one real project, part by part, with every step as a Git tag you can check out and compare.**

**Audience (in priority order)**
1. **Switcher Sam:** a developer who knows Python or JavaScript and wants to build agents (LangGraph, RAG, tools) that work in practice.
2. **Fresher Fiona:** a CS student or recent graduate who wants a portfolio-grade project, not another to-do app.
3. **Recruiters and peers:** they read the Projects, About and the course repo as evidence of skill.

**Promises you can keep**
- Every part ends with working, tested code at a Git tag.
- Every lesson cites its sources, and every snippet comes from the real repo.
- Every roadmap shows when it was last reviewed.

**What you are not:** a certification body, a video course, or a news site.

---

## 3. Competitive landscape

| Competitor | Strength | Gap you can fill |
|---|---|---|
| Full Stack Open | Gold standard for project-based learning | Web dev focus; not agents or LLM tooling |
| Official docs (LangGraph, LangChain) | Authoritative | Reference-style; no single guided project |
| Vendor academies and short courses | Polished, trusted brands | Video-first; code state is hard to compare across steps |
| YouTube and blog tutorials | Reach and personality | Code drifts out of date; no per-step tags |
| roadmap.sh, freeCodeCamp | Brand, breadth | Breadth over a single built project |

**Defensible edges:** (1) the tagged project repo; (2) sources and review dates on everything; (3) fast to update when libraries change; (4) a distinctive visual identity; (5) a real engineer's voice (yours) rather than generic content.

---

## 4. Content strategy

### 4.1 Hub and spokes

```
HUB (flagship course)   /roadmaps/langgraph-deep-research/
   ├─ Part 1 … Part 6   /roadmaps/langgraph-deep-research/<part>/
   └─ supporting posts  /blog/<slug>/  (each links to the relevant part and back)
PROJECT REPO (GitHub)   github.com/<you>/langgraph-deep-research   (tags part-0 … part-6)
```

- Every blog post links to at least one course part. Every part links to related posts.
- The repo README links to the course, and the course links to the repo. Each side strengthens the other.

### 4.2 Launch set (candidate topics to validate, not promises)

Choose the 4 to 5 that you can write with real firsthand knowledge. Check each against Search Console data later; until then these are hypotheses.

| # | Candidate post | Why it fits |
|---|---|---|
| 1 | How LangGraph's `interrupt()` works, and when to use human-in-the-loop | Precise, searchable question; links to Part 5 |
| 2 | Architecture of a deep-research agent before you write any code | Natural top-of-funnel for the course |
| 3 | Getting reliable structured output from different models through OpenRouter | Firsthand lessons from this very pipeline |
| 4 | Why your research agent should fetch and verify every URL itself | Distinct angle, supports trust positioning |
| 5 | A practical pnpm monorepo with an Astro site and a Python app | Practical dev-tooling post with real config |

Rules for every post: a unique angle or firsthand example, tested code, a sources section, and a "last reviewed" date.

### 4.3 Cadence after launch
- 1 to 2 posts per week at most, each passing the quality gates. Never bulk-publish.
- A new course part every 2 to 3 weeks after the first course ships. A second course only after the first has traction.
- Review each post and part every 3 to 6 months, and update "last reviewed" only when something real changed.
- Posts with no impressions after about 90 days: improve, merge, or remove.

### 4.4 Quality rules that double as SEO insurance
Google's spam policy targets large volumes of pages made mainly to rank, however they are produced. The pipeline's design (human approval, cited sources, similarity and quote limits, code taken from a real repo) is the safeguard. Keep it.

---

## 5. SEO strategy

### 5.1 Principles
1. **People-first, answer-first.** Every page answers a specific question in its opening lines.
2. **Topical authority over volume.** One strong hub with supporting posts beats fifty unrelated articles.
3. **Technical excellence.** Static Astro on a CDN is a head start. Protect Core Web Vitals.
4. **Evidence of experience.** The GitHub repo, tags and your author page are proof of first-hand work.
5. **Measure with first-party data.** Search Console is the source of truth.

### 5.2 Staging, then launch (indexing control)
You want the pipeline and deployments working before the world sees the site.

| Phase | Site state | How |
|---|---|---|
| **Staging** (now until launch) | Live on a `*.pages.dev` URL, **not indexable** | `PUBLIC_SITE_INDEXING=off` adds `<meta name="robots" content="noindex">` and a `Disallow: /` robots.txt at build time |
| **Launch** | Custom domain attached, indexing on | Set `PUBLIC_SITE_INDEXING=on` in Cloudflare, redeploy, verify the domain in Search Console, submit the sitemap |

Keep your existing `benkicodes.pages.dev` blog running until launch day. Build the new site as a separate Cloudflare Pages project. At launch, point the custom domain at the new project and redirect old URLs (§5.9).

### 5.3 Keyword and topic research (lightweight, repeatable)
1. **Seed:** your pillars: LangGraph, agents, RAG, deep research, structured output, OpenRouter, tool use.
2. **Free sources:** Google autocomplete and "People also ask" (these also show how people phrase questions), Search Console queries once live, Reddit and Hacker News threads, GitHub issues and discussions on the libraries you cover.
3. **Pick targets** where intent is clear (learn, build, compare, fix), the top results are dated or shallow, and you have firsthand material.
4. **Per page:** one primary question, a few related phrasings as natural headings, one distinct angle.
5. **Avoid** head terms ("what is Python") and keyword-variation spam.

### 5.4 On-page rules (enforced by the site and pipeline)
- One H1; answer-first intro of 2 to 3 sentences; descriptive H2s phrased as the questions people ask.
- Title around 60 characters; description 120 to 155 characters, unique per page.
- Descriptive slugs without dates. Canonical on every page.
- Images with real alt text and explicit dimensions; code blocks with language and filename captions.
- Visible author, published date, **last reviewed** date, and sources.
- Internal links: every post to a course part, every part to its neighbors and related posts.

### 5.5 Technical SEO (site-side, see `02-prd-blog-site.md` §7)
Sitemap with accurate `lastmod`, robots.txt, canonical URLs, RSS, Open Graph and Twitter cards with generated images, semantic HTML, breadcrumbs, mobile-first layout, HTTPS, security headers, fast LCP/INP/CLS, and a clean 404.

### 5.6 Structured data: what is worth doing in 2026
- **Do:** `BlogPosting`/`Article` on posts and course parts, `BreadcrumbList` on every non-home page, `Person` for the author, `WebSite` on the home page. These match visible content.
- **Do not rely on:** the `Course` rich result. Google retired Course Info and several other types in June 2025. FAQ rich results have been retired, and HowTo has been deprecated for years. Do not add markup for features that no longer exist, and never mark up content that is not on the page.
- Structured data does not directly boost rankings. It supports rich-result eligibility and machine understanding. Validate with Google's Rich Results Test and watch the Enhancements reports in Search Console. *(verify the current supported-types list)*

### 5.7 Appearing in suggestions and Discover
- **Autocomplete and "People also ask":** you cannot request placement. You earn it by writing pages that directly answer the questions people type, using natural question phrasing in headings, and being the clearest answer. Use those surfaces for research as well.
- **Google Discover** *(verify current requirements)*: favors fresh, high-quality content with large, high-resolution images. Allow large image previews (`max-image-preview:large`), provide 1200px-wide OG images, and publish real timely pieces rather than evergreen filler. Do not plan around Discover; treat it as a bonus.
- **AI answers (AI Overviews and chat search):** write extractable, self-contained answers, show original value (tested code, a runnable repo, benchmarks, opinions), keep content dated and fresh, and keep the site fast and crawlable. There is no special markup that guarantees inclusion.

### 5.8 Index and measurement setup (launch day)
1. Verify the domain in **Google Search Console** (DNS verification) and submit `sitemap-index.xml`.
2. Verify in **Bing Webmaster Tools** (Bing also feeds other products). Optionally enable IndexNow for faster Bing discovery *(verify)*; Google does not use it.
3. Use URL Inspection to request indexing for the homepage, the course hub, and the first posts. Do not spam it.
4. Turn on **Cloudflare Web Analytics** (or Plausible/Umami) for traffic. Search Console covers search performance.
5. Check the Page indexing report weekly for "Discovered, not indexed" and "Crawled, not indexed".

### 5.9 Redirects and domain change
If the old `benkicodes.pages.dev` content moves, add 301 redirects (a `_redirects` file) for any URL that changes. Old pages that have no equivalent can simply return 404 or be removed; do not redirect everything to the homepage.

### 5.10 Backlinks and the repo as an SEO asset
- A public repo with a clear README, a license, tags per part, topics, and a link to the course is itself discoverable on GitHub and gives a natural, relevant backlink.
- Earn links by being useful: cite and credit the docs and courses that inspired you (they sometimes link back), share on communities that allow it, and post to dev.to or Hashnode with the **canonical URL pointing to your site**.
- Avoid link schemes, comment spam and paid links.

### 5.11 Realistic timeline
| When | What to expect |
|---|---|
| Weeks 0 to 2 | Pages discovered and indexed; few or no impressions |
| Weeks 3 to 8 | First impressions for long-tail queries; clicks are small and uneven |
| Months 3 to 6 | Patterns appear in Search Console; refine titles, add posts for rising queries |
| Months 6 to 12 | Compounding growth if quality and cadence hold |

---

## 6. Distribution and growth

| Channel | Tactic | Notes |
|---|---|---|
| **GitHub** | Public course repo with a great README, topics, template-repo setting, release notes per part | Stars and forks are social proof and traffic |
| **Communities** | r/LangChain-style communities, Hacker News "Show HN" for the course, dev.to, Hashnode | Follow each community's rules; give value first |
| **LinkedIn / X** | One post per published part or article: what you built, a screenshot, the link | Build in public |
| **Newsletter** | Start simple (RSS first, email later) | Owned audience, no algorithm |
| **Cross-posting** | Short adaptations with a canonical link back | Never copy full text without a canonical |
| **Peers and recruiters** | Link the course and repo from your CV and profiles | The project is your proof of skill |

The course repo is the strongest marketing asset you have. Treat its README as a landing page.

---

## 7. Launch plan

| Phase | Goal | Exit criteria |
|---|---|---|
| **A. Foundations** | Monorepo, Cloudflare staging deploy, noindex on | `pnpm build` green; staging URL live; Approve in admin publishes and deploys |
| **B. Blog set** | 4 to 5 reviewed posts via the pipeline | Each post passes gates, is reviewed by you, and links to the course |
| **C. Flagship course** | 6 parts, tagged repo, CI green on every tag | Every part published; repo public with README and template setting |
| **D. SEO polish** | Metadata, OG images, sitemap, RSS, internal links, performance | Lighthouse ≥ 90 on mobile for key pages; checklist in §7.1 complete |
| **E. Public launch** | Indexing on, custom domain, Search Console, announcements | Domain verified; sitemap submitted; first posts requested for indexing |

### 7.1 Pre-launch checklist
- [ ] Custom domain bought and attached to the new Pages project
- [ ] `PUBLIC_SITE_INDEXING=on` set for production only
- [ ] About page with real photo/bio, Contact, Privacy, Editorial policy, Terms or disclaimer
- [ ] Every page has a unique title and description; no placeholder text anywhere
- [ ] Every post and part shows author, dates and sources; AI-assistance disclosure is present and honest
- [ ] Course repo public, README complete, license added, topics set, CI green on all tags, "Use this template" enabled
- [ ] Sitemap, robots.txt, RSS feeds, canonical tags verified on the production build
- [ ] OG images render; 404 page helpful
- [ ] Lighthouse mobile ≥ 90 (performance, accessibility, SEO) on home, a post, a part
- [ ] Analytics on; Search Console and Bing verified
- [ ] Old site redirects planned (§5.9)

---

## 8. Monetization (later, and realistic)

**At launch:** no ads. The site is small, you may not meet AdSense's quality bar yet, and ads can hurt Core Web Vitals and trust for a new site.

**AdSense readiness (when you apply)**
- There is no fixed traffic requirement; rejection is most often "low value content".
- Expect to need a custom domain, original substantial content (roughly 20 to 30 solid pages is a common benchmark, not a rule), Privacy, About, Contact, and Editorial pages, a clean and fast site, and a consent banner for EEA/UK traffic *(verify current requirements)*.
- The site already has a single `ads.enabled` flag, so applying is a config change.

**Better first layers for a developer audience**
1. **Affiliate links** for tools you genuinely use (hosting, domains, books), clearly labelled.
2. **Newsletter sponsorship** once there is an audience.
3. **Premium extras** later: a printable cheat sheet, a part with extended exercises, or a hosted exercise checker. Do not build these until learners ask.
4. **Ads** once traffic is steady.

**Realism:** developer audiences block ads heavily, and traffic from India earns a much lower RPM than traffic from the US, UK or EU. The larger return from this project is career value (portfolio, hiring signal), with ads as a modest extra.

---

## 9. Trust and compliance

| Item | Requirement |
|---|---|
| Editorial policy page | Explains sources, AI assistance, human review, corrections |
| AI disclosure | Short, honest line on AI-assisted content; consistent wording |
| Privacy policy | Covers storage in the browser, analytics, ads, newsletter |
| Cookie consent | Only if ads or non-essential cookies are enabled |
| Copyright | Paraphrase; short quotes with attribution; link to resources, never copy them; credit inspirations in an "Inspired by" box; code in the repo has a license |
| Corrections | A visible "report an error" link; fix and update the review date |
| Affiliate disclosure | Near the links, when used |

---

## 10. Measurement

| Category | Metric | Target (first 6 months, aspirational) |
|---|---|---|
| Quality | Lighthouse mobile (home, post, part) | ≥ 90 |
| Indexing | Indexed pages ÷ pages submitted | > 90% |
| Search | Impressions and clicks (Search Console) | Growing month over month |
| Content | Posts passing all gates on the first review | Rising |
| Course | Repo stars/forks, part-to-part drop-off (analytics), time on part pages | Tracked |
| Pipeline | Cost and review time per post and per part | Falling |
| Revenue | Affiliate clicks; ad RPM once enabled | Tracked, not a goal yet |

Review Search Console every week for the first month, then monthly.

---

## 11. 90-day plan

| Window | Focus |
|---|---|
| Days 1 to 14 | Monorepo, staging deploy (noindex), pipeline refactor, first two posts |
| Days 15 to 45 | Posts 3 to 5; course plan approved; Parts 1 to 3 coded, reviewed, published to staging |
| Days 46 to 75 | Parts 4 to 6; repo README and CI polish; SEO polish and performance |
| Days 76 to 90 | Public launch; Search Console; announcements; first Search Console review; plan the next posts from real queries |

Adjust to your available hours. The order matters more than the dates.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Slow search traffic | Distribution beyond search (GitHub, communities); leading indicators; patience |
| Content judged low value | Unique angle, tested code, citations, human review, reviewed dates |
| Library versions change and lessons go stale | Pin versions in the repo, show "last reviewed", update by tag, schedule reviews |
| Over-polishing before launch | Launch with 4 to 5 posts and one course; learn from real data |
| Effort spread too thin | One flagship course first; defer ideation agents and extra courses |
| Copying concerns with inspirations | Cite, paraphrase, link, credit |

---

## 13. Decisions needed from you

1. **Domain name** and registrar (needed before launch).
2. **GitHub username/org** and the course repo name.
3. Your final choice of the **4 to 5 launch posts**.
4. Whether to use your **real name and photo** on the About page (recommended for trust).
5. **Newsletter** at launch (RSS only is fine) or later.
