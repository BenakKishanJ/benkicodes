# PRD — LangGraph Content Pipeline (Python)

**Version:** 1.0 · **Date:** 23 Oct 2026
**Owner:** Ben
**Status:** Draft for review
**Related:** `01-market-seo-monetization-strategy.md`, `02-prd-astro-blog-site.md`

---

## 1. Overview

### 1.1 Purpose
A multi-agent system, built with **LangGraph**, that turns Ben's source material and topic ideas into **publish-ready blog posts and learning roadmaps**, with a mandatory **human review loop** before anything is published to the Astro site.

### 1.2 Product principles
1. **Human in command.** Nothing is published without explicit approval. The pipeline drafts, Ben decides.
2. **Source-grounded.** Claims trace to supplied or retrieved sources. No source, no claim.
3. **Quality over volume.** Gates and critics slow things down on purpose. The pipeline exists to avoid "scaled content abuse", not to enable it.
4. **Resumable and inspectable.** Any run can be paused, resumed, replayed, and audited.
5. **Portable.** Model-agnostic, config-driven, loosely coupled to the site through a content contract.

### 1.3 Goals
| # | Goal | Success measure |
|---|---|---|
| G1 | Produce drafts Ben can approve with light edits | ≥ 70% of drafts approved within 2 revision rounds (after the first 20 posts) |
| G2 | Two modes: **Blog** (curate from supplied material) and **Roadmap** (plan, lessons, quizzes) | Both run end to end |
| G3 | Durable human-in-the-loop | Runs survive process restarts using a persistent checkpointer |
| G4 | Auto-publish after approval | Approved content becomes a PR on the site repo with valid schema |
| G5 | Showcase-grade engineering | Tracing, evals, tests, cost tracking, clear README and architecture diagram |

### 1.4 Non-goals (v1)
- Multi-user or multi-tenant operation
- Fully autonomous publishing (no human gate)
- Mass keyword-driven article generation
- Image generation (cover image **prompts** only, in v1)
- Social media posting

### 1.5 Users
**Single operator: Ben** (author, reviewer, publisher). Design the interfaces for one person working quickly, but keep the architecture clean enough to extend later.

---

## 2. Scope: modes and workflows

### 2.1 Blog mode
**Input:** topic or news item plus Ben's supplied material (text, URLs, PDFs, notes, pasted links) plus optional angle/audience/length.
**Output:** a reviewed `.md/.mdx` post with valid frontmatter, sources list, SEO metadata, and a cover image prompt.

### 2.2 Roadmap mode
**Input:** a subject (e.g., "LangGraph for AI engineers"), target level, optional structure from Ben, or "propose a structure".
**Output:** a roadmap folder: `index.md` + N module files, each with objectives, lesson body, resources, and a quiz.

### 2.3 Maintenance mode (P2)
**Refresh:** re-check an existing post/roadmap for outdated facts, versions, and broken links; propose a diff for review.

---

## 3. User flows

### 3.1 Blog mode (happy path)
```
1. ben new-blog --topic "..." --sources ./notes/*.md --url https://...
2. Pipeline ingests + cleans sources, extracts claims
3. (optional) research gaps via web search, labelled "retrieved" vs "supplied"
4. Outline generated → [CHECKPOINT A: approve/edit outline]   (configurable; on by default for new topics)
5. Draft written → critic reviews → revise loop (max N)
6. Finalizer adds SEO metadata, tags, cover prompt, internal-link suggestions
7. [CHECKPOINT B: human review]  ← run pauses (interrupt)
8. Ben reviews: approve / request changes (with comments) / reject
9. On changes → writer revises with comments → back to 7
10. On approve → publisher validates schema → opens PR → Cloudflare preview URL returned
11. Ben merges PR → site deploys
```

### 3.2 Roadmap mode (happy path)
```
1. ben new-roadmap --subject "..." --level beginner [--outline outline.md | --propose]
2. Planner proposes structure (phases, modules, prerequisites, outcomes, hours)
3. [CHECKPOINT A: approve/edit structure]  ← required, before spending tokens on lessons
4. For each module (parallel fan-out): research → lesson writer → quiz generator → module critic
5. Consistency agent checks cross-module flow, duplication, prerequisite order, terminology
6. [CHECKPOINT B: per-module review]  approve / revise / regenerate each module independently
7. Publisher validates + opens one PR for the roadmap (or per module, configurable)
```

