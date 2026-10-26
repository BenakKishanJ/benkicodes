# 03. PRD: Content Pipeline (LangGraph, lean edition)

**Version:** 2.0 · **Date:** 26 Oct 2026 · **Owner:** Ben · **Status:** Draft for review
**Companions:** `01-marketing-seo-strategy.md`, `02-prd-blog-site.md`
**Supersedes:** the earlier pipeline PRDs. **Builds on:** the delivered v0.1 blog pipeline (FastAPI + LangGraph + admin page).

> **The one rule of this version: keep it lean.** Fewer model calls means fewer tokens and lower cost. Use code where code works (fetching, validating, git, gates). Use a model only where judgment or writing is needed. Add agents later only when real use shows a need.

---

## 1. Overview

### 1.1 Purpose
A local, human-supervised system that produces two kinds of content for the site:
1. **Blog posts:** from sources you choose, written by a model, reviewed by you, published on approval.
2. **Hands-on roadmaps (courses):** a guided project built part by part. The agent **writes the project code** in a GitHub repo with proper commits and tags, then writes each lesson from the real diffs. You review the code and the lesson for every part before it goes live.

### 1.2 Decisions

| Topic | Decision |
|---|---|
| Repo | pnpm monorepo: `apps/site`, `apps/pipeline`, `packages/content-schema`. **Course project repos are separate GitHub repos** (outside the monorepo) |
| Runs where | Only on your computer. Pipeline and admin page are never deployed |
| Models | OpenRouter, one model chosen per task, switchable in the admin page |
| Blog flow | 3 model calls: plan, write, check. You review. Approve commits to `main` |
| Course flow | Plan once, then one part at a time: code → your code review → lesson → your lesson review → publish |
| Code in lessons | Taken from the project repo by line range at a tag. The model never types lesson code from memory |
| Grounding | Blogs: sources you supply. Courses: official docs URLs you supply + web research for curated references, all verified by fetching |
| Go-live | Part by part. A part goes live when approved. Unfinished parts do not exist in any repo |
| Launch scope | 4 to 5 blogs + 1 flagship course (LangGraph deep-research agent, 6 parts) |
| Later (post-launch) | Blog idea scout, course idea scout (lean designs in §8) |

### 1.3 Goals

| # | Goal | Measure |
|---|---|---|
| G1 | Cheap to run | Blog ≤ 3 base model calls; course part ≤ 4 base calls; cost shown live and capped |
| G2 | Drafts you can approve with light edits | ≥ 70% of blog drafts approved within 2 rounds; ≥ 60% of parts within 2 rounds |
| G3 | Course code that runs | Every published tag passes the repo's tests in CI |
| G4 | Nothing unverified goes live | Every cited source and link was fetched successfully by the pipeline |
| G5 | Easy to switch models | Change any task's model in the UI in under 30 seconds |
| G6 | Durable | A run survives a crash; resume from the last checkpoint |

### 1.4 Non-goals (this version)
Hosting the pipeline; accounts or multi-user; parallel agents, subgraph fan-out, or self-directed autonomous agents; sandboxed auto-run of generated code (a Docker option comes later); a CLI verifier, submissions or certificates for learners; image generation; editing already-published content (refresh mode later).

### 1.5 Principles
1. **Human decides what goes live.** Every blog and every part is approved by you.
2. **Code over model.** Fetching, validating, diffing, tagging, publishing are plain code.
3. **Ground it or leave it out.** Facts come from sources. Lesson code comes from the repo.
4. **Verify, don't trust.** Search results, pages and model output are untrusted input.
5. **One thing at a time.** One run per piece, one part at a time, sequential.
6. **Cost is visible and capped.**

---

## 2. Lean design: where the model is (and is not) used

### 2.1 Model-call budget

| Workflow | Model calls (base) | Plain code |
|---|---|---|
| **Blog** | `plan`, `write`, `check` (**3**). Extras only on request: auto-revise ≤ 1; each review round with comments adds `apply_feedback` + `check` | intake, ingest (fetch/clean/inject-scan), gates, publish |
| **Course planning** | `research` (1 to 2, with web search), `plan` (1) | docs mapping, URL verification, repo init |
| **Course part** | `code` (1; + up to 2 fixes), `lesson` (1), `quiz` (1, cheap model), `check` (1) (**4**) | apply edits, git, tests runner, snippet expansion, gates, two-repo publish |

### 2.2 Rough token budget (for planning, not billing)

| Item | Input tokens | Output tokens |
|---|---|---|
| Blog (5 sources of about 12k characters) | about 60 to 70k across 3 calls | about 5 to 6k |
| Course planning | about 30 to 50k | about 6 to 8k |
| One course part | about 80 to 100k across 4 calls (repo context + diffs + docs) | about 12 to 16k |
| A 6-part course | about 0.5 to 0.7M | about 80 to 100k |

Multiply by the per-token prices of the models you choose (OpenRouter shows them). The admin page shows real dollars from OpenRouter's usage data. *(Treat these as estimates; measure on your first runs.)*

### 2.3 Where the "intelligence" comes from (without many agents)
- **Plans before prose:** a structured plan (outline or course spec) you approve before the expensive calls.
- **Different model as checker:** `check` uses a different model family than `write`.
- **Tools plus verification:** search finds candidates, **our fetcher** verifies them.
- **Grounded code and quotes:** snippets and file contents come from git, not memory.
- **Memory that matters:** the course keeps a short running summary and glossary passed to the next part; the idea scouts remember what you accepted or rejected.
- **Asking you when stuck:** missing sources, failing checks, and unclear choices become questions in the UI rather than guesses.
- **Evals later:** a small golden set to tell whether a prompt or model change helped.

---

## 3. Repositories, workspace, and runtime

### 3.1 Repositories

