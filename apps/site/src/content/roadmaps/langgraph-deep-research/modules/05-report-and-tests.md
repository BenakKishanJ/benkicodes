---
title: Report and Tests
order: 5
estimatedMinutes: 150
objectives:
- Write a synthesis node that produces a structured markdown report with bibliography.
- Create a pytest suite with fakes for both the chat model and Tavily, fully offline.
- Run the agent via `uv run deep-research-ui` and verify end-to-end.
sources:
- title: Streaming - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/streaming
  accessed: &id001 2026-11-07
- title: Learn - Docs by LangChain
  url: https://docs.langchain.com/oss/python/learn
  accessed: *id001
- title: Reference - Docs by LangChain
  url: https://docs.langchain.com/oss/python/reference/overview
  accessed: *id001
- title: Contributing - Docs by LangChain
  url: https://docs.langchain.com/oss/python/contributing/overview
  accessed: *id001
- title: Changelog - Docs by LangChain
  url: https://docs.langchain.com/oss/python/releases/changelog
  accessed: *id001
- title: Event streaming - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/event-streaming
  accessed: *id001
resources: []
code:
  startTag: part-4
  endTag: part-5
  compareUrl: https://github.com/BenakKishanJ/langgraph-deep-research/compare/part-4...part-5
  treeUrl: https://github.com/BenakKishanJ/langgraph-deep-research/tree/part-5
  commits:
  - sha: 487f5a2
    message: 'part-5: synthesis node — structured markdown report with bibliography'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/487f5a241202b2c45690480b56f103f5c660cc63
  - sha: 1cee5da
    message: 'part-5: offline pytest suite with fakes for model and Tavily'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/1cee5dae39e25b1046cb42e9865d38a3140fbe44
  - sha: b0e9054
    message: 'part-5: document UI run and offline tests in README and ARCHITECTURE'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/b0e905408aee7ab04ec1f6cc4d02fab871b5c088
  - sha: 03c1516
    message: 'part-5: update docs (architecture, parts index)'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/03c15162b73ee2463a3e2252534b4ffc78199be5
  files:
  - README.md
  - src/langgraph_deep_research/brief.py
  - tests/test_brief.py
  - tests/test_deep_research_offline.py
quiz:
- id: q1
  question: Which elements should the synthesis node include to produce a structured markdown report with bibliography?
  type: single
  options:
  - id: a
    text: A title, sections with headings, inline citations, and a bibliography section mapping citation keys to sources.
  - id: b
    text: Only the final answer text, with raw source URLs appended at the end.
  - id: c
    text: A JSON blob embedded in a markdown code block so the output is machine-readable.
  - id: d
    text: A bulleted list of sources only, since the LLM output already contains the reasoning.
  correct:
  - a
  explanation: A structured markdown report must be human-readable and traceable. Headings organize findings, inline citations connect claims to evidence, and a bibliography maps those keys to full source details. Raw URLs alone lack context, JSON is not a markdown report, and a source-only list omits the synthesis narrative.
  difficulty: medium
  hint: How would a reader verify a specific claim in the report?
- id: q2
  question: How should inline citation markers in the markdown body relate to the bibliography?
  type: single
  options:
  - id: a
    text: They should be arbitrary text highlights with no link to the bibliography.
  - id: b
    text: They should match bibliography keys exactly, e.g. [1] in the text corresponds to [1] in the reference list.
  - id: c
    text: They should be omitted entirely because the bibliography alone is sufficient.
  - id: d
    text: They should repeat full URLs inline instead of using keys.
  correct:
  - b
  explanation: Citation keys act as pointers between the body and the reference list. If the inline marker does not exactly match a bibliography entry, the reader cannot locate the source. Colors or omitted keys break traceability, and repeating full URLs inline harms readability.
  difficulty: medium
  hint: Think of the bibliography as a lookup table keyed by the inline markers.
- id: q3
  question: When creating a fully offline pytest suite for the research agent, how should the chat model and Tavily be handled?
  type: single
  options:
  - id: a
    text: Make real network calls to Tavily and the chat model but skip assertions on responses.
  - id: b
    text: Fake only Tavily, but call the real chat model because it runs locally.
  - id: c
    text: Replace both with fakes/stubs that return deterministic, canned responses so tests run without network.
  - id: d
    text: Skip testing the agent entirely and test only the report node.
  correct:
  - c
  explanation: Fully offline tests cannot depend on Tavily's API or the chat model's network endpoint. Faking both with deterministic canned responses removes network variability and lets you assert exact behavior. Real calls violate the offline constraint, faking only one leaves a network dependency, and skipping agent tests leaves the integration unchecked.
  difficulty: medium
  hint: What does "fully offline" rule out?