---

## 4. System architecture

```
┌────────────┐   ┌────────────────────────────────────────────┐   ┌──────────────┐
│  Interfaces │   │             LangGraph runtime              │   │   Outputs     │
│ CLI (v1)    │──▶│ Supervisor/router                          │──▶│ Site repo PR  │
│ FastAPI +   │   │  ├─ Blog subgraph                          │   │ (MD/MDX +     │
│ Review UI   │◀──│  └─ Roadmap subgraph (parallel modules)    │   │  assets)      │
│ (v2)        │   │ Checkpointer (SQLite → Postgres)           │   └──────────────┘
└────────────┘   └───────┬───────────────┬────────────────────┘
                         │               │
              ┌──────────▼───┐   ┌───────▼────────┐   ┌────────────────┐
              │ Tools         │   │ LLM gateway     │   │ Observability   │
              │ web search,   │   │ model router,   │   │ LangSmith or    │
              │ URL fetch,    │   │ retries, cost   │   │ Langfuse, logs, │
              │ PDF parse,    │   │ tracking,       │   │ evals           │
              │ code runner   │   │ structured out  │   └────────────────┘
              └───────────────┘   └────────────────┘
```

### 4.1 Technology choices

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.12+ | Type hints throughout |
| Orchestration | LangGraph (pin the current stable version in `pyproject.toml`) | Subgraphs, `interrupt`, checkpointers, `Send` for fan-out |
| Models | Provider-agnostic via LangChain chat model interface or thin custom gateway | Default: Gemini (generous free tier, fits Ben's stack); Claude/OpenAI configurable |
| Schemas | Pydantic v2 | Structured outputs at every node |
| Persistence | SQLite checkpointer for dev, Postgres for prod/hosted | |
| API (v2) | FastAPI | Review UI backend |
| CLI (v1) | Typer + Rich | Diff views, prompts, status |
| Retrieval/search | Pluggable: Tavily/Brave/SerpAPI or similar *(choose one; verify pricing and free tier)* | Behind a `SearchTool` interface |
| Fetching/parsing | `httpx` + `trafilatura`/`readability` for HTML, `pymupdf` for PDFs | |
| Git publishing | PyGithub or `gh` CLI | PR creation |
| Tracing | LangSmith or Langfuse | Pick one; Langfuse is self-hostable |
| Testing | pytest, pytest-asyncio, VCR-style recorded responses | |
| Packaging | `uv` or Poetry; Docker for deployment | |

### 4.2 Repository structure

```
content-pipeline/
├─ src/pipeline/
│  ├─ config/            # settings.py (pydantic-settings), models.yaml, prompts/
│  ├─ state/             # state.py (TypedDict/Pydantic), schemas.py (content contracts)
│  ├─ graphs/
│  │   ├─ supervisor.py
│  │   ├─ blog.py
│  │   └─ roadmap.py
│  ├─ nodes/             # ingest.py, research.py, outline.py, writer.py, critic.py,
│  │                     # seo.py, planner.py, lesson.py, quiz.py, consistency.py, publish.py
│  ├─ tools/             # search.py, fetch.py, pdf.py, code_runner.py, github.py
│  ├─ llm/               # gateway.py (router, retries, cost), structured.py
│  ├─ review/            # cli_review.py, api.py (v2), diff.py
│  ├─ evals/             # datasets/, metrics.py, run_evals.py
│  └─ cli.py
├─ prompts/              # versioned prompt files (.md/.jinja) with frontmatter
├─ voice/                # style profile, writing samples, banned phrases
├─ tests/
├─ docs/ (architecture.md, adr/, runbook.md)
├─ pyproject.toml
└─ README.md
```

---

## 5. State and data models

### 5.1 Core state (illustrative)

```python
from typing import Annotated, Literal, TypedDict
from operator import add
from pydantic import BaseModel, Field, HttpUrl

class Source(BaseModel):
    id: str
    kind: Literal["supplied", "retrieved"]
    title: str
    url: HttpUrl | None = None
    text: str                      # cleaned
    summary: str
    trust: Literal["high", "medium", "low"] = "medium"

class Claim(BaseModel):
    id: str
    text: str
    source_ids: list[str]
    confidence: Literal["supported", "partial", "unsupported"]

class Review(BaseModel):
    verdict: Literal["approve", "changes", "reject"]
    comments: list[str] = []
    section_comments: dict[str, list[str]] = {}

class BlogState(TypedDict):
    run_id: str
    mode: Literal["blog"]
    topic: str
    audience: str
    angle: str | None
    sources: Annotated[list[Source], add]
    claims: list[Claim]
    outline: dict | None
    draft_md: str
    critique: dict | None           # scores + issues
    revision_count: int
    human_review: Review | None
    seo: dict | None                # title options, description, slug, tags, og text, cover prompt
    status: Literal["ingesting","outlining","drafting","critiquing","awaiting_review",
                    "revising","approved","published","rejected","failed"]
    cost_usd: float
    errors: Annotated[list[str], add]
```

`RoadmapState` adds: `subject`, `level`, `structure` (phases → modules), `modules: dict[slug, ModuleState]`, `consistency_report`, per-module `human_review`.

### 5.2 Structured outputs
Every LLM node returns a validated Pydantic model, with automatic retry-with-error-feedback on validation failure (max 2). No free-text parsing.

### 5.3 Content contract with the site
The publisher serializes to the site's Zod-defined schema (Site PRD §4). A shared `content-schema.json` is generated from the site repo and vendored here. The publisher **refuses to open a PR** if validation fails.

---

## 6. Blog subgraph: node specifications

| # | Node | Responsibility | Model tier | Output |
|---|---|---|---|---|
| 1 | **Intake** | Normalize inputs (topic, audience, length, angle), validate | none/cheap | `BlogBrief` |
| 2 | **Ingest** | Fetch/parse/clean URLs, PDFs, notes. Strip boilerplate. Detect prompt-injection patterns. Dedupe. Summarize each source. | cheap | `Source[]` |
| 3 | **Claim extractor** | Extract atomic factual claims with source IDs | cheap/mid | `Claim[]` |
| 4 | **Research (optional)** | Fill specific gaps via search; mark as `retrieved`, lower trust; max N queries | mid | `Source[]` |
| 5 | **Angle & outline** | Propose unique angle (what the top results lack), outline with section goals and source mapping | strong | `Outline` |
| 6 | **Writer** | Draft in Ben's voice from the outline + claims only. Inline citation markers `[S3]`. | strong | `draft_md` |
| 7 | **Code verifier** (when code present) | Execute or lint code in a sandbox; report failures | tool | `CodeReport` |
| 8 | **Critic** | Score: factual grounding, unique value, structure, voice, redundancy, hallucination risk. List concrete issues with locations. | strong (different model/prompt than writer) | `Critique` |
| 9 | **Revise loop** | If critique below threshold and `revision_count < max`, writer revises against issues | strong | updated draft |
| 10 | **SEO/finalizer** | Title options (≤60), description (≤155), slug, tags, TOC check, internal link suggestions, cover image prompt, reading time, JSON-LD hints | cheap/mid | `SEOPackage` |
| 11 | **Human review (interrupt)** | Present draft, sources, claim map, critique, diff | n/a | `Review` |
| 12 | **Human-revision writer** | Apply Ben's comments minimally; preserve approved sections | strong | updated draft |
| 13 | **Publisher** | Render MDX + frontmatter, validate schema, create branch/PR, post summary comment | none | PR URL |

**Routing logic**
- After Critic: `pass → SEO`, `fail & retries left → Revise`, `fail & no retries → human review with warning banner`.
- After Review: `approve → Publisher`, `changes → Human-revision writer → Critic (light) → Review`, `reject → end (archive)`.
- Hard cap on total revision rounds (default 3 automated, unlimited human) and per-run token budget.

**Writer constraints (system prompt essentials)**
- Use only supplied/retrieved claims for facts; mark inference clearly as opinion.
- No generic intros ("In today's fast-paced world…"), no filler conclusions, no unexplained jargon.
- Answer-first opening; scannable headings; code blocks with language and filename.
- Quotes: max 1 short quote per source (under ~15 words), always attributed. Otherwise paraphrase fully.
- Do not copy structure or phrasing of any single source.
- Match the voice profile (`voice/`).
- Include "What I'd do / my take" sections only if Ben supplied opinion notes. Do not invent personal experience.

---

## 7. Roadmap subgraph: node specifications

| # | Node | Responsibility | Output |
|---|---|---|---|
| 1 | **Intake** | Subject, level, constraints, optional Ben outline | `RoadmapBrief` |
| 2 | **Landscape research** | Survey existing roadmaps/curricula/docs; note gaps and current versions | `Source[]`, `gap_notes` |
| 3 | **Planner** | Propose phases and modules with objectives, prerequisites, estimated time, outcomes, ordering rationale | `RoadmapStructure` |
| 4 | **Checkpoint A (interrupt)** | Ben edits/approves structure before generation | approved structure |
| 5 | **Module fan-out** (`Send`) | One parallel subgraph per module | |
| 5a | → Module researcher | Gather authoritative docs/resources, pin versions | `Source[]` |
| 5b | → Lesson writer | Objectives → explanation → worked example → common mistakes → practice → summary | `lesson_md` |
| 5c | → Code verifier | Run/lint code samples | `CodeReport` |
| 5d | → Quiz generator | ≥ 5 questions: mixed difficulty, plausible distractors, explanations, each tied to an objective | `Quiz` |
| 5e | → Module critic | Checks accuracy, objective coverage, quiz validity (single correct answer, no ambiguity), reading level | `Critique` |
| 6 | **Consistency agent** | Cross-module: terminology, redundancy, prerequisite order, progressive difficulty, broken forward/back references | `ConsistencyReport` + targeted fixes |
| 7 | **Checkpoint B (interrupt, per module)** | Approve / revise / regenerate each module independently | `Review` per module |
| 8 | **Publisher** | Serialize `index.md` + `modules/*.mdx`, validate, open PR | PR URL |

**Quiz quality rules**
- Each question maps to a stated learning objective (stored as `objective_id` in pipeline state; optional in frontmatter).
- Exactly one correct answer for `single`; clearly defined set for `multi`.
- Distractors reflect real misconceptions, not obviously wrong answers.
- Explanations teach, and don't merely restate the answer.
- Quiz checker node validates: answer present among options, no duplicate options, no "all of the above" patterns unless allowed, question not answerable by lesson-less guesswork.
- Automated test: an independent model attempts the quiz *without* the lesson, and then *with* it. Questions answered correctly without the lesson, or incorrectly with it, are flagged.

---

## 8. Human-in-the-loop design

### 8.1 Mechanism
- Use LangGraph **`interrupt()`** at checkpoints and a **persistent checkpointer**. The run state is saved and the process can exit. Resume with `Command(resume=...)` using the `thread_id` (= `run_id`).
- Checkpoints: **A** (outline/structure), **B** (final review). Both configurable per run (`--auto-outline`, etc.).

### 8.2 Review interface

**v1: CLI (Typer + Rich)**
- `ben review <run_id>` shows: draft rendered in terminal, sources table, claim-to-source map, critic scores, diff vs. previous revision.
- Actions: `approve`, `comment` (section-level or global), `edit` (opens `$EDITOR` on the draft), `reject`.
- `ben runs` lists runs and statuses.

**v2: Web review UI (FastAPI + small React/Astro app, protected by Cloudflare Access or a local-only mode)**
- Side-by-side: rendered draft | sources with claim highlights.
- Inline comments mapped to sections, sent to the revision writer.
- Revision history with diffs, cost and token summary, preview-site link.
- Approve button triggers the publisher.

### 8.3 Review feedback handling
- Comments are structured (`section_id`, `comment`, `severity`) and passed to the revision writer.
- Writer must **change only what's commented** and report a change summary. A diff is shown to Ben.
- Direct edits by Ben are authoritative. The pipeline never silently overwrites them. It merges against his version.
- Style learning (P2): store accepted edits to improve the voice profile.

---

## 9. Quality gates, critics, and evals

### 9.1 Automated gates (pre-review)

| Gate | Method | Block or warn |
|---|---|---|
| Schema valid | Pydantic + site schema | Block |
| Every factual claim sourced | Claim map; unsupported-claim count | Block if > 0 unsupported high-risk claims, else warn |
| Source diversity | ≥ 2 sources unless a single primary source is justified | Warn |
| Plagiarism/similarity | n-gram overlap vs. each source; max threshold | Block above threshold |
| Quote policy | Quote length and count per source | Block |
| Code correctness | Run/lint in sandbox | Block on failure |
| Link validity | HEAD requests on all URLs | Warn/Block dead links |
| Length & structure | Min/max words, heading depth, TOC | Warn |
| Cliché/filler detector | Banned phrase list from `voice/` | Warn |
| SEO metadata | Title/description length, slug format, tags count | Block |
| Prompt-injection flags | Source scanner results surfaced to reviewer | Warn |

### 9.2 Critic rubric (scored 1–5, with evidence)
Factual grounding · Unique value vs. top results · Clarity & structure · Voice match · Redundancy · Technical accuracy · Reader usefulness. A draft needs an average of ≥ 4 and no dimension < 3 to skip automated revision.

### 9.3 Offline evals (the "showcase" differentiator)
- **Golden set:** 10–20 topics with reference sources and Ben-approved outputs.
- **Metrics:** grounding rate, unsupported-claim rate, similarity score, rubric scores (LLM-as-judge, spot-checked by Ben), quiz validity rate, revision rounds to approval, cost per post.
- **Regression runs:** executed when prompts, models, or graph structure change. Results stored and charted in the README.
- **Human agreement:** track how often Ben's verdict matches the critic's.

---

## 10. Tools & integrations

| Tool | Behavior and constraints |
|---|---|
| `fetch_url` | Respect `robots.txt` and rate limits; timeouts; content-type allowlist; size cap; extract main content only |
| `search_web` | Query budget per run; results logged; domains allow/deny lists (prefer official docs, primary sources) |
| `parse_pdf` | Text and table extraction; page cap |
| `code_runner` | Sandboxed (Docker, no network by default, CPU/time/memory limits); languages: Python, JS/TS first |
| `link_checker` | Async HEAD/GET with retries |
| `similarity_checker` | Shingled n-gram overlap and optional embedding similarity vs. sources |
| `github_publisher` | Branch naming `content/<mode>/<slug>-<runid>`; PR template with run summary; labels; never pushes to `main` |
| `og/cover_prompt` | Produces a prompt/alt text only (v1) |

All tools return structured results and are individually mockable for tests.

---

## 11. LLM gateway: models, cost, reliability

### 11.1 Model routing (configurable in `models.yaml`)

| Task class | Tier | Rationale |
|---|---|---|
| Ingest cleanup, summaries, claim extraction, SEO metadata | Cheap/fast | High volume, low risk |
| Outline, writing, revision | Strong | Quality-critical |
| Critic, quiz validation | Strong, ideally **different model family or prompt from writer** | Reduces self-agreement bias |
| Consistency checks | Mid/strong with long context | Needs whole-roadmap view |

### 11.2 Cost controls
- Per-run **token/USD budget**; node-level soft caps; abort or ask Ben to continue when exceeded.
- Cache source summaries and extracted claims by content hash.
- Cost recorded per node and run (`cost_usd`), displayed at review time.
- Dry-run mode (stubbed LLM) for testing graph logic.

### 11.3 Reliability
- Retries with exponential backoff and jitter; provider fallback list.
- Idempotent nodes where possible; side effects (PR creation) only in the publisher and guarded by an idempotency key.
- Timeouts per node; clear failure states with resumable checkpoints.

---

## 12. Security & safety

- **Prompt injection:** Source material and fetched pages are **untrusted data**. Nodes wrap them in delimiters and instruct the model to treat them as content only. The ingest node flags instruction-like text ("ignore previous…", tool-call patterns). Writer and publisher nodes have no access to secrets or tools beyond their role (least privilege). Flags are shown at review.
- **Secrets:** API keys via environment/secret manager; never in prompts, logs, or repo. GitHub token is scoped to the site repo with PR permission only.
- **Publish safeguards:** PR only (never direct push), schema validation, MDX construct allowlist (no raw scripts), branch protection on the site repo requires CI and Ben's approval.
- **Sandbox:** code execution isolated, no network, resource-limited.
- **Copyright & attribution:** short quotes only, source attribution, similarity gate, image licensing notes. No verbatim reproduction of source articles.
- **Privacy:** don't send private notes to providers you don't want to share them with. Provide a `--local-model` option (Ollama) for sensitive material.
- **Logging:** logs redact secrets; traces can be disabled per run.

---

## 13. Observability & operations

- **Tracing:** every node call traced (inputs/outputs sizes, latency, cost) with `run_id` as the correlation ID. `pipelineRunId` is also written into content frontmatter for traceability.
- **Run ledger:** table of runs with mode, topic, status, cost, revision count, time-to-approval, outcome.
- **Dashboards (P2):** approval rate, avg revision rounds, cost per post, failure reasons.
- **Runbook:** how to resume a failed run, rotate keys, change models, roll back a published post (revert PR).
- **Deployment:** local CLI first. Optional Docker + small VPS or Cloud Run for the review API. Keep the pipeline off Cloudflare Workers unless you intentionally port it. LangGraph/Python fits a container better.

---

## 14. Configuration

`config.yaml` (excerpt):

```yaml
site:
  repo: "ben/benki-blog"
  content_paths: { blog: "src/content/blog", roadmaps: "src/content/roadmaps" }
voice: { profile: "voice/ben.md", banned_phrases: "voice/banned.txt" }
models: { cheap: "gemini-flash", strong: "gemini-pro", critic: "claude-sonnet" }   # example names; set real ones at implementation
budgets: { per_run_usd: 1.50, max_auto_revisions: 3, max_search_queries: 8 }
checkpoints: { outline: true, final_review: true }
gates: { max_similarity: 0.18, require_sources_min: 2, block_on_unsupported: true }
publishing: { open_pr: true, labels: ["content","ai-assisted"], target_branch: "main" }
```

Everything niche-specific (voice, domain, audience, tags taxonomy) lives in config and `voice/`, so the same pipeline can serve a different site.

---

## 15. Functional requirements summary

| ID | Requirement | Pri |
|---|---|---|
| PL-1 | CLI to start blog and roadmap runs with sources/URLs/files | P0 |
| PL-2 | Ingest and clean URLs, PDFs, Markdown/text inputs | P0 |
| PL-3 | Claim extraction with source mapping | P0 |
| PL-4 | Outline → draft → critic → revise loop with caps | P0 |
| PL-5 | Persistent checkpointer; resume after restart | P0 |
| PL-6 | Human review interrupt with approve/comment/reject | P0 |
| PL-7 | Publisher opens PR with valid frontmatter and files | P0 |
| PL-8 | Roadmap planner with structure checkpoint | P0 |
| PL-9 | Parallel module generation (lesson + quiz) | P0 |
| PL-10 | Quiz validation (answer integrity, difficulty mix, explanations) | P0 |
| PL-11 | Consistency agent for roadmaps | P1 |
| PL-12 | Similarity and quote-policy gates | P0 |
| PL-13 | Code execution sandbox for samples | P1 |
| PL-14 | Cost tracking and per-run budget | P0 |
| PL-15 | Tracing (LangSmith/Langfuse) | P1 |
| PL-16 | Offline eval suite and regression runs | P1 |
| PL-17 | Web review UI with inline comments | P2 |
| PL-18 | Topic suggester (HN/GitHub trending/RSS; Ben picks) | P2 |
| PL-19 | Refresh mode for stale content | P2 |
| PL-20 | MCP server exposing pipeline actions (`draft_blog`, `approve`, `publish`) | P2 |
| PL-21 | Voice profile learning from accepted edits | P2 |

---

## 16. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Blog draft to review in ≤ ~5 min typical; roadmap of 8 modules ≤ ~25 min (parallelized) |
| Cost | Target ≤ $0.50 per blog post and ≤ $5 per 8-module roadmap on default models *(measure and adjust)* |
| Reliability | Any node failure leaves a resumable checkpoint |
| Determinism | Temperature and seeds configurable; prompts versioned; runs reproducible from stored inputs and prompt versions |
| Maintainability | Typed code, ≥ 80% coverage on non-LLM logic, ADRs for key decisions |
| Portability | No hard dependency on a single model vendor |

---

## 17. Testing strategy

| Layer | Approach |
|---|---|
| Unit | Pure functions: slugging, schema serialization, claim mapping, similarity, quote checker, quiz integrity |
| Node tests | Recorded LLM responses (VCR/cassettes) or a fake LLM returning fixtures |
| Graph tests | Run subgraphs with stubbed nodes; assert routing (pass/fail/retry/reject), interrupts, resume |
| Contract tests | Generated content validates against the site's schema; a site-side CI job builds a fixture produced by the pipeline |
| Eval regression | Golden-set metrics tracked per commit/prompt change |
| Safety tests | Injection fixtures (sources containing malicious instructions) must not alter output or tool use |
| E2E | Dry-run end to end to a throwaway repo, with PR creation mocked or against a test repo |

---

## 18. Milestones

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0 — Spike** (2–3 days) | Minimal linear graph: sources → draft → write `.md` file. Fake review prompt. | One real post drafted from real sources |
| **P1 — Blog MVP** (~1 wk) | Ingest, claim extraction, outline, writer, critic loop, SEO node, CLI review with `interrupt`, SQLite checkpointer, schema-valid output | Run, pause, resume, approve → local file |
| **P2 — Publishing** (~3–4 days) | GitHub PR publisher, contract validation, preview-link flow | Approved post lands as PR and deploys a preview |
| **P3 — Roadmap mode** (~1.5 wks) | Planner + Checkpoint A, parallel module fan-out, lesson and quiz nodes, consistency agent, per-module review | One full roadmap published |
| **P4 — Quality & safety** (~1 wk) | Similarity/quote gates, code sandbox, link checker, injection scanner, cost budgets | Gates demonstrably block bad drafts |
| **P5 — Observability & evals** (~1 wk) | Tracing, run ledger, golden set, regression script, README charts | Metrics reported for ≥ 15 runs |
| **P6 — Review UI & extras** | FastAPI + web UI, topic suggester, MCP server, refresh mode | Optional |

---

## 19. Acceptance criteria (v1 complete)

- [ ] Blog and roadmap modes run end to end from the CLI
- [ ] Runs pause for human review and resume after a process restart
- [ ] Nothing reaches the site repo without explicit approval, and always as a PR
- [ ] Output passes the site's schema validation and builds
- [ ] Every published post lists sources, and gates show zero unsupported high-risk claims
- [ ] Quiz validator catches an intentionally broken quiz in tests
- [ ] Injection fixture does not change pipeline behavior
- [ ] Cost and revision counts visible at review time
- [ ] README includes an architecture diagram, a demo GIF/video, and eval results
- [ ] ≥ 10 posts and 2 roadmaps produced by the pipeline and approved by Ben

---

## 20. Risks

| Risk | Mitigation |
|---|---|
| Drafts sound generic; reviewers burn time rewriting | Voice profile, banned phrases, "unique value" gate, angle step, learn from accepted edits |
| Hallucinated facts or APIs | Claim grounding, source-only writing, code execution, different-model critic, human approval |
| Over-publishing triggers spam/quality demotion | Cadence limits in the publisher (e.g., max N PRs per week), human gate |
| Cost creep | Budgets, caching, model routing, dry-run mode |
| LangGraph or provider API changes | Pin versions; thin wrappers; ADRs; contract tests |
| Scope explosion | Strict phases; CLI before UI; one provider at first |
| Time conflict with flagship project | Timebox P0–P2 first; defer P3+ if it competes |

---

## 21. Open questions

1. Default model provider(s) and monthly budget?
2. Which search provider (and its free tier)?
3. Where does the pipeline run: local only, or a small hosted service for the review UI?
4. One PR per roadmap or per module?
5. Should Checkpoint A (outline approval) be on for all blog runs or only new topics?
6. Which Ben-written samples define the voice profile (aim for 5–10 pieces)?
7. Open-source the pipeline (portfolio value) while keeping the site template separate (sale value)?
