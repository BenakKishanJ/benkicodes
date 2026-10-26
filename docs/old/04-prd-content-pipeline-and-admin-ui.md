# PRD: Content Pipeline (LangGraph), Admin UI, and Monorepo

**Version:** 2.0 · **Date:** 26 Oct 2026 · **Owner:** Ben · **Status:** Draft for review
**Supersedes:** `03-prd-langgraph-content-pipeline.md` (v1 concept). **Builds on:** the v0.1 blog-mode implementation already delivered.
**Companions:** `01-market-seo-monetization-strategy.md`, `02-prd-astro-blog-site.md`

> **How to read this.** Section 1 states what is decided. Sections 2 to 4 cover the repo, how it runs, and the model layer. Sections 5 to 8 are the heart of the document: the domain model, the blog graph, the roadmap graph, and the quality gates. Section 9 specifies the admin UI and its API. Sections 10 to 14 cover publishing, security, testing, the build plan, and risks. Facts about OpenRouter come from its current documentation. Where a detail must be confirmed against the live API at implementation time, it is marked *(verify)*.

---

## 1. Overview

### 1.1 Purpose
A local, human-supervised content system for the BenKi site. It turns sources Ben chooses into **reviewed blog posts** and **reviewed learning roadmaps** (lessons plus quizzes), and publishes each approved piece to the site by committing to `main`. It also serves as a showcase of a production-style LangGraph application: durable runs, human-in-the-loop checkpoints, parallel fan-out, quality gates, evals, cost control, and a purpose-built control UI.

### 1.2 Decisions already made

| Topic | Decision |
|---|---|
| Repo shape | One git repo, pnpm workspace: `apps/site` (Astro), `apps/pipeline` (Python), `packages/content-schema` (shared contract) |
| Where it runs | **Only on Ben's own computer.** The pipeline and the admin page are never deployed. Only the static site is deployed. |
| Admin UI | A reserved route in the site (`/admin/`), present in `pnpm dev` only and excluded from production builds |
| Model provider | **OpenRouter**, so models are switchable per task from the UI |
| Publish action | Approve commits straight to `main`; Cloudflare auto-deploys |
| Blog grounding | Sources Ben supplies (URLs, pasted text), optional gap-filling research |
| Roadmap grounding | **Official docs URLs Ben supplies, plus web research with citations** to find well-illustrated, curated resources |
| Roadmap go-live | **Module by module**, as each is approved. Unfinished modules stay drafts inside the pipeline (not in the repo). |
| First delivery order | Blog mode first (done as v0.1), roadmap mode next |

### 1.3 Goals

| # | Goal | Measure |
|---|---|---|
| G1 | Drafts Ben can approve with light edits | ≥ 70% of blog drafts and ≥ 60% of roadmap modules approved within 2 review rounds after the first 15 runs |
| G2 | Nothing unverified reaches the site | 0 published claims without a source; 0 published links that did not resolve at publish time |
| G3 | Switch models without code changes | Any task's model changeable in the UI in under 30 seconds; same input runnable on 2 to 3 models for comparison |
| G4 | Predictable cost | Every run shows live tokens and dollars; a per-run cap always stops overspend |
| G5 | Durable and inspectable | A run survives a crash or restart; every node's inputs, outputs, model, tokens and cost are viewable |
| G6 | Showcase-grade | Public-quality README, architecture diagram, eval results, demo video |

### 1.4 Non-goals (this version)
- Hosting the pipeline or admin page anywhere (see §3.4 for the explicit analysis)
- Multi-user access, accounts, or roles
- Fully autonomous publishing. A human approves every publish.
- Image generation (cover *prompts* only)
- Editing existing published content through the pipeline (planned refresh mode, §14)
- Social posting, newsletters, analytics

### 1.5 Principles
1. **Human in command.** Ben approves the outline or structure and every piece that goes live.
2. **Grounded or omitted.** A factual statement needs a source. Resources are linked, never copied.
3. **Verify, don't trust.** Model output, search results and fetched pages are untrusted. Every URL a published page contains was fetched successfully by the pipeline itself.
4. **Cheap by default, strong where it counts.** Tiered models, caching, a per-run budget.
5. **Resumable.** Every step checkpoints. A failure is retried from the last good step, not from the start.
6. **One contract.** The site's content schema is the single source of truth, shared with the pipeline through `packages/content-schema`.

### 1.6 Delta from the v0.1 implementation

| Area | v0.1 (delivered) | This PRD |
|---|---|---|
| Model access | `langchain-google-genai`, Gemini | OpenRouter gateway with per-task models, fallbacks, live cost |
| Modes | Blog | Blog + Roadmap |
| Research | None | Web research (OpenRouter web search) + verified fetching |
| Publishing | Writes into the site working tree, `pull --rebase --autostash` | Dedicated git worktree; Ben's working tree is never touched |
| Repo | Two separate folders | pnpm monorepo, shared schema package |
| Admin UI | Single-run review page, polling | Runs, roadmap workspace, library, settings, graph view, streaming events |
| Cost | Token counts | Real dollars from OpenRouter usage data, caps, budget pause |
| Evals | None | Golden-set evals and model comparison |

---

## 2. Monorepo and workspace architecture

### 2.1 Layout

```
benki/                                  # git root
├─ pnpm-workspace.yaml
├─ package.json                         # root scripts only
├─ pnpm-lock.yaml
├─ .gitignore  .editorconfig  README.md
├─ apps/
│  ├─ site/                             # Astro site (what Cloudflare builds)
│  │  ├─ package.json  (name: "site")
│  │  ├─ astro.config.mjs
│  │  └─ src/ (content/, pages/, components/, admin/ ...)
│  └─ pipeline/                         # Python app (LangGraph + FastAPI)
│     ├─ package.json  (name: "pipeline", private, wrapper scripts only)
│     ├─ pyproject.toml  uv.lock
│     ├─ .env.example                   # OPENROUTER_API_KEY, ADMIN_TOKEN, ...
│     ├─ src/pipeline/ ...              # see §2.4
│     ├─ prompts/  voice/  config/
│     ├─ tests/  evals/
│     └─ data/                          # gitignored: sqlite, cache, publish worktree
└─ packages/
   └─ content-schema/                   # Zod source of truth + generated JSON Schema
      ├─ package.json  (name: "@benki/content-schema")
      ├─ src/*.ts                       # blog, roadmap, module, project schemas
      └─ dist/*.schema.json             # generated; consumed by Python and the site
```