- id: q4
  question: What does running `uv run deep-research-ui` primarily do in this project?
  type: single
  options:
  - id: a
    text: Installs a new Python version and creates an unrelated virtual environment.
  - id: b
    text: Runs only the pytest suite and exits without starting any UI.
  - id: c
    text: Compiles the markdown report into a PDF and emails it.
  - id: d
    text: Executes the project's deep-research-ui script using the project's uv-managed environment, launching the agent interface.
  correct:
  - d
  explanation: '`uv run <command>` executes the named command inside the project''s uv-managed environment. `deep-research-ui` is the entry point that starts the agent''s interface, which is what you need for an end-to-end verification run. It is not a test runner, a PDF exporter, or a standalone Python installer.'
  difficulty: medium
  hint: What does `uv run` do with the argument that follows it?
lastReviewed: *id001
draft: false
pipelineRunId: 030c8433a4
---

## What we add

You can now turn the evidence your agent collected into a readable markdown report with a Findings section and a numbered Bibliography, and you can prove the whole pipeline works offline with a pytest suite that fakes both the chat model and Tavily. This part adds the synthesis node, the offline tests, and the docs that tie them together.

## How it works

The synthesis node is a pure function called `build_brief` in `src/langgraph_deep_research/brief.py`. It takes the accumulated evidence list — each item a dict with `url`, `title`, and `snippet` — and writes a markdown report in two passes. First pass writes the Findings section: one bullet per snippet, each cited as `[N]`. Second pass writes the Bibliography: a numbered list with title and URL. If the evidence list is empty, it returns a short "no sources found" message instead of raising, so a search that returns nothing doesn't break the graph.

The implementation is at 

<figure class="snippet-fig">
```python
def build_brief(evidence: list[dict[str, str]]) -> str:
    """Return a structured markdown report with Findings and Bibliography.

    Each finding cites its source as [N] and the numbered Bibliography
    lists every source with its title and URL. Empty evidence yields a
    short "no sources" report.
    """
    if not evidence:
        return "# Research Report\n\nNo sources found."
    lines = ["# Research Report", "", "## Findings", ""]
    for i, item in enumerate(evidence, start=1):
        snippet = item.get("snippet", "")
        lines.append(f"- {snippet} [{i}]")
        lines.append("")
    lines.append("## Bibliography")
    lines.append("")
    for i, item in enumerate(evidence, start=1):
        title = item.get("title", "Untitled")
        url = item.get("url", "")
        lines.append(f"[{i}] {title} - {url}")
    return "\n".join(lines)
```
<figcaption><code>src/langgraph_deep_research/brief.py</code>, lines 5–25 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-5/src/langgraph_deep_research/brief.py#L5-L25">view on GitHub</a></figcaption>
</figure>

.

The key insight for testing is that nothing in the graph calls the real model or Tavily client at import time. Both are looked up at run time through module-level functions: `graph._default_model` and `tools._client`. The planner and reflection nodes call `_default_model()` when they need an LLM; the search node calls `_client()` when it needs a Tavily client. So in a test you monkeypatch those two attributes on their modules, and the graph runs entirely on your fake responses.

When you invoke the graph in a test, you must provide every DeepResearchState channel — `messages`, `sub_queries`, `follow_up_queries`, `round`, `evidence`, `brief`. The state schema expects them all, and a missing key surfaces as a runtime error deep in the graph.

One mistake to avoid: patching an imported name instead of the module attribute the node actually calls. If a node does `from ..graph import _default_model`, patching `langgraph_deep_research.graph._default_model` still works because Python resolves the attribute at call time. But if you patch the wrong module path, the node silently gets the real implementation and makes a network call. Always check which module owns the attribute.

Another trap: leaving real API keys in the test environment. The fakes only work if the graph never reaches the real clients. If a key is present and your patch is slightly wrong, the real client initializes and the test hits the network. Delete the keys or run with a clean env when you run the suite.

## Step by step

### Commit 487f5a2 — synthesis node

This commit adds `src/langgraph_deep_research/brief.py` with the `build_brief` function. It's a pure function: no LLM, no network, no randomness. Give it a list of evidence dicts and it hands back a string.

The format is fixed: `# Research Report`, then `## Findings` with one bullet per snippet cited as `[N]`, then `## Bibliography` with `[N] title - url`. Empty evidence returns `"# Research Report\n\nNo sources found."` instead of raising.

The existing test in `tests/test_brief.py` covers both paths — two sources and the empty case. Run it to confirm:

```sh
uv run pytest tests/test_brief.py -v
```

### Commit 1cee5da — offline pytest suite

This commit adds `tests/test_deep_research_offline.py`, the end-to-end offline test. It defines two fakes:

- `FakeModel` — holds a queue of canned responses and pops one per `invoke`. The planner and reflection nodes both call the model, so the queue drives the whole loop.
- `FakeTavilyClient` — returns canned results keyed by query string from a dict you provide.