| Repo | Contents | Where it lives |
|---|---|---|
| **Site monorepo** (`benki`) | `apps/site`, `apps/pipeline`, `packages/content-schema` | GitHub; Cloudflare Pages deploys `apps/site` |
| **Course project repo** (one per course, e.g. `langgraph-deep-research`) | The guided project, tagged per part, with CI | GitHub (public); local clone at `COURSES_DIR/<name>` outside the monorepo |

Course repos stay separate so learners can fork or use them as a template, and so their history is clean and independent of the site.

### 3.2 Pipeline package layout (`apps/pipeline`)

```
apps/pipeline/
├─ package.json                    # wrapper: dev, test, setup (run uv)
├─ pyproject.toml  uv.lock
├─ .env.example                    # OPENROUTER_API_KEY, ADMIN_TOKEN, paths
├─ config/
│  ├─ models.yaml                  # task → model + fallbacks + params
│  ├─ settings.default.yaml        # budgets, gates, paths, publish mode
│  └─ feeds.yaml                   # idea-scout feeds (post-launch)
├─ prompts/                        # versioned prompt templates (markdown with variables)
│  ├─ blog_plan.md  blog_write.md  blog_check.md  blog_revise.md  blog_feedback.md
│  ├─ course_research.md  course_plan.md  code_step.md  code_fix.md
│  ├─ lesson.md  quiz.md  lesson_check.md
│  └─ scout_blog.md  scout_course.md
├─ voice/  ben.md  banned.txt
├─ templates/course-repo/          # scaffold for every course repo
│  ├─ README.md.tmpl  LICENSE  .gitignore  pyproject.toml.tmpl
│  ├─ .github/workflows/ci.yml
│  ├─ src/PACKAGE/__init__.py  tests/test_smoke.py
│  └─ docs/ARCHITECTURE.md  docs/PARTS.md
├─ src/pipeline/
│  ├─ cli.py  config.py  store.py  state.py
│  ├─ gateway/        client.py  models.py  cost.py  search.py
│  ├─ schemas/        common.py  blog.py  course.py  contract.py
│  ├─ graphs/         blog.py  course.py
│  ├─ nodes/          blog_nodes.py  course_nodes.py
│  ├─ tools/          fetch.py  gates.py  quizcheck.py  edits.py  snippets.py
│  │                  repo.py  runner.py  publisher.py  worktree.py
│  ├─ ideas/          scout.py  sources.py            # post-launch
│  └─ api/            app.py  auth.py  routes_blog.py  routes_course.py
│                     routes_settings.py  routes_library.py  stream.py  routes_ideas.py
├─ tests/  fakes.py  test_*.py
├─ evals/  golden/                  # later
└─ data/                           # gitignored: checkpoints.db, runs.db, artifacts/, cache/, publish-worktree/
```

### 3.3 Runtime

```
 Browser  http://localhost:4321/admin/
    │  fetch + SSE, X-Admin-Token, CORS only from the site origin
    ▼
 Pipeline API  127.0.0.1:8787  (FastAPI; Host-header check)
    ├─ LangGraph runs (thread pool, max 2 concurrent runs)
    ├─ SQLite: checkpoints.db + runs.db; artifacts on disk
    ├─ Gateway ──▶ OpenRouter (chat, structured output, web search tool)
    ├─ Fetcher ──▶ public web (robots.txt, SSRF-guarded, size caps)
    ├─ Repo manager ──▶ local course repo ──push──▶ GitHub (course repo)
    └─ Publisher ──▶ git worktree ──push──▶ GitHub (site repo, main) ──▶ Cloudflare Pages
```

Requirements: bind to loopback only; reject requests with an unexpected `Host`; token on every route but `/health`; CORS only for the site origin; secrets only in `apps/pipeline/.env`; startup makes no paid calls; `pipeline doctor` checks keys, git, paths, schema package, remotes.

### 3.4 Deploy or not
**Deployed:** the site only. **Not deployed:** the pipeline, the admin page, the course workspace. Enforced in `02` §8.2. Revisit only if you need to approve from other devices, run on a schedule while your computer is off, or share access. That would require hosting, authentication, a GitHub-API publisher and a job queue, all out of scope.

---

## 4. Model layer (OpenRouter)

### 4.1 Gateway
Nodes call a small interface: `text(task, …)`, `structured(task, schema, …)`, `research(task, …)`. The OpenRouter implementation handles routing, retries, fallbacks, validation, cost and budgets. Tests inject a fake. Use an OpenAI-compatible client against OpenRouter through LangChain's chat-model interface; prefer a first-party LangChain OpenRouter integration if one is current and exposes the fields below *(verify)*.

OpenRouter request fields used:
- `provider.require_parameters: true` on structured and tool requests, so routing only goes to endpoints that support them (only some models support structured outputs).
- A `models` list for fallbacks, and optional `provider` data-policy preferences.
- Errors inside an HTTP 200 response are treated as failures.

### 4.2 Tasks (lean) and defaults

| Task | Used for | Needs |
|---|---|---|
| `fast` | quizzes, small structured jobs | cheap, valid structured output |
| `plan` | blog plan, course plan, idea scouting | reasoning, structured output |
| `write` | blog draft, lessons, revisions, feedback | long-form quality |
| `check` | critics and metadata | strong; **different family from `write`** |
| `code` | writing project code | strong at code and following exact edit formats |
| `research` | web research for references | tool calling |

Defaults live in `config/models.yaml` as placeholders; choose real models in the UI after a smoke test. The settings screen warns when `write` and `check` use the same model. Model names are never hard-coded.

### 4.3 Catalog and smoke test
The pipeline caches OpenRouter's model list with pricing and supported parameters *(verify field names)*. Pickers filter by capability (structured outputs for `plan`, `fast`, `check`, `code`; tool calling for `research`). A **smoke test** per model runs one structured call and one long-form call and reports validity, latency and cost.