### 2.2 What pnpm does and does not do
- pnpm manages **JavaScript** packages: `site` and `@benki/content-schema`. It links them and runs scripts across the workspace.
- pnpm does **not** manage Python dependencies. `apps/pipeline` has a thin `package.json` so pnpm can run it with `--filter`. Python dependencies are locked by **uv** (`pyproject.toml` + `uv.lock`).
- The repo requires Node ≥ 22.23.4 (Astro 7.4), pnpm via Corepack (`packageManager` field pinned), and Python ≥ 3.11 with uv.

### 2.3 Scripts

| Script (root) | Runs | Notes |
|---|---|---|
| `pnpm setup` | `pnpm install` then `pnpm --filter pipeline setup` (`uv sync`) | One command after cloning |
| `pnpm dev` | `pnpm -r --parallel --filter site --filter pipeline dev` | Astro on `:4321` and the pipeline API on `127.0.0.1:8787`, together |
| `pnpm dev:site` / `dev:pipeline` | Each alone | |
| `pnpm build` | `pnpm --filter site build` | What Cloudflare runs |
| `pnpm test` | `pnpm -r test` | Site checks + `uv run pytest` |
| `pnpm schema` | Generates JSON Schema from Zod (`z.toJSONSchema` in Zod 4) into `packages/content-schema/dist` | Run automatically before `dev`, `test`, `build` |
| `pnpm eval` | `uv run pipeline eval` | Golden-set evals (opt-in, spends money) |

`apps/pipeline/package.json` scripts: `dev` → `uv run pipeline serve --reload`, `test` → `uv run pytest -q`, `setup` → `uv sync`, `lint` → `uv run ruff check .`.

### 2.4 Pipeline package layout

```
src/pipeline/
  config.py            settings (pydantic-settings): env + data/settings.json overrides
  gateway/             openrouter.py (client), models.py (catalog, capability filter), cost.py (budget), search.py (web search tool)
  schemas/             llm outputs, state, decisions (Pydantic); contract.py (validates against content-schema JSON)
  state.py             BlogState, RoadmapState, ModuleState, reducers
  graphs/              blog.py, roadmap.py, module.py (subgraph), hub.py (review hub), common.py
  nodes/               ingest.py research.py claims.py outline.py write.py critique.py quiz.py consistency.py seo.py ...
  tools/               fetch.py (robots, SSRF guard, size caps), gates.py, quiz_checks.py, code_checks.py, publisher.py, worktree.py
  api/                 app.py, routes_runs.py, routes_models.py, routes_settings.py, routes_library.py, events.py (SSE)
  store.py             run index, event log, settings store
  cli.py               serve, token, eval, compare, doctor
```

### 2.5 Git and deployment settings for a monorepo
- **Cloudflare build:** command `pnpm --filter site build`, output directory `apps/site/dist`, repo root as project root. Set **build watch paths** to include `apps/site/*`, `packages/*`, `pnpm-lock.yaml` and exclude `apps/pipeline/*`, so pipeline-only commits never redeploy. Approving content commits into `apps/site/src/content/…`, which does trigger a deploy. *(Confirm the watch-path options in the Cloudflare dashboard when you set this up.)*
- **Hosting product note:** Cloudflare now steers new projects toward Workers static assets. Because the site is plain static output, either product works with this build command. Keep the config isolated so a later move is a settings change.
- **Branching:** work normally on feature branches. The pipeline only ever pushes content commits to `main` (§10.4) and never touches your working tree.

---

## 3. How it runs: local operation, and whether to deploy

### 3.1 Process model

```
 Browser  http://localhost:4321/admin/
    │  fetch + SSE (X-Admin-Token, CORS: only http://localhost:4321)
    ▼
 Pipeline API  http://127.0.0.1:8787      (FastAPI, bound to loopback)
    ├─ LangGraph runtime (thread pool, max 2 runs, module concurrency 3)
    ├─ SQLite: checkpoints.db (LangGraph state), runs.db (index, events, settings)
    ├─ Gateway ──HTTPS──▶ OpenRouter (chat, structured outputs, web search tool)
    ├─ Fetcher ──HTTPS──▶ public web (robots.txt respected, SSRF-guarded)
    └─ Publisher ─ git worktree ─▶ origin/main ──▶ Cloudflare build ──▶ live site
```

### 3.2 Day-to-day workflow
1. `pnpm dev` (first time: `pnpm setup`). The terminal prints the API address and the admin token once. The token is stored in `apps/pipeline/.env`.
2. Open `http://localhost:4321/admin/` and paste the token once. It is kept in the browser's local storage.
3. Start a blog or roadmap run, answer checkpoints, review, approve.
4. Approve commits to `main`. The site redeploys in about a minute. The admin page shows the commit and the live URL.
5. Stop `pnpm dev` whenever. Runs waiting for review stay in the database and resume next time.

### 3.3 Local-runtime requirements

| ID | Requirement |
|---|---|
| RT-1 | The API binds to `127.0.0.1` only. It rejects requests whose `Host` header is not `127.0.0.1:8787` or `localhost:8787` (DNS-rebinding guard). |
| RT-2 | Every route except `/health` requires the `X-Admin-Token` header, compared in constant time. |
| RT-3 | CORS allows only the configured site origins (default `http://localhost:4321`, `http://127.0.0.1:4321`) and only the headers it needs. A test proves other origins get no CORS headers. |
| RT-4 | The OpenRouter key lives only in `apps/pipeline/.env` (gitignored). It is never sent to the browser, logged, or put in prompts. |
| RT-5 | State is durable: checkpoint DB survives restarts; on startup the API marks runs that were mid-step as `interrupted` and offers **Resume from last checkpoint**. |
| RT-6 | `pipeline doctor` checks: Python and uv, Node and pnpm versions, API key present and valid, git repo clean enough to publish (worktree can be created), `origin` reachable, schema package built, site content dir present. The admin page shows the same checks on its connect screen. |
| RT-7 | Startup never makes a paid model call. |

### 3.4 Deploy or not: the decision

| Component | Deploy? | Why |
|---|---|---|
| **Site** (`apps/site`) | **Yes**, Cloudflare | Static, fast, cheap, SEO-ready |
| **Admin page** (`/admin/`) | **No.** Dev-only | It only works with the pipeline API, which is local. Shipping it adds attack surface and no value. |
| **Pipeline API + graphs** | **No.** Local only | One user. Local keeps API keys and git credentials off any server, costs nothing to host, and avoids building auth and a job queue. |

**How "not deployed" is enforced (not just intended):**
- `apps/site/src/pages/admin/[...slug].astro` returns an empty `getStaticPaths()` unless `import.meta.env.DEV` is true, so the route does not exist in production.
- A CI check fails the build if `dist/admin` exists or if the string `X-Admin-Token` appears anywhere in `dist`.
- The admin components are imported only from that route, so they are tree-shaken out of production bundles. A second CI check searches the bundle for the pipeline API base URL.