The fakes and helpers live at 

<figure class="snippet-fig">
```python
class FakeModel:
    """A chat model that returns canned responses in order."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[str] = []

    def invoke(self, prompt, **kwargs):
        self.calls.append(str(prompt))
        content = self.responses.pop(0) if self.responses else ""
        return AIMessage(content=content)


class FakeTavilyClient:
    """A Tavily client that returns canned results keyed by query."""

    def __init__(self, results_by_query: dict[str, list[dict[str, str]]]):
        self.results_by_query = results_by_query

    def search(self, query, max_results=5, search_depth="basic"):
        return {"results": self.results_by_query.get(query, [])}


def _install_fakes(monkeypatch, model_responses, results_by_query):
    fake_model = FakeModel(model_responses)
    monkeypatch.setattr(graph_module, "_default_model", lambda: fake_model)
    fake_client = FakeTavilyClient(results_by_query)
    monkeypatch.setattr(tools, "_client", lambda: fake_client)


def _initial_state(question: str) -> dict:
    return {
        "messages": [HumanMessage(content=question)],
        "sub_queries": [],
        "follow_up_queries": [],
        "round": 0,
        "evidence": [],
        "brief": "",
    }
```
<figcaption><code>tests/test_deep_research_offline.py</code>, lines 15–53 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-5/tests/test_deep_research_offline.py#L15-L53">view on GitHub</a></figcaption>
</figure>

. The `_install_fakes` helper patches `graph_module._default_model` and `tools._client` with lambdas that return your fakes. The `_initial_state` helper builds a full state dict with all six channels, so the graph never sees a missing key.

Two tests cover the important paths:

- `test_deep_research_single_round` starts at {{code:tests/test_deep_research_offline.py#L56}} — the planner emits two queries, reflection emits nothing, and the brief is built with two evidence items.
- `test_deep_research_reflection_loop` starts at {{code:tests/test_deep_research_offline.py#L90}} — the planner emits one query, reflection emits one follow-up, then nothing. Evidence ends up with three items and `round` at 2.

Run the whole suite to confirm everything passes offline:

```sh
uv run pytest
```

No API keys, no network, under a second.

### Commit b0e9054 — document UI run and offline tests

This commit updates `README.md` with the two ways to run the project: `uv run deep-research-ui` for the live UI at `http://localhost:5102`, and `uv run pytest` for the offline suite. The manual test section tells you to set `OPENROUTER_API_KEY` and `TAVILY_API_KEY` before running the UI for real.

### Commit 03c1516 — update docs

This commit updates the architecture and parts index docs so the new synthesis node and test file appear in the navigation. Housekeeping only — no behaviour changes.

### Commit 3d25778 — restore README fences and align the UI test

Two small leftovers from the review pass: the README's fenced code blocks
came back as bare `sh` lines in the edit, so they were rebuilt (plus a line
making clear the UI is prebuilt); and the part-3 UI adapter test still
expected the brief-style `[1] ...` prefix, so it now asserts the structured
report header, the `## Bibliography` section, and a numbered bibliography
entry.

## Wrap-up

You now have a deterministic synthesis node that turns evidence into a cited report, and a pytest suite that exercises the full graph offline by faking the two run-time lookups. The report format is fixed and simple, which is a feature: the UI renders it without post-processing, and tests can assert on exact strings.

## Exercises

**Exercise 1: add a third source to the single-round offline test.**  
*Acceptance:*  
- `test_deep_research_single_round` gets a third query/result pair and a third line in the planner's canned response.  
- The generated report contains a `[3]` citation and the third URL in the Bibliography.  
- `uv run pytest tests/test_deep_research_offline.py` is green.  
*Hint:* Extend `results_by_query` with the third query and the planner's first canned response with one more query line — the fan-out and bibliography numbering follow automatically.

**Exercise 2: make the Bibliography safe for markdown special characters.**  
*Acceptance:*  
- A bibliography entry whose URL contains `(`, `)`, or `_` renders wrapped in angle brackets (`<...>`) in the report.  
- A plain URL still renders unwrapped, and the existing brief tests still pass.  
*Hint:* Add a small `wrap_url` helper above the f-string in `build_brief`; `test_brief.py` shows the two-path assertion style to reuse.

**Exercise 3: prove the graph stops before a second search when the budget is spent.**  
*Acceptance:*  
- A graph-level test starts with `round: 2` and a fake model whose reflection response includes follow-up queries.  
- Exactly one batch of searches runs, then the brief is built (assert with a counting fake client).  
- The result's `round` equals 3: the reflection node still executes once and increments, and the router stops because `round` is no longer below the budget.  
*Hint:* Start from `test_deep_research_graph_runs` in `tests/test_deep_research.py`; wrap `FakeClient.search` with the counting pattern from the offline suite.