### 4.4 Structured output
Request a JSON schema, validate with Pydantic, retry twice with the validation error, then try the fallback model, then fail the node clearly. Long prose (articles, lessons) is requested as plain text so the model is not forced to escape a long body inside JSON.

### 4.5 Web research
Use OpenRouter's `web_search` server tool (beta) for `research`. The model decides when to search; results come back as `url_citation` annotations. Parameters include `max_results` (1 to 25), `allowed_domains`, `excluded_domains` and `max_uses`; it requires a tool-calling model and is billed in addition to tokens. The older `:online` and web plugin are deprecated. *(verify current parameters)*

How it is used safely:
1. The research call gets the topic, `max_uses` (cap), and your allow and exclude lists.
2. URLs are harvested from the **annotations**, never from the model's prose.
3. Each URL is fetched by the pipeline's own fetcher (robots.txt, SSRF guard, size cap, content-type allowlist). Unreachable or unreadable URLs are dropped and logged.
4. Verified items are shown to you; only the ones you keep are used.

### 4.6 Cost and budgets
Record per call: task, model used, tokens, dollars, latency, retries, fallback. Show live cost per run and per node. **Per-run cap** (defaults: blog $1, course part $3, course planning $2; configurable). At 80% warn; at 100% pause the run (`paused_budget`) without data loss; raise the cap to resume. Cache fetched pages by content hash so retries do not pay twice.

---

## 5. Data model and state

### 5.1 Entities

| Entity | Key fields |
|---|---|
| **Run** (blog) | id, topic, status, settings snapshot, cost, events |
| **Course** | id, slug, title, repo_name, repo_path, repo_url, docs_urls, references[], modules[], status, cost |
| **Source** | id (S1…), origin (supplied or researched), kind, title, url, text (capped), flags, content_hash |
| **Reference** (courses) | id, title, url, type (docs, video, article, repo, interactive, book, course, roadmap), why, illustrated, verified |
| **ModuleSpec** | n, slug, title, objectives[], concepts[], steps[] (commit plan), doc_urls[], ref_ids[], estimatedMinutes |
| **ModuleState** | spec, status, branch, commits[], test_result, lesson_md, quiz[], resources[], sources[], gates[], rounds |
| **Decision** | what you send at an interrupt (§9.3) |
| **Event** | t, node, level, msg, cost?, model? |

Large artifacts (diffs, file snapshots, fetched pages) are stored as files under `data/artifacts/<id>/`. State holds paths and hashes, not blobs, so checkpoints stay small.

### 5.2 Status machines

```
Blog:    queued → working → awaiting_plan? → awaiting_review → publishing → published
                                  working → failed | paused_budget | cancelled; awaiting_* → rejected
Course:  planning → awaiting_refs → awaiting_plan → part_N: coding → awaiting_code_review
                    → lesson → awaiting_lesson_review → publishing → part_published → (next part) → complete
Part status: planned · coding · code_review · lesson · lesson_review · published · skipped
```

### 5.3 Content contract
All frontmatter is validated twice before any write: against Pydantic models and against the JSON Schema generated from `packages/content-schema` (`02` §5). The pipeline refuses to publish if either fails.

---

## 6. Blog pipeline (lean)

### 6.1 Graph

```
intake → ingest → plan ──(optional)──▶ plan_review ⟲(revise)
       → write → check → gates ─┬─ high-severity issues & auto_revisions < 1 → revise → check
                                └─▶ human_review ──approve──▶ publish
                                        │ changes → apply_feedback → check → gates → human_review
                                        │ reject → END
                                        └ hard gate failing → blocked → human_review
```

### 6.2 Nodes