**When to revisit.** Move to a hosted mode only if one of these becomes true: you want to approve content from your phone or another computer; you want scheduled runs while your computer is off; or you share the pipeline with someone else. A hosted mode would need, at minimum:
1. A container host with a persistent volume (SQLite) or Postgres for checkpoints.
2. Authentication in front of the admin page and API (for example Cloudflare Access), plus rotating tokens.
3. A publisher that uses the GitHub API with a fine-scoped token instead of local git.
4. Secrets management for the OpenRouter key; request logging with redaction; rate limits.
5. A job queue and worker so long runs do not depend on a browser tab.
6. A production build flag (`PUBLIC_ENABLE_ADMIN`) and a protected `/admin` path.

All of that is deliberately out of scope now. The design keeps the seams for it: the API is already HTTP-only, the publisher is an interface with two implementations planned (local git worktree now, GitHub API later), and nothing reads the filesystem outside the data directory and the publish worktree.

---

## 4. Model layer: OpenRouter gateway

### 4.1 Why a gateway
Nodes never talk to a provider. They call a small interface, `LLM.text(...)`, `LLM.structured(schema, ...)` and `LLM.research(...)`. The OpenRouter implementation handles routing, retries, structured-output rules, cost tracking, budgets, and logging in one place. Tests inject a fake. A different backend can replace it later without touching graphs.

### 4.2 Client
- Use an OpenAI-compatible client pointed at OpenRouter's chat-completions endpoint, through LangChain's chat-model interface so LangGraph tooling keeps working. If a first-party LangChain OpenRouter integration is current at implementation time and exposes the OpenRouter-specific request fields below, prefer it. Either way the choice is hidden behind the `LLM` interface. *(verify)*
- OpenRouter-specific request fields used:
  - `provider.require_parameters: true` on every structured or tool request, so a request is only routed to endpoints that support the parameters it uses. OpenRouter's structured outputs are supported only by select models, which is why this matters.
  - `provider.allow_fallbacks` and the `models` fallback list so one flaky provider does not fail a run.
  - Optional `provider` data-policy preferences (for example excluding providers that train on prompts, or zero-data-retention only). Exposed as a setting.
- Handle the case where OpenRouter returns an error object inside an HTTP 200 response: treat it as a failure, not as empty output.

### 4.3 Model tiers and task mapping
Models are configured per **task**, not hard-coded. Defaults come from `config/models.yaml`. Overrides are saved from the UI into `data/settings.json`. A run can override per run and stores the exact models it used.

| Task | Tier | What it needs | Used by |
|---|---|---|---|
| `summarize`, `claims`, `seo`, `quiz_check_blind` | **fast** | Cheap, reliable structured output | ingest, claim extraction, SEO, quiz validation |
| `outline`, `structure_plan`, `quiz_generate` | **strong** | Reasoning, structured output | outline, roadmap structure, quizzes |
| `write`, `revise`, `apply_feedback`, `lesson_write` | **writer** | Long, high-quality prose | drafts and revisions |
| `critic`, `module_critic`, `consistency` | **critic** | Strong and *different from the writer's model* to avoid self-agreement | critique and consistency passes |
| `research` | **research** | Tool calling (web search) | research nodes |

- Recommended practice: use two or three distinct model families across writer, critic and fast tiers. The UI warns if writer and critic are the same model.
- The settings screen **does not hard-code model names**. The catalog is fetched live (see 4.4). Defaults in `models.yaml` are examples and are checked by `pipeline doctor`.

### 4.4 Model catalog and capability filter
- The pipeline caches OpenRouter's model list (refresh on demand, plus daily). Each entry includes pricing and the parameters it supports. *(verify exact field names)*
- Task-to-model pickers filter by capability:
  - Structured nodes list only models that support structured outputs / JSON schema.
  - The `research` task lists only models that support tool calling.
- The picker shows price per million input and output tokens, context length, and a "tested" badge for models that passed the pipeline's built-in smoke test.
- **Model smoke test** (button per model, small cost): runs one structured call with a representative schema and one long-form call, then reports validity, latency, tokens and cost. A model that fails structured output is marked unfit for structured tasks.

### 4.5 Structured output rules
1. Request `response_format` with a JSON schema and `provider.require_parameters: true`.
2. Validate with Pydantic. On failure, retry up to 2 times, feeding back the validation error. Then try the fallback model. Then fail the node with a readable error.
3. If a model produces fenced or wrapped JSON, strip and re-validate before counting it a failure.
4. Long free-form prose (articles, lessons) is requested as plain text, not JSON, so the model is not forced to escape a 2,000-word body.

### 4.6 Web research via OpenRouter's search tool
OpenRouter provides a `web_search` server tool (currently in beta). The model decides when to search; results come back as `url_citation` annotations. The tool takes parameters such as `max_results` (1 to 25), `allowed_domains`, `excluded_domains` and `max_uses`, and supports several engines. It requires a tool-calling model, and search is billed in addition to token costs. The older `:online` suffix and web plugin are deprecated, so use the server tool. *(verify current parameter names and engines)*

**How the pipeline uses it (and why it never trusts it):**
1. A **research call** gives a tool-calling model the topic and instructions, with `openrouter:web_search` enabled, `max_uses` capped per call, `allowed_domains` set when searching official docs, and `excluded_domains` set from a configurable low-quality list.
2. The pipeline harvests URLs from the **annotations**, not from the model's prose.
3. Each URL goes through the pipeline's **own fetcher** (§7.3), which enforces robots.txt, SSRF rules, size limits and content-type allowlists, and extracts the page text.
4. Only URLs that fetched successfully and have readable content become sources or resources. Everything else is dropped and logged.
5. A separate structured **curation call** classifies the verified pages. It sees fetched text or metadata, not the model's earlier claims.

This is why the pipeline uses its own fetcher rather than OpenRouter's web fetch tool: verification and politeness rules must be under the pipeline's control.

**Search engine choice** is a setting (default engine, or a bring-your-own-key engine if configured in OpenRouter). The PRD requires only that the `SearchTool` interface keep the engine swappable and that search cost appear in the run's cost.

### 4.7 Usage, cost and budgets
- OpenRouter returns usage with each response, including a cost figure. The gateway records per call: task, model actually used, input/output tokens, cost in dollars, latency, retries, and fallback used.
- A **cost meter** per run and per node is shown live in the UI and persisted.
- **Budgets:** default per-run cap (configurable, with separate defaults for blog and roadmap). At 80% the UI warns. At 100% the run **pauses** in state `paused_budget` (no new model calls, no data lost). Ben can raise the cap and resume.
- **Account guard:** the settings screen shows the remaining OpenRouter credit if retrievable, and the run refuses to start when it is below a configurable floor. *(verify the credits endpoint)*
- **Caching:** summaries, claims and fetched pages are cached by content hash, so a retry or a re-run with the same sources does not pay twice.
- **Free or rate-limited models:** retry with backoff honoring `Retry-After`, and surface "rate limited, waiting" as an event rather than failing.

