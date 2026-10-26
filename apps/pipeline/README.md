# BenKi content pipeline (LangGraph)

Turns sources you choose into a reviewed blog post and, when you click **Approve**, commits it to the Astro site's `main` branch (which auto-deploys).

```
you (admin page) ──> local API (FastAPI) ──> LangGraph run ──> data/*.db (checkpoints survive restarts)
                                                    └─ on approve: write src/content/blog/<slug>.md, commit, push to main
```

## Run it

```bash
cd apps/pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # set GOOGLE_API_KEY and SITE_REPO_PATH (your local clone of the Astro site)
pipeline serve              # prints an admin token the first time

# in the Astro site repo:
npm run dev                 # open http://localhost:4321/admin/ and paste the token
```

Try it safely first: set `PUBLISH_MODE=files` in `.env`. Approve then only writes the file into the site repo, with no commit and no push.

## What a run does (blog mode)

1. **ingest**: fetches your URLs (respects robots.txt, blocks private addresses, 3 MB cap), reads PDFs, cleans text, flags instruction-like text, summarises each source.
2. **claims**: extracts atomic claims, each tied to the source ids that support it.
3. **outline**: proposes an angle and sections mapped to claims. **You approve or edit it** (can be turned off per run).
4. **write -> critique -> revise** (max `MAX_AUTO_REVISIONS`): drafts in your voice (`voice/ben.md`) using only the claims. A critic (own model setting) scores it and lists unsupported statements.
5. **finalize**: SEO metadata plus deterministic **gates**: schema, citations, section coverage, unsupported claims, similarity to sources, quote length, filler phrases, length, structure, source safety, link check.
6. **your review**: read the draft, sources, claims, checks, diff; edit markdown or metadata directly; leave comments for another pass; approve, request changes, or reject.
7. **publish**: validates against the site's content schema, numbers citations by first use, writes the file, `git pull --rebase`, commit, push.

Rules the pipeline enforces: nothing publishes without your approval; schema and citation failures can never be overridden; other failing gates need an explicit "publish anyway"; your direct edits always win over the model's.

## Where things live
- `src/pipeline/graphs/blog.py`: the graph (nodes, routing, interrupts)
- `src/pipeline/prompts.py`: every prompt. `voice/ben.md` and `voice/banned.txt`: your voice
- `src/pipeline/tools/`: `ingest.py`, `gates.py`, `publisher.py`
- `src/pipeline/api.py`: the HTTP API the admin page uses (token header, CORS limited to localhost:4321)
- `tests/`: 13 tests using a fake LLM (full run incl. outline loop, auto-revision, human changes, git publish to a temp remote)

```bash
pytest -q
```

## Notes
- Models: defaults are `gemini-3.1-flash-lite` (fast) and `gemini-3.5-flash` (strong, critic). Gemini 2.5 models were scheduled for shutdown on 16 Oct 2026, and names change often, so check https://ai.google.dev/gemini-api/docs/models and edit `.env`. To use Claude or OpenAI: install the extra, set `LLM_PROVIDER` and the `MODEL_*` names.
- Tokens are tracked per run; set `PRICE_PER_MTOK_IN/OUT` to see an estimated cost.
- Not included yet: roadmap mode (next), web search, uploading local PDFs from the UI (PDF *links* work), running code samples, a hosted deployment.
- Security: the API binds to 127.0.0.1, requires the token, and renders drafts with raw HTML disabled. Source text is always treated as data, never instructions.