| Node | Kind | What it does |
|---|---|---|
| `intake` | code | Validate request; snapshot settings and models |
| `ingest` | code | Fetch URLs and PDFs, extract main text, clean, cap length, scan for instruction-like text, assign ids S1… . **No model call** (v0.1's per-source summaries are removed) |
| `plan` | model (`plan`, structured) | One call returning `BlogPlan`: angle, working title, and sections with key points, each tied to source ids. Replaces v0.1's separate claims and outline steps |
| `plan_review` | interrupt (default on, per-run toggle) | Approve, edit or request changes. No model call before the interrupt |
| `write` | model (`write`, text) | Draft from the approved plan and the sources, in your voice, with `[S#]` citations |
| `check` | model (`check`, structured) | One call returning scores, issues, unsupported statements **and** the SEO package (title, description, slug, tags, category, cover prompt). Replaces v0.1's separate critic and SEO steps |
| `gates` | code | Deterministic checks (§10.1) |
| `revise` | model (`write`) | Only if high-severity issues or ≥ 3 unsupported statements and `auto_revisions < 1` |
| `human_review` | interrupt | Approve, request changes (comments and/or your direct edits), or reject |
| `apply_feedback` | model (`write`) | Minimal changes for your comments; **your direct edits always win** |
| `publish` | code | Validate, renumber citations, commit through the worktree (§11.2) |

### 6.3 Rules
- The writer may use only facts from the plan and sources. First-person opinions come only from your notes. Quotes ≤ 15 words and rare; paraphrase fully.
- A source without a URL can be used for understanding but cannot be cited in a published post.
- Hard gates (schema, citations) cannot be overridden. Other failing gates need an explicit "publish anyway".

### 6.4 Output
`apps/site/src/content/blog/<slug>.md`, validated frontmatter (`02` §5.1), body starting at `##`, citations as numbered links to the Sources section, optional `relatedPart` linking to a course part.

---

## 7. Course (roadmap) pipeline

### 7.1 Anatomy of a hands-on course

**Course:** a guided project you build part by part, Full Stack Open style. The final app is the point; the parts are the steps.

**Each part** (about 1 to 3 hours):
1. Objectives and "what we add in this part"
2. A short concept explanation
3. **Follow-along:** steps that correspond to real commits, with snippets pulled from the repo
4. **Exercises** (2 to 4): goal, acceptance criteria, collapsed hints. Types: extend, debug, refactor
5. A concept **quiz** (4 to 6 questions)
6. **Resources:** curated, verified links with a one-line reason
7. **Sources:** the official docs the lesson relies on
8. The **code panel** on the site: start tag, end tag, commits, compare link, `git checkout` snippet

**Exercises in v1** are tasks with acceptance criteria and hints. There are no hidden tests and no solution code, which keeps token use down. Exercise tests or solution branches can come later if learners ask.

**Inspired by:** the courses, roadmaps and articles that shaped the structure are credited on the course page.

### 7.2 Graph

```
PLANNING
 intake → seed_docs → research_refs → refs_review ⟲ → plan_course → plan_review ⟲ → init_repo
                                                         │ (interrupts: refs_review, plan_review)

PER PART (loop, sequential)
 select_part → code_step → apply_commits → code_review ⟲(changes → code_fix → apply_commits)
            → lesson_step → quiz_step → lesson_check → gates → lesson_review ⟲(changes → lesson_fix)
            → publish_part → (more parts? → select_part : END)
 lesson_review can send you back to code_review ("back_to_code")
```

No subgraphs, no fan-out. Parts are produced in order, so each part sees the real result of the previous one.

### 7.3 Planning phase

| Node | Kind | Detail |
|---|---|---|
| `intake` | code | Subject, level, **official docs URLs**, optional hints, part count range, budget cap |
| `seed_docs` | code | Fetch the docs URLs; follow same-domain links one level (bounded) or read the sitemap; build a **docs map** (titles and URLs) and cache pages |
| `research_refs` | model (`research`) + code | One or two search-enabled calls: existing courses, roadmaps, illustrated explainers, official tutorials, well-regarded repos. URLs from annotations; each verified by fetching; classified (type, illustrated, level) |
| `refs_review` | interrupt | You tick which references to keep, add your own URLs, and mark "inspired by" items. Nothing proceeds without it |
| `plan_course` | model (`plan`, structured) | Returns the **CoursePlan**: project spec (what you build, stack, architecture), then parts. Each part has objectives, concepts, **commit steps** (2 to 4 planned commits), `doc_urls` chosen from the docs map, `ref_ids` chosen from your kept references with a one-line `why`, and a time estimate |
| `plan_review` | interrupt | Edit titles, objectives, steps, order; add or remove parts; ask for changes. After approval, slugs and order are fixed |
| `init_repo` | code | Create the local course repo from `templates/course-repo/`; commit the scaffold; tag `part-0`; check the GitHub remote (see §7.4) |

`CoursePlan` (summary):
```
project: { name, summary, stack[], architecture_md, final_features[] }
parts[]: { n, slug, title, objectives[≥2], concepts[], steps[{title, intent, files[]}],
           doc_urls[], ref_ids[], resource_notes{ref_id: why}, estimatedMinutes }
```

### 7.4 Project repo manager (`tools/repo.py`)

**One-time setup per course (you):** create an **empty public GitHub repository**, then give the pipeline its URL. Recommended settings: description and topics, license (MIT or Apache-2.0), "Template repository" enabled, Actions enabled. `pipeline doctor` checks that the remote is reachable and empty.

**Conventions**

| Item | Convention |
|---|---|
| Local path | `COURSES_DIR/<repo-name>` (default `../courses/`), outside the monorepo |
| Branches | `main` always equals the latest **published** part. Work happens on `wip/part-N` branched from `main` |
| Commits | 2 to 4 per part, message `part-N: <what and why>`; identity from your git config, trailer `Assisted-by: content-pipeline` |
| Tags | Annotated tag `part-N` on the last commit of the part; `part-0` is the scaffold. Tags are immutable once pushed; fixes after publishing are new commits (errata) |
| Docs in repo | `docs/ARCHITECTURE.md` kept current; `docs/PARTS.md` table (tag, title, link to the lesson); README "How to follow along" |
| CI | `.github/workflows/ci.yml` runs the tests on every push and tag |
| Dependencies | The agent **names** dependencies; the pipeline runs `uv add <name>` so real, current versions are resolved (no invented version numbers) |

**Learner commands shown on every part:** `git clone …`, `git checkout part-N`, `git diff part-(N-1) part-N`, and a Compare link on GitHub.

**Safety rules for the repo tools:** all paths resolved inside the repo; `.git` and paths outside are rejected; no shell strings, only argument lists; commands come from an allowlist in config (`uv sync`, `uv add`, `uv run pytest -q`, `uv run ruff check .`); a secrets regex scan blocks commits containing key-like strings.

### 7.5 Code step: the agent writes the project

**`code_step` (model `code`, structured).** Inputs: the project spec, `docs/ARCHITECTURE.md`, this part's spec and steps, the repo file tree, contents of relevant files (bounded, line-numbered), the previous part's `summary_for_next`, and the part's docs excerpts. Output:

```
CodeStepOutput {
  commits: [ { message, edits: [FileEdit], add_dependencies: [{name, dev?}] } ],   # 2 to 4 commits
  architecture_update: str,                  # new text for docs/ARCHITECTURE.md (or empty)
  notes_for_lesson: str                      # what to emphasise when teaching this part
}
FileEdit { path, op: create | replace | edit | delete,
           content?: str,                    # for create/replace
           edits?: [{ search: str, replace: str }] }   # for edit; each search must match exactly once
```

**`apply_commits` (code):** on `wip/part-N`, apply each commit's edits in order, run `uv add` for dependencies, update `docs/ARCHITECTURE.md` and `docs/PARTS.md`, make the commits. Rejected edits (path escape, search not found or ambiguous, size caps, secret-like strings) fail the node with a precise message; the model gets one retry with the error.

**Limits to keep parts learnable:** about 200 to 600 changed lines per part; each file focused; tests included for each part's behavior. Tests use a fake LLM and make no network calls, so `uv run pytest` is fast and free.

**`code_review` (interrupt) – what you do:**
1. Read the commit list and diffs in the admin page (per commit and cumulative).
2. Edit files in your own editor in the repo folder if you want (the page shows the path and a refresh button).
3. **Run tests** (button): runs the allowlisted test command in the repo with a timeout and a scrubbed environment (no API keys); output is shown and saved.
4. **Ask for changes:** your comment (and optional failing output) goes to `code_fix` (model `code`, same output shape, max 2 per part) which applies new commits or amends.
5. **Accept:** if the working tree has your manual edits, you give a commit message and the pipeline commits them as `part-N: manual adjustments`.

Running generated code is the one risky step, so it never happens automatically. You read the diff first, then click Run. A Docker option (`--network none`) can be added later.

### 7.6 Lesson step: written from the real diff

**`lesson_step` (model `write`, text).** Inputs: the part's commits with diffs (bounded; large files summarised), line-numbered file snapshots at `HEAD`, the part spec, `notes_for_lesson`, doc excerpts (as `[S#]` sources), the course glossary and `summary_for_next` from earlier parts, and your voice file. Output: the lesson in Markdown with:
- a **"What we add"** summary, a short concept section, and follow-along steps matching the commits;
- **code as placeholders**: `{{code:src/agent/graph.py#L10-34}}`. The model sees numbered lines, so ranges are accurate. It may type only short inline code or shell commands (≤ 8 lines per block);
- **Exercises** in the fixed shape from `02` §5.4 (2 to 4, with criteria and hints);
- `[S#]` citations to official docs for factual statements.

**Expanding placeholders (code, `snippets.py`):** for each placeholder, read the file at `HEAD`, verify the range exists and is ≤ 40 lines, emit a fenced block with the right language, followed by a caption linking to `…/blob/part-N/<path>#Lx-Ly`. Anything unresolved is a hard gate failure.

**`quiz_step` (model `fast`, structured):** 4 to 6 concept questions mapped to the objectives; deterministic validation of option counts, correct ids, no "all/none of the above", position spread.

**`lesson_check` (model `check`, structured):** scores, issues, unsupported statements, a meta description, and `summary_for_next` (≤ 120 words, carried to the next part with the glossary).

**`gates` (code):** §10.2.

**`lesson_review` (interrupt):** rendered lesson with snippets expanded, tabs for Sources, Resources, Quiz, Checks, Diff; edit markdown; comment for `lesson_fix` (model `write`, minimal changes); `back_to_code`; approve.

**Resources:** assembled deterministically from the part's `ref_ids` (title, url, type, illustrated from the verified references; the `why` text from the plan). You can remove or reorder in review. Links are never copied content.

### 7.7 Publishing a part (two repos, in a safe order)

```
1. Preconditions   course repo clean; wip/part-N at HEAD; lesson hard gates pass; remotes reachable;
                   (warn if tests were not run or failed)
2. Course repo     create annotated tag part-N; fast-forward main to it;
                   git push origin main part-N; verify with git ls-remote --tags origin part-N
3. Build files     module markdown (frontmatter incl. code: start/end tag, commits, compareUrl, treeUrl, files)
                   + roadmap index.md (create on first part; otherwise update planned[], lastReviewed;
                   last part → status: complete, version bump)
4. Site repo       worktree commit "content(roadmap): <course> part N - <title>" → push to main
5. Deploy          Cloudflare Pages builds main → part is live
6. Record          links to tag, compare view, live page; optional poll until the page responds
```

**Why this order:** the tag is pushed first, so every GitHub link on the live page already works. If step 4 fails, the tag is harmless and the retry button re-runs steps 3 to 4. If step 2 fails, nothing public has changed.

**Module frontmatter example (generated, never hand-typed):**
```yaml
title: "Tools: search and verified fetch"
order: 3
estimatedMinutes: 90
objectives: ["Define a tool interface", "Fetch and verify a source before using it"]
sources: [{ title: "LangGraph docs: tools", url: "https://…", accessed: 2026-11-02 }]
resources: [{ title: "…", url: "https://…", type: article, why: "Clear diagrams of the tool-calling loop", illustrated: true }]
code:
  startTag: part-2
  endTag: part-3
  compareUrl: https://github.com/<user>/langgraph-deep-research/compare/part-2...part-3
  treeUrl: https://github.com/<user>/langgraph-deep-research/tree/part-3
  commits: [{ sha: "a1b2c3d", message: "part-3: add search tool interface", url: "https://github.com/…/commit/a1b2c3d" }]
  files: ["src/deep_research/tools/search.py", "tests/test_search.py"]
quiz: [ … ]
lastReviewed: 2026-11-02
```

### 7.8 Flagship course (proposal to confirm at `plan_review`)

**Title:** Build a LangGraph deep-research agent, part by part.
**Final project:** a research agent that plans, searches, reads, verifies and writes a cited report, with checkpointing and human approval, served over an API.
**Stack:** Python 3.12, uv, LangGraph, Pydantic, httpx, pytest, FastAPI. Models via OpenRouter (OpenAI-compatible endpoint).

| Part | Tag | Adds | Key concepts |
|---|---|---|---|
| 1 | `part-1` | Project setup, typed LLM client, first call, fake LLM for tests, CI | uv, env, OpenRouter, testing without network |
| 2 | `part-2` | Structured output and your first graph (`plan → answer`) | Pydantic, state, nodes, edges |
| 3 | `part-3` | Tools: search and a verified fetcher; source objects | tool interface, robots/SSRF basics, provenance |
| 4 | `part-4` | The research loop with a planner, a researcher and a reflect step | conditional edges, loops, budgets, iteration caps |
| 5 | `part-5` | Cited report writer; checkpointing; human-in-the-loop plan approval | citation validation, checkpointer, `interrupt()` |
| 6 | `part-6` | Serve it: FastAPI with streaming, a minimal CLI or UI, a small eval set | streaming, evals, deployment notes |

`part-0` is the scaffold. Open decisions for the plan checkpoint: the course project's search provider (a free-tier search API versus OpenRouter's search tool) and whether Part 6 includes a UI or only a CLI.