---

## 5. Domain model

### 5.1 Core entities

| Entity | Fields (summary) |
|---|---|
| **Run** | `id`, `mode` (blog or roadmap), `topic`, `status`, `created/updated`, `settings_snapshot` (models, budgets, gates), `cost`, `error` |
| **Source** | `id` (S1…), `origin` (`supplied` or `researched`), `kind` (url, pdf, text), `title`, `url`, `text` (cleaned, capped), `summary`, `trust`, `flags` (injection), `fetched_at`, `content_hash` |
| **Claim** | `id`, `text`, `source_ids` |
| **Resource** (roadmaps) | `id`, `title`, `url`, `type` (docs, video, article, repo, interactive, book), `why`, `illustrated` (bool), `level`, `quality` (1 to 5), `verified` (bool), `origin` |
| **Outline** (blog) | `angle`, `working_title`, `sections[]` (id, heading, goal, claim_ids) |
| **RoadmapStructure** | roadmap metadata + `modules[]` (§7.2) |
| **ModuleDraft** | module metadata, `lesson_md`, `quiz[]`, `resources[]`, `source_ids`, `critique`, `gates[]`, `status`, `rounds` |
| **Decision** | human input at an interrupt (§9.5) |
| **GateResult** | `name`, `status` (pass, warn, fail), `detail`, `scope` (run or module) |
| **Event** | `t`, `node`, `level`, `msg`, optional `cost`, `model`, `module` |

### 5.2 Run status machine

```
queued → working → awaiting_outline | awaiting_structure
                 → awaiting_review (blog) | review_hub (roadmap)
                 → publishing → published | partially_published
        working → failed        (retry from checkpoint)
        working → paused_budget (raise cap, resume)
        any     → cancelled
        awaiting_* → rejected
```

`partially_published` is a roadmap with some modules live and others still drafts. A roadmap reaches `published` when every planned module is approved or explicitly dropped.

### 5.3 Contract with the site
All frontmatter is validated twice before any file is written: against Pydantic models in the pipeline and against the generated JSON Schema from `packages/content-schema`. The pipeline refuses to publish if either fails. A contract test builds the site against pipeline-produced fixtures.

---

## 6. Blog graph

The v0.1 graph is kept and extended. New in this version: an optional **research** step, OpenRouter gateway, cost-aware routing, and streaming events.

### 6.1 Flow

```
intake → ingest → [research_gaps?] → extract_claims → outline → outline_review ⟲(revise)
       → write → critique ⟲(revise, max N) → finalize(seo + gates)
       → human_review ──approve──▶ publish
            │changes → apply_feedback → recheck → finalize → human_review
            │reject → END
            └ blocked (hard gate) → human_review
```

### 6.2 Nodes

| Node | Purpose | Task / tier | Inputs → outputs | Failure handling |
|---|---|---|---|---|
| `intake` | Validate request, snapshot settings | none | request → state | Reject invalid input early with clear message |
| `ingest` | Fetch URLs, read PDFs, clean text, scan for instruction-like text, summarize | fast | sources → `Source[]` | A source that fails is skipped and logged; run fails only if none remain |
| `research_gaps` *(optional, per-run toggle)* | Find supporting material for thin areas Ben flagged or the claim extractor found uncovered | research | topic + gaps → `Source[]` (origin `researched`) | Only verified fetches kept; budget-capped |
| `extract_claims` | Atomic claims mapped to sources | fast | sources → `Claim[]` | Drops claims with unknown source ids |
| `outline` | Angle plus sections mapped to claims | strong | claims + Ben's notes → `Outline` | Retry with validation feedback |
| `outline_review` | **Interrupt:** approve, edit, or request changes | n/a | outline → decision | Optional per run |
| `write` | Draft in Ben's voice from claims only | writer | outline + claims + sources → markdown | Fenced output stripped |
| `critique` | Score the draft, list issues and unsupported statements | critic | draft + claims → `Critique` | Counts a pass when avg ≥ 4, min ≥ 3, no high-severity unsupported claims |
| `revise` | Fix issues | writer | draft + critique → draft | Capped at `max_auto_revisions` |
| `finalize` | SEO metadata, deterministic gates | fast + code | draft → `SEOPackage`, `GateResult[]` | Metadata validated against schema |
| `human_review` | **Interrupt:** approve, comment, edit, reject | n/a | draft + gates → decision | Hard gates block approval |
| `apply_feedback` | Apply comments minimally; Ben's direct edits always win | writer | draft + decision → draft | |
| `recheck` | Re-run the critic after human changes | critic | draft → `Critique` | |
| `publish` | Render, validate, commit (§10) | none | state → commit | Errors leave the run at review with a retry |

### 6.3 Routing rules
- After `critique`: pass or revision cap reached → `finalize`; else → `revise`.
- After `human_review`: `reject` → end; `changes` → `apply_feedback`; `approve` with a hard gate failing (schema or citations) → `blocked` then back to `human_review`; `approve` with other failing gates → requires explicit "publish anyway"; otherwise → `publish`.
- Interrupt nodes contain no model calls before `interrupt()`, because LangGraph re-runs a node from the top when it resumes.

### 6.4 Blog output contract
Markdown body starting at `##`; `[S#]` markers renumbered by first citation into numbered links to the Sources section; frontmatter per `02-prd-astro-blog-site.md` §4.1 including `sources`, `aiAssisted`, `pipelineRunId`. A source without a URL cannot be cited in a published post.

---

## 7. Roadmap graph

A roadmap is a planned sequence of modules; each module is a lesson plus a quiz. Generation happens in phases, with a human checkpoint after the structure and a review hub for modules.

### 7.1 Flow

```
PARENT GRAPH
 intake → seed_sources → landscape_research → plan_structure → structure_review ⟲(revise)
        → generate_modules (fan-out, concurrency 3) ──▶ [MODULE SUBGRAPH × N]
        → consistency_pass → review_hub ⟲ (one decision at a time) → done

MODULE SUBGRAPH (per module)
 module_research → curate_resources → plan_lesson → write_lesson → code_checks
   → generate_quiz → validate_quiz ⟲(fix) → module_critic ⟲(revise, max N) → module_gates → ready_for_review
```

### 7.2 Inputs and the structure object
**Inputs (new-roadmap form):** subject; target level; **official documentation URLs** (one or more, with optional labels); optional per-topic hints; optional outline Ben already has; preferred depth (modules count range); research toggle and domain preferences (allow and exclude lists); budget cap.