---

## 8. Idea scouts (post-launch, lean)

Build these **after launch**, once you know what you actually want suggested. Both are single-pass, not autonomous agents.

### 8.1 Blog idea scout
```
collect (code) → prefilter (code) → rank & pitch (1 model call) → you choose → handoff to a blog run
```
- **Collect:** feeds you list in `config/feeds.yaml` (official blogs, changelogs), the Hacker News search API for your keywords, GitHub search for fast-rising repos in your niche, and optionally one search-enabled call. Each item keeps title, URL, date, a snippet and a signal (points, stars).
- **Prefilter (code):** drop old items, duplicates and denied domains; skip topics you already published (titles read from the library) or rejected.
- **Rank and pitch (1 call, `plan`):** over at most about 40 items, return 8 idea cards: pitch, angle, **why now** (dated evidence), a **reading list** of 3 to 6 links with a reason each, effort, fit score, risk.
- **Your part:** read the links yourself, mark each as useful or not, optionally paste highlights. "Start run" creates a blog run whose sources are the links you kept, so curation starts from what you read. Reject with a reason chip ("too hyped", "off-niche", "already covered"); recent reasons are shown to the model next time (no fine-tuning).
- **Cost:** about 1 to 2 calls and 15 to 25k input tokens per scan.

### 8.2 Course idea scout
One search-enabled call to survey existing courses, roadmaps and popular repos in a niche you give, then one structured call returning about 5 course ideas: audience, "you will build X", gap versus existing courses, prerequisites, a part outline, a flagship project idea, candidate docs URLs, inspirations to credit, effort estimate. "Start course" pre-fills the New Course form. You will use this rarely, so it is the lowest priority.