**`RoadmapStructure`:**
```
roadmap: { title, description (≤160), level, estimatedHours, prerequisites[], outcomes[≥3], tags[] }
modules[]: { slug, order, title, objectives[≥2], prerequisites[] (module slugs or external text),
             estimatedMinutes, key_topics[], docs_hints[] (URLs or doc section names), phase }
```
Slugs and order are fixed once the structure is approved. Later modules therefore slot into the public roadmap in the right place.

### 7.3 Phase A: planning (parent graph)

| Node | Purpose | Notes |
|---|---|---|
| `intake` | Validate inputs, snapshot settings, create the roadmap id and slug | |
| `seed_sources` | Fetch Ben's official docs URLs with the verified fetcher; follow same-domain links one level deep (bounded, configurable) to map the docs' table of contents | Produces `Source[]` (origin supplied) and a **docs map** (titles and URLs) that later steps search within |
| `landscape_research` | Research call: what do existing curricula and roadmaps cover, in what order, for this subject at this level? Uses web search, harvest from annotations, verify by fetching | Output feeds gaps and ordering only. Nothing from it is copied |
| `plan_structure` | Propose phases and modules with objectives, prerequisites, time, key topics, docs hints. Must cite which docs sections each module draws on | Strong model; validated for acyclic prerequisites and coverage of every roadmap outcome |
| `structure_review` | **Interrupt:** Ben edits titles, objectives, order, adds or removes modules, or asks for changes | Drag-to-reorder in the UI (§9.4). Revise loops back to `plan_structure` with Ben's notes |

### 7.4 Phase B: per-module generation (subgraph)

| Node | Purpose | Task / tier | Detail |
|---|---|---|---|
| `module_research` | Gather **official** material for this module | research + code | (1) Find relevant pages inside the docs map by topic match. (2) If the docs map is thin, run a research call restricted with `allowed_domains` to the supplied docs domains. (3) Fetch with the verified fetcher; keep the best N pages by relevance and size. Output: module `Source[]` (S-ids local to the module) |
| `curate_resources` | Find **well-illustrated, curated** learning resources to link | research + fast | Research call, unrestricted except the exclude list, instructed to prefer visual explainers, diagrams, interactive demos, official tutorials, well-regarded talks, and repos with clear READMEs. Harvest annotation URLs, **verify by fetching** (status, readable content or metadata), then a structured curation call classifies each as `docs / video / article / repo / interactive / book`, sets `illustrated`, `level`, `quality` and writes a one-line `why`. Keep the top 3 to 6 |
| `plan_lesson` | Turn objectives and sources into a lesson plan | strong | Maps each section to claims; reuses the roadmap **glossary** and a summary of earlier modules so terms and depth stay consistent |
| `write_lesson` | Write the lesson | writer | Fixed teaching shape: why it matters, concept, worked example, common mistakes, short practice, recap. Cites official sources `[S#]`. Paraphrases. No invented APIs or versions |
| `code_checks` | Check code samples | code | v1: syntax checks (Python via `ast`, JS/TS via a parser) and tag checks. v2: run in a sandbox with no network |
| `generate_quiz` | 5 to 8 questions mapped to objectives | strong | Mix of difficulty, plausible distractors, explanations that teach, optional hints |
| `validate_quiz` | Deterministic and blind-solve validation (§8.3) | code + fast | Failing questions are regenerated individually, max 2 rounds |
| `module_critic` | Score accuracy vs sources, objective coverage, progression, redundancy, reading level | critic | Auto-revision capped |
| `module_gates` | Run module gates (§8.2) | code | |
| `ready_for_review` | Mark the module `needs_review` | | Returns control to the parent |

**Resource rules (hard):** a resource appears in a module only if (a) Ben supplied it, or (b) it was returned by search **and** fetched successfully. Resources are linked, never copied, and each has a short original `why`. Video links that cannot be text-verified are labelled "metadata only" so Ben can eyeball them in review.

### 7.5 Cross-module consistency (`consistency_pass`)
Runs once after all first drafts exist.
- Builds a **glossary** of terms and checks that each is defined at first use and used consistently.
- Detects duplicated explanations across modules (shingle overlap) and prerequisite violations (a module uses a concept introduced later).
- Checks that every roadmap outcome is covered by at least one module's objectives.
- Produces targeted **fix tasks** (module, issue, fix). Each runs through `Send` as a focused revision of just that module, followed by a light re-critique.
- Anything the pass cannot fix is attached to the module as a review note.

### 7.6 Review hub (module by module)
Several modules can finish at once, so the graph uses **one interrupt at a time** to avoid parallel interrupts.

- `review_hub` waits for a decision about **one module**. It then handles it and returns to waiting.
- Decisions per module: `approve`, `changes` (comments and/or Ben's direct edits), `regenerate` (fresh draft, optional new instructions), `drop` (remove from the plan), plus roadmap-level `edit_structure` (reorder, rename, add) and `close` (end the run, leaving unreviewed modules as drafts).
- `approve` → `publish_module` runs immediately (commit, §10). Other modules keep waiting.
- `changes` → targeted rework of that module only (feedback → recheck → gates), then back to the hub.
- The roadmap is `partially_published` after the first approval. It is `published` when every planned module is approved or dropped.
- Optional **lazy mode** (setting): generate modules one at a time in order so that approved modules inform later ones. Default is parallel (faster); lazy mode is better when a roadmap must be tightly sequential and cost matters.

### 7.7 Publishing semantics for roadmaps

| Event | What is committed |
|---|---|
| First module approved | Roadmap `index.md` (status `in-progress`, with the `planned` module list) **and** that module file |
| Another module approved | That module file, plus an updated `index.md` (shorter `planned` list, `lastReviewed` date) |
| Last module approved | Final `index.md` with `status: complete` and a version bump |
| Module changed after approval | Not through this flow in v1 (refresh mode, §14) |

Unapproved modules are **never in the repo**, so a half-finished module cannot leak. The site shows planned-but-unpublished modules as "coming soon" (site change SC-1). Every commit is one logical change with a clear message.

### 7.8 Roadmap output contract
Module frontmatter extends the site schema: `title, order, estimatedMinutes, objectives, resources[{title,url,type,why?,illustrated?}], sources[]` (official sources used, rendered as a numbered list), `quiz[]` as in the site schema, `lastReviewed, draft, pipelineRunId`. Roadmap `index.md` adds `status` and `planned[]`. Required site changes are in §9.9.

---

## 8. Quality gates and evaluation

### 8.1 Blog gates (carried over, tightened)
Schema; citations (all `[S#]` known, all cited sources have URLs); section coverage; unsupported claims (critic); similarity to sources (8-word shingles, default limit 18%); quote length (≤ 15 words, ≤ 1 per source); filler phrases; length; structure (no H1, ≥ 2 H2, code fences tagged); source safety (instruction-like text flagged); links reachable. **Hard gates (cannot be overridden):** schema, citations. Others fail or warn, and a fail needs an explicit "publish anyway".

### 8.2 Module gates
| Gate | Rule | Level |
|---|---|---|
| schema | Module frontmatter validates (Pydantic and JSON Schema) | hard |
| objective coverage | Every objective is addressed in the lesson (critic with evidence) | fail |
| source grounding | Every factual paragraph cites an official source; unsupported claims flagged | fail if ≥ 3 |
| similarity | Overlap with each source under the limit; no copied doc passages | fail |
| code | Code blocks parse; language tagged; no obviously broken snippets | fail |
| resources | ≥ 1 official doc linked; 3 to 6 total resources; every URL verified; at most 1 "metadata only" | hard for verification |
| quiz | See 8.3 | hard for integrity |
| length and reading level | Within module time estimate and level | warn |
| progression | Uses no concept first introduced in a later module (consistency pass) | warn |
| injection | Source text flagged for instruction-like content | warn |

### 8.3 Quiz validation
**Deterministic (hard):** every `correct` id exists among options; no duplicate options; `single` has exactly one correct, `multi` has at least two and at most n−1; 3 to 6 options; no "all/none of the above"; the correct option is not always the longest; correct-option positions are not clustered; every question maps to an objective; explanation present and not a restatement of the answer.

**Blind-solve (LLM, fast model):**
1. A model answers each question **without** the lesson. If it answers correctly with high confidence, the question tests common knowledge or has a giveaway, so it is flagged.
2. A model answers **with** the lesson. If it answers wrong, the question is ambiguous or the lesson does not support it, so it is flagged.
3. Flagged questions are regenerated individually (max 2 rounds), then surfaced to Ben with the reason.

### 8.4 Evals
- **Golden set:** 10 blog topics and 3 roadmap subjects with fixed sources and Ben-approved reference outputs, stored in `apps/pipeline/evals/`.
- **Metrics:** unsupported-claim rate, similarity, rubric scores, quiz validity rate, resource verification rate, revision rounds to approval, cost, latency.
- **`pipeline eval`** runs the set against the current prompts and models and writes a report. It is opt-in because it spends money, and it warns with an estimated cost first.
- **Model comparison (`pipeline compare` and the UI):** run one request on 2 to 3 model configurations, show outputs side by side with scores, cost and time. This is the feature that proves "switchable models" is real.

---

## 9. Admin UI

### 9.1 Principles
One reserved route, one purpose: supervise runs, make decisions, see cost. It must be fast to review in, safe to click, and obvious about what is live. It uses the site's own design system, but in the calm scene (solid panels, no shader).

### 9.2 Information architecture
`/admin/` (single route, in-page views, URL hash for deep links):

| View | Purpose |
|---|---|
| **Connect** | Token and API address; `doctor` checks (key, git, worktree, schema, Node/Python) |
| **Runs** | List with status chips, cost, updated time; filters (mode, status); **New run** (blog or roadmap) |
| **Blog run** | Activity, checkpoints, review tabs, publish (existing, upgraded) |
| **Roadmap workspace** | Structure board, module cards, per-module review, publishing state |
| **Library** | What is published (read from the repo) with links, commit ids, review dates; **Revert** a publish |
| **Settings** | Models per task, budgets, search preferences, gates thresholds, publish mode, voice file editor |
| **Compare** | Run one request across model configurations |

A persistent header strip shows API status, current OpenRouter credit (if available), today's spend, and the active publish mode (`git → main` or `files only`), so there is never doubt about what Approve does.

### 9.3 New-run forms
- **Blog:** topic, audience, angle, length, notes (only source of first-person claims), sources (URL / pasted text with optional URL and title), research toggle, outline checkpoint toggle, model overrides, budget cap, estimated cost range shown before start.
- **Roadmap:** subject, level, **official docs URLs** (repeater with labels), topic hints, optional existing outline, module count range, research toggle with allow/exclude domain lists, concurrency, lazy vs parallel generation, budget cap, estimated cost range.

### 9.4 Roadmap workspace
Three panes:

1. **Structure board (Checkpoint A):** modules as cards in phases, drag to reorder, inline edit title, objectives, minutes, prerequisites, docs hints; add or remove modules; "ask for changes" note regenerates the plan. A diagram of prerequisite links highlights cycles.
2. **Module grid (after approval of the structure):** one card per module showing state (`queued, researching, writing, quiz, critiquing, needs review, changes requested, approved and live, failed, dropped`), progress bar by node, cost, gate summary. Click to open.
3. **Module review:** tabs *Lesson* (rendered, with an edit-markdown mode), *Sources*, *Resources* (each with the `why`, a "verified" tick, an "illustrated" tag, open-link button, and remove/replace controls), *Quiz* (rendered as the reader sees it, plus the blind-solve results and per-question regenerate), *Checks* (gates and critic), *Diff*. Review bar actions: **Approve and publish this module**, request changes (comments and/or direct edits), regenerate, drop.

A roadmap-level header shows: modules live / total, cost to date, last commit, the public URL, and **Close roadmap** (leave remaining drafts).

### 9.5 Decisions the UI sends (resume payloads)
```
blog outline:      { action: approve|revise, comments[], outline? }
blog review:       { action: approve|changes|reject, comments[], edited_md?, seo?, force? }
roadmap structure: { action: approve|revise, comments[], structure? }
roadmap hub:       { module, action: approve|changes|regenerate|drop,
                     comments[], edited_md?, edited_quiz?, resources_edit?, force? }
                   | { action: edit_structure, structure } | { action: close }
```
Ben's direct edits (markdown, quiz, resources, metadata) are authoritative and are re-validated and re-gated before publish is possible.

### 9.6 Live graph and activity
- A **graph view** draws the active graph (parent and module subgraph) from the compiled LangGraph structure, colored by node state (idle, running, done, failed, waiting for you). Clicking a node shows its inputs, outputs, model, tokens, cost and duration.
- An **activity log** streams events as they happen. Search-result and fetch events show the URL and verdict (kept or dropped, and why).
- Updates arrive over **Server-Sent Events** from `GET /runs/{id}/stream`, with automatic fallback to polling. Streaming comes from LangGraph's stream modes feeding an in-process event bus; the same events are persisted for replay.

### 9.7 Settings
- **Models:** one picker per task with capability filtering, price, "smoke test" button, fallback chain editor, and a warning when writer = critic.
- **Budgets:** per-run default caps, warning threshold, credit floor.
- **Research:** default engine, max results, `max_uses`, allow and exclude lists (a sensible default exclude list for low-quality aggregators), fetch limits.
- **Gates:** similarity limit, auto-revision cap, outline checkpoint default.
- **Publishing:** mode (git to `main` or files only), branch, remote, commit message prefix. A "test publish" writes to a temp branch-less dry run and shows the diff without committing.
- **Voice:** edit `voice/ben.md` and the banned-phrase list in the browser (saved to disk).
- **Import/export** settings as JSON.

### 9.8 API contract

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness (no auth) |
| `GET /doctor` | Environment checks |
| `GET /config` | Non-secret effective config |
| `GET/PUT /settings` | Models, budgets, research, gates, publishing |
| `GET /models?refresh=1` | Cached OpenRouter catalog with capability flags |
| `POST /models/{id}/smoke` | Run the model smoke test |
| `GET /credits` | Remaining OpenRouter credit (if retrievable) |
| `POST /runs` (blog or roadmap) | Start a run; returns an id and an estimated cost range |
| `GET /runs`, `GET /runs/{id}` | List and detail projections |
| `GET /runs/{id}/stream` | SSE events and status snapshots |
| `GET /runs/{id}/graph` | Graph structure plus node states |
| `POST /runs/{id}/resume` | Send a decision (validated against the pending interrupt type) |
| `POST /runs/{id}/retry` | Continue from the last checkpoint |
| `POST /runs/{id}/cancel` | Cooperative cancel (checked between nodes) |
| `POST /runs/{id}/budget` | Raise the cap and resume from `paused_budget` |
| `DELETE /runs/{id}` | Delete run and checkpoints |
| `GET /library` | Published items read from the repo with commit ids |
| `POST /library/revert` | `git revert` a publish commit through the worktree |
| `POST /compare` | Start a multi-model comparison |

Projections never include full source text (excerpts only), never include secrets, and render markdown to HTML on the server with raw HTML disabled.

### 9.9 Required site changes (small, scoped)

| ID | Change | Why |
|---|---|---|
| SC-1 | Roadmap schema: `status` (`in-progress` or `complete`) and `planned[]` (`slug, title, estimatedMinutes`). Roadmap overview shows planned modules as locked "coming soon" items in the git-graph | Module-by-module go-live |
| SC-2 | Module schema: add `sources[]`; render with the existing Sources list and numbered inline citations | Lessons cite official docs |
| SC-3 | Module `resources[]`: add `why` and `illustrated`, and a new type `interactive`; show a small "illustrated" badge | Curated resources |
| SC-4 | `getStaticPaths` guard for `/admin/` plus the two CI checks from §3.4 | Keep admin out of production |
| SC-5 | Replace `src/content.config.ts` schemas with imports from `@benki/content-schema` | One contract |

---

## 10. Publishing

### 10.1 What is written
- **Blog:** `apps/site/src/content/blog/<slug>.md`.
- **Roadmap:** `apps/site/src/content/roadmaps/<roadmap>/index.md` and `.../modules/<NN-slug>.md`.
- Frontmatter is rendered with a YAML emitter, validated against both schemas, and a source without a URL cannot be cited.

### 10.2 Citation handling
`[S#]` markers are renumbered by first use into numbered links to the Sources section. The published `sources` list contains only sources actually cited, in citation order.

### 10.3 Collision and idempotency
A file is only overwritten if its `pipelineRunId` equals the current run's id (republish after a fix). Otherwise the pipeline refuses and asks for a different slug. Publishing is idempotent: a retry after a push failure never creates duplicate commits.

### 10.4 Git strategy: a dedicated worktree
The v0.1 publisher pulled and wrote in the site working tree. In a monorepo where Ben is also editing code, that is fragile. v2 uses a **managed worktree**:
1. `git fetch origin main`.
2. Keep a **detached** worktree at `apps/pipeline/data/publish-worktree`, reset to `origin/main` before every publish. Detached HEAD avoids the git rule that one branch cannot be checked out in two worktrees.
3. Write the file(s) there, `git add` only those paths, commit with `content: <title>` (or `content(roadmap): <module>`).
4. `git push origin HEAD:main`. If rejected because `main` moved, fetch, rebase the single commit, and retry up to 3 times. On final failure keep the commit and show the exact error with a retry button.
5. Ben's working tree and index are never read or modified.

Safety rails: publish mode `files` (writes into the worktree and shows the diff without committing) for dry runs; the confirm dialog always states "commits to `main` and goes live"; a global kill-switch setting disables pushing.

### 10.5 After publish
- The commit id and live URL are shown. An optional check polls the live URL for up to a few minutes and marks the item "live" when it responds.
- **Revert** (Library): creates a `git revert` commit on `main` through the same worktree. It is the rollback path for a bad publish.

---

## 11. Security, privacy and safety

| Area | Requirement |
|---|---|
| Prompt injection | Source text, search results and fetched pages are untrusted data. They are always wrapped in delimited tags with a standing instruction to treat them as data. The ingest step flags instruction-like patterns. Nodes that write or publish get no tools beyond their role. Flags are shown at review. |
| Search results | The model's prose about search results is never used as a source. Only fetched, verified page content is. |
| SSRF | Fetcher blocks non-http(s), loopback, private, link-local and metadata addresses (after DNS resolution and after redirects). A test suite includes known bypass shapes. |
| Politeness | robots.txt honored, identified user agent, per-host rate limit, size caps (3 MB default), content-type allowlist. |
| Secrets | OpenRouter key and admin token only in `.env`. Redacted in logs. Never in the browser, prompts, run exports, or committed files. A pre-commit check blocks them. |
| Local API | Loopback bind, token, Host check, strict CORS (RT-1 to RT-3). |
| Output safety | Published content is plain Markdown. Raw HTML, scripts and unknown MDX components are rejected by a lint step. Admin previews render with raw HTML disabled. |
| Copyright | Paraphrase fully; quotes ≤ 15 words and rare; similarity gate; resources linked, never copied; attribution via sources. |
| Data policy | A setting restricts routing to providers with acceptable data policies. A per-run flag marks material as private so it is not sent to providers outside that policy. |
| Cost safety | Hard caps, credit floor, and an obvious per-run meter. |

---

## 12. Testing strategy

| Layer | Approach |
|---|---|
| Unit | Slugging, citation renumbering, shingle similarity, quiz integrity checks, quote policy, SSRF guard, budget math |
| Node tests | Fake `LLM` returning fixtures; recorded OpenRouter responses (including error-in-200 and fallback cases) |
| Graph tests | Full blog and roadmap runs with the fake LLM: outline loop, auto-revision, human changes, hard-gate blocking, module hub with approve/changes/regenerate/drop, partial publish, resume after restart |
| Contract tests | Pipeline-produced fixtures validate against `content-schema` JSON Schema, then the site builds with them in CI |
| API tests | Auth, Host and CORS, resume validation, SSE ordering, cancel, budget pause and resume |
| Publisher tests | Temp bare remote + clone: worktree reset, push race (rebase retry), revert, files mode, dirty working tree untouched |
| Security tests | Injection fixtures must not change behavior; private-IP and redirect fetch cases blocked |
| UI tests | Playwright against the dev site and a fake API: connect, new run, structure edit, module approve, publish confirm, error states |
| Eval suite | Golden set (§8.4), opt-in |
| Live smoke | One opt-in test with a real OpenRouter key and a tiny budget: structured call, tool call, search, cost accounting |

---

## 13. Implementation plan

| Milestone | Scope | Exit criteria | Est. |
|---|---|---|---|
| **M0 Monorepo** | Move into `apps/site`, `apps/pipeline`, `packages/content-schema`; workspace scripts; Cloudflare build and watch paths; CI guard SC-4/SC-5 | `pnpm setup`, `pnpm dev` and `pnpm build` work; deploy still green | 1–2 d |
| **M1 Gateway** | OpenRouter client, tiers, fallbacks, capability filter, usage and cost, budgets and pause, model catalog and smoke test, settings storage | Same blog run works on two different models; cost shown in dollars | 2–3 d |
| **M2 Publisher v2** | Detached worktree, push-race retry, revert, files/dry-run mode, collision rules | Publisher tests green; working tree untouched in tests | 1 d |
| **M3 Blog v2** | Research-gaps node with verified fetching, SSE events, cancel/retry polish, cost per node, admin shell (header strip, settings, library, connect + doctor) | Blog run end to end with research; streamed activity; library lists live posts | 3–4 d |
| **M4 Roadmap graph** | Planning phase, structure checkpoint, module subgraph (research, curation, lesson, quiz, critic), consistency pass, review hub, module publish | Fake-LLM graph tests green; one real roadmap generates | 5–7 d |
| **M5 Roadmap UI and site** | Structure board, module grid and review, resources tab, SC-1 to SC-3 | Approve a module → it appears on the live site while others stay hidden | 4–5 d |
| **M6 Quality** | Quiz blind-solve, evals, compare view, graph view, security tests | Eval report for ≥ 10 runs; compare UI works | 3–5 d |
| **M7 Showcase** | README with architecture diagram, demo video, docs for `pnpm setup` and day-to-day use | A newcomer can run it from the README | 2 d |

Total roughly 21 to 29 working days of focused effort. Ship in order, and stop after any milestone with a working system. M0 to M3 gives a stronger blog pipeline on its own.

---

## 14. Risks, open questions, and later work

### 14.1 Risks

| Risk | Mitigation |
|---|---|
| Models differ in structured-output support and quality | `require_parameters`, capability filter, smoke tests, validation retries, fallbacks, per-task selection |
| Search results are noisy or low quality | Exclude list, verification by fetching, curation scoring, Ben's review of every resource, fewer but better links |
| Hallucinated or stale technical facts in lessons | Official-docs grounding, critic from a different model, version pinning in prompts, code checks, mandatory review |
| Cost surprises, especially roadmaps (many modules, many searches) | Estimates before start, per-run caps, caching, lazy mode, `max_uses` on search |
| Pipeline commits racing with Ben's own pushes | Worktree plus fetch/rebase retry; commits touch only content paths |
| A bad publish goes live | Hard gates, confirm dialog, one-click revert |
| OpenRouter beta features change (server tools) | Isolated behind `SearchTool`; contract tests; the engine and parameters are settings |
| Scope | Milestones are independent; M0 to M3 is already valuable |
| Time conflict with the flagship project | Pause after any milestone; nothing depends on later ones |

### 14.2 Open questions
1. Which OpenRouter models become the defaults for each tier? Decide after the M1 smoke tests, using real cost and quality numbers.
2. Default web search engine, and whether to set a bring-your-own-key engine in OpenRouter.
3. Default exclude list for low-quality domains (start small, grow from experience).
4. Should `planned` modules on the public roadmap be shown at all, or only after the structure is final? (SC-1 assumes shown as "coming soon".)
5. Voice samples: which 3 to 5 pieces of your writing seed `voice/ben.md`?

### 14.3 Later work (not in this version)
- **Refresh mode:** re-check published posts and modules for stale facts and versions, propose diffs for review.
- **Hosted mode:** the blueprint in §3.4.
- Sandboxed execution of code samples.
- Topic suggester from feeds you choose, where you pick what to run.
- An MCP server exposing "draft", "approve" and "publish" so other tools can drive the pipeline.
- Local PDF upload in the UI.

---

## Appendix A: Environment and configuration

`apps/pipeline/.env.example`
```
ADMIN_TOKEN=                      # generated on first `pipeline serve`
OPENROUTER_API_KEY=
OPENROUTER_APP_URL=http://localhost:4321   # optional attribution headers
GIT_REMOTE=origin
GIT_BRANCH=main
PUBLISH_MODE=git                  # git | files
```

`apps/pipeline/config/models.yaml` (example shape; model ids are chosen in the UI)
```
tasks:
  summarize:   { model: "<fast-model-id>",    fallbacks: ["<fast-fallback>"] }
  claims:      { model: "<fast-model-id>" }
  outline:     { model: "<strong-model-id>" }
  write:       { model: "<writer-model-id>",  temperature: 0.7 }
  critic:      { model: "<other-family-id>",  temperature: 0.2 }
  research:    { model: "<tool-calling-id>" }
budgets:       { blog_usd: 1.00, roadmap_usd: 8.00, warn_at: 0.8, credit_floor_usd: 2.00 }
research:      { engine: default, max_results: 6, max_uses: 6, exclude_domains: [] }
gates:         { max_similarity: 0.18, max_auto_revisions: 2 }
```

## Appendix B: Example roadmap run, start to live

1. Ben starts a roadmap: "LangGraph for AI engineers", level beginner, docs URL = the LangGraph docs.
2. The pipeline maps the docs, researches existing curricula, and proposes 8 modules in 3 phases. Ben drags module 5 before 4, edits two objectives, approves the structure. (Cost so far: shown.)
3. Modules generate in parallel (3 at a time). Each finds official pages, curates 4 to 5 verified resources, writes the lesson, builds and validates the quiz, and passes the critic.
4. The consistency pass fixes a term used before its definition in module 3 and a duplicated explanation in module 6.
5. In the hub, Ben approves module 1. A commit adds `index.md` (in progress, 7 planned) and `01-state-and-nodes.md`. The live roadmap shows one module and seven "coming soon" items.
6. Ben requests changes on module 2 ("shorter intro, add a warning about X"). Only that module is reworked and returns for review.
7. Over a few days he approves the rest. The last approval flips the roadmap to `complete`.