---

## 9. Admin page and API

### 9.1 Screens (lean)

| Screen | What it does |
|---|---|
| **Connect** | Token and address; `doctor` results; current spend; publish mode strip |
| **Runs** | Blog runs and courses with status chips; New blog; New course |
| **New blog** | Topic, audience, angle, length, your notes, sources (URL or pasted text with optional URL), plan checkpoint toggle, budget |
| **Blog review** | Activity log; tabs Draft, Sources, Checks, Diff, Metadata; edit markdown; comments; approve, request changes, reject; publish confirm |
| **New course** | Subject, level, docs URLs, hints, part range, repo name and GitHub URL, budget |
| **Course plan** | Step 1 references (verified list with keep checkboxes, add your own); Step 2 the plan editor (parts, objectives, steps, order) |
| **Part workspace** | Stepper **Code → Lesson → Publish**. Code: commits, diffs, files, Run tests, Ask for changes, Accept. Lesson: rendered preview, Sources, Resources, Quiz, Checks, edit, comments, back to code, approve. Publish: exactly what will happen (§7.7) with links |
| **Settings** | Model per task with price and capability filter, smoke test, fallbacks; budgets; paths (courses dir, site repo); publish mode; voice editor |
| **Library** | Read-only list of what is live, with commit ids and links |

### 9.2 API (lean)

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness (no auth) |
| `GET /doctor`, `GET /config` | Environment checks; effective non-secret config |
| `GET/PUT /settings`, `GET /models`, `POST /models/{id}/smoke`, `GET /credits` | Models, budgets, catalog, credit |
| `POST /blog/runs` · `GET /blog/runs` · `GET /blog/runs/{id}` | Start, list, view |
| `POST /courses` · `GET /courses` · `GET /courses/{id}` | Create, list, view (plan, parts, repo state) |
| `GET /courses/{id}/parts/{n}` | Part detail: commits, diffs, test result, lesson preview |
| `POST /courses/{id}/parts/{n}/tests` | Run the allowlisted tests (after your review) |
| `POST /runs/{id}/resume` | Send a decision (validated against the pending interrupt) |
| `POST /runs/{id}/retry` · `/cancel` · `/budget` | Continue after failure; cancel between nodes; raise cap and resume |
| `GET /runs/{id}/stream` | Server-Sent Events: events and status snapshots (polling fallback) |
| `GET /library` | Published items with commit ids |
| `POST /ideas/blog/scan` · `GET /ideas` · `POST /ideas/{id}/decision` | Idea scout (post-launch) |

Projections never contain secrets, never contain full fetched pages (excerpts only), and render Markdown to HTML on the server with raw HTML disabled.

### 9.3 Decisions you send (resume payloads)
```
blog plan:        { action: approve | revise, comments[], plan? }
blog review:      { action: approve | changes | reject, comments[], edited_md?, seo?, force? }
course refs:      { action: approve, keep_ids[], extra_urls[], inspired_by_ids[] }
course plan:      { action: approve | revise, comments[], plan? }
code review:      { action: accept | changes | skip_part, comments[], failing_output?, manual_commit_message? }
lesson review:    { action: approve | changes | back_to_code, comments[], edited_md?, edited_quiz?, resources_edit?, force? }
```
Your direct edits are authoritative and are re-validated and re-gated before publishing is possible.

---

## 10. Quality gates

### 10.1 Blog gates
Schema (hard); citations (hard: all `[S#]` known and every cited source has a URL); unsupported statements (from `check`); similarity to sources (8-word shingles, default limit 18%); quote length (≤ 15 words); filler phrases (`voice/banned.txt`); length; structure (no H1, ≥ 2 H2, tagged code fences); source safety (instruction-like text flagged); links reachable (warn); section coverage (warn).

### 10.2 Part gates

| Gate | Rule | Level |
|---|---|---|
| schema | Module frontmatter validates (Pydantic + JSON Schema) | hard |
| snippets | Every `{{code:…}}` resolves; each ≤ 40 lines; typed code blocks ≤ 8 lines | hard |
| code state | Tag range valid; commits exist; no secret-like strings | hard |
| sources | Cited sources fetched OK; every factual paragraph cites or is flagged | hard for URLs, fail for coverage |
| similarity | Overlap with docs under the limit | fail |
| exercises | 2 to 4, each with acceptance criteria and at least one hint | fail |
| quiz | Deterministic integrity checks | hard |
| tests | Last test run passed (warn if never run or failed) | warn |
| resources | Each URL verified; from the references you kept | hard |
| objectives | Critic confirms each objective is taught | fail |
| links, injection flags, length | as in blog | warn |

### 10.3 Evals (later)
A small golden set (3 blog topics, one tiny two-part course) run with `pipeline eval`, tracking unsupported-claim rate, gate failures, revision rounds, cost. Opt-in because it spends money.

---

## 11. Publishing and deployment

### 11.1 End-to-end picture

```
BLOG    you approve ─▶ worktree commit (site repo, main) ─▶ GitHub ─▶ Cloudflare Pages build ─▶ live
COURSE  you approve a part ─▶ tag part-N pushed to the course repo (GitHub)
                           ─▶ worktree commit of the lesson + index (site repo, main) ─▶ Cloudflare ─▶ live
        reader: lesson page ─▶ "Compare on GitHub" ─▶ course repo at part-N
```

### 11.2 Site repo publishing (blog and parts): the worktree
The publisher never touches your working tree:
1. `git fetch origin main`; keep a detached worktree at `data/publish-worktree` reset to `origin/main`.
2. Write the files; `git add` only those paths; commit (`content: <title>` or `content(roadmap): …`).
3. `git push origin HEAD:main`. If rejected because `main` moved, fetch, rebase the one commit, retry (up to 3).
4. On final failure the commit is kept and the UI shows the exact error and a retry.

Safety: `files` mode (write into the worktree and show the diff without committing) for dry runs; the confirm dialog says "commits to `main` and goes live"; a global setting disables pushing.

### 11.3 Cloudflare and GitHub (site)
Cloudflare Pages is connected to the site monorepo with production branch `main`, build command `pnpm build`, output `apps/site/dist`, and **build watch paths** that include `apps/site/*`, `packages/*` and the lockfile but exclude `apps/pipeline/*`. Full settings, the staging-to-launch plan and CI are in `02` §9. A failed Cloudflare build does not replace the live site.

### 11.4 Course repo on GitHub
- Created once (empty, public, template enabled, Actions on).
- The pipeline pushes `main` and one tag per approved part. CI runs on every push and tag, so every tag is verifiably green (the README shows the badge).
- The site links to the repo, tags, commits and compare views using URLs computed from `project.repo` and the tags, never written by the model.
- Optional later: create a GitHub Release per part from the lesson summary; wait for CI green before marking a part live (needs a GitHub token).

### 11.5 Revert
Library → **Revert** creates a `git revert` commit through the worktree for a site commit. Course tags are immutable once pushed; corrections are new commits and a note on the lesson.

---

## 12. Security and safety

| Area | Requirement |
|---|---|
| Prompt injection | Sources, search results and pages are untrusted data, always wrapped in delimiters with a standing instruction; instruction-like text is flagged to you; model output is never executed as commands |
| Generated code | Never auto-run. You review the diff, then click Run Tests; allowlisted commands only, argument lists (no shell strings), timeouts, scrubbed environment (no API keys). Docker sandbox optional later |
| Edits | Paths resolved inside the repo; `.git` protected; size caps; secrets regex blocks commits |
| SSRF and politeness | Public http(s) only (checked after DNS and after redirects), robots.txt, size and type limits, per-host rate limit |
| Local API | Loopback bind, token, Host check, strict CORS |
| Secrets | `.env` only; redacted in logs; never in browser, prompts or commits |
| Output safety | Published Markdown allows only `<details>` and `<summary>` as raw HTML; scripts and unknown components are rejected |
| Copyright | Paraphrase; short quotes; resources linked not copied; docs cited; "Inspired by" credits |
| Data policy | Optional OpenRouter provider restrictions and a per-run "private" flag |
| Cost | Caps, warnings, credit floor, visible meter |

---

## 13. Testing

| Layer | Approach |
|---|---|
| Unit | Slugging, citation renumbering, shingles, quiz checks, SSRF guard, edit application (path escape, ambiguous search), snippet expansion, budget math |
| Node and graph | Fake LLM: full blog run (plan loop, auto-revise, feedback, blocked, reject, resume after restart); full 2-part course run producing a tiny real repo |
| Repo manager | Temp repo and bare remote: branches, commits, tags, fast-forward, push, `uv add` stubbed, race and failure paths |
| Publisher | Temp site repo and remote: worktree reset, push race retry, revert, files mode, user working tree untouched |
| API | Auth, Host and CORS, decision validation, SSE order, cancel, budget pause and resume |
| Contract | Pipeline output validates against the schema package, and the site builds with it in CI |
| Security | Injection fixtures; private-IP and redirect fetch cases; secret-in-edit blocked |
| Live smoke (opt-in) | One tiny real OpenRouter call set: structured, long text, search, cost accounting |
| UI | Playwright against the dev site and a fake API |

---

## 14. Implementation plan

Work in order. After each phase you have something that works.

| Phase | Scope | Exit criteria | Est. |
|---|---|---|---|
| **P0 Monorepo** | Shared with site S0 and S1: workspace, schema package, Cloudflare staging deploy | `pnpm dev` runs site + pipeline; a commit to `main` deploys to staging | 2 to 3 d |
| **P1 Gateway and lean blog** | OpenRouter gateway (tasks, fallbacks, cost, budgets, catalog, smoke test); refactor blog graph to plan/write/check; remove per-source summaries; worktree publisher; settings screen | A blog run costs 3 base calls, shows dollars, publishes through the worktree to staging | 3 to 4 d |
| **P2 Launch blogs** | Run the pipeline for 4 to 5 posts; fix what hurts; polish blog review UX | 4 to 5 posts live on staging, each reviewed and edited by you | 5 to 7 d (mostly review) |
| **P3 Course foundation** | Repo manager, template, `seed_docs`, `research_refs`, `plan_course`, repo init, course screens (plan, references) | A course plan approved; local repo created with `part-0`; remote verified | 4 to 5 d |
| **P4 Part loop** | `code_step`, edit application, code review UI, tests runner, `lesson_step`, snippets, quiz, `lesson_check`, gates, part workspace, two-repo publish, site changes (`02` S2) | Part 1 goes from approved plan to live lesson with a pushed tag; CI green | 6 to 8 d |
| **P5 Flagship course** | Produce parts 1 to 6; refine prompts from what you correct | 6 parts live; README, license, template, CI polished | 10 to 15 d (mostly code review) |
| **P6 Launch** | Shared with site S3, S5, S6: SEO build-out, polish, domain, indexing on | `01` §7.1 checklist complete; Search Console set up | 3 to 4 d |
| **P7 Scouts (post-launch)** | Blog idea scout; course idea scout if wanted | Scout returns idea cards with reading lists; "Start run" prefilled | 3 to 4 d |

Total is roughly 5 to 7 weeks at part-time hours. Stop after any phase with a working system. P0 to P2 already gives you a strong blog pipeline.

### 14.1 Changes to the delivered v0.1 code

| Area | Change |
|---|---|
| LLM layer | Gemini-specific code → OpenRouter gateway with tasks and cost |
| Blog graph | Remove `extract_claims`, per-source summaries and the separate SEO node; merge into `plan` and `check`; default auto-revisions 1 |
| Publisher | Working-tree writer → detached worktree |
| API | Add tasks/settings/models/credits/stream/library; add course routes |
| Admin UI | Extend the delivered run list and review view; add course screens |
| Repo | Two folders → pnpm monorepo with a shared schema package |
| Tests | Keep the 13 tests; adapt to the new graph; add repo-manager and course tests |

---

## 15. Risks and open questions

| Risk | Mitigation |
|---|---|
| Agent-written project code is wrong or messy | Small parts, tests per part, your diff review, one-click Run Tests, targeted `code_fix`, CI on every tag |
| Lessons drift from the code | Snippets are extracted from the tag; gates fail on unresolved placeholders |
| Dependency versions go stale | Pipeline adds dependencies via `uv add`; lock file in the repo; "last reviewed" dates; refresh later |
| Cost overruns | Lean call budget, caps, caching, model choice per task |
| Models disagree on structured output | `require_parameters`, validation retries, fallbacks, smoke tests |
| Search noise | Verification by fetching, your keep/discard step, short lists |
| Tag pushed, site commit fails | Order guarantees working links; retry re-runs only the site step |
| Scope creep | Ideation, evals, Docker, certificates, CLI are deliberately deferred |

**Open questions**
1. Course repo name and GitHub owner; license choice.
2. Search provider inside the course project (free-tier search API or OpenRouter's search tool).
3. Whether Part 6 ships a UI or a CLI only.
4. Whether commits should carry your identity only, or also a co-author line.
5. Which models become defaults after the smoke tests.

---

## Appendix A. Configuration

`apps/pipeline/.env.example`
```
ADMIN_TOKEN=                         # created on first `pipeline serve`
OPENROUTER_API_KEY=
COURSES_DIR=../courses               # where course repos are cloned (outside the monorepo)
SITE_REPO_PATH=..                    # monorepo root (git root)
SITE_APP_DIR=apps/site
SITE_BASE_URL=https://<staging-or-domain>
PUBLISH_MODE=git                     # git | files
GIT_REMOTE=origin
GIT_BRANCH=main
```

`config/models.yaml` (shape; model ids chosen in the UI)
```yaml
tasks:
  fast:     { model: "<id>", fallbacks: ["<id>"] }
  plan:     { model: "<id>", fallbacks: ["<id>"] }
  write:    { model: "<id>", temperature: 0.7 }
  check:    { model: "<id from a different family>", temperature: 0.2 }
  code:     { model: "<id>", temperature: 0.2 }
  research: { model: "<tool-calling id>" }
budgets: { blog_usd: 1.0, course_plan_usd: 2.0, part_usd: 3.0, warn_at: 0.8, credit_floor_usd: 2.0 }
research: { max_results: 6, max_uses: 6, exclude_domains: [] }
gates: { max_similarity: 0.18, max_auto_revisions: 1, max_snippet_lines: 40, max_typed_code_lines: 8 }
commands: { test: ["uv", "run", "pytest", "-q"], lint: ["uv", "run", "ruff", "check", "."], timeout_s: 120 }
```

## Appendix B. A course part, end to end

1. You approve the plan. The repo exists with `part-0`.
2. **Part 3, code:** the agent proposes 3 commits (search interface, fetcher with checks, tests). They are applied on `wip/part-3`. You read the diffs, run tests (green), tweak a variable name in your editor, accept (a "manual adjustments" commit is added).
3. **Part 3, lesson:** the agent writes the lesson from those diffs with `{{code:…}}` placeholders, 3 exercises and a 5-question quiz. Checks pass with one warning. You edit two sentences and approve.
4. **Publish:** tag `part-3` is pushed to GitHub (CI runs green); the lesson and updated roadmap index are committed to the site `main`; Cloudflare deploys; the page shows the code panel with the commits and a Compare link; the next part is selected.
5. A reader opens the lesson, clones the repo, runs `git checkout part-3`, and sees exactly what you saw.
