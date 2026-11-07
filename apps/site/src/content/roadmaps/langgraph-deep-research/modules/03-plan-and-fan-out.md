---
title: Plan and Fan-Out
order: 3
estimatedMinutes: 150
objectives:
- Create a planner node that breaks a topic into sub-queries.
- Accumulate evidence (url, title, snippet) in graph state using a reducer.
- Produce a brief with numbered citations.
sources:
- title: Graph API overview - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/graph-api
  accessed: &id001 2026-11-07
- title: Streaming - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/streaming
  accessed: *id001
- title: tools | langchain
  url: https://reference.langchain.com/python/langchain/tools/
  accessed: *id001
- title: Deep Agents overview - Docs by LangChain
  url: https://docs.langchain.com/oss/python/deepagents/overview
  accessed: *id001
resources: []
code:
  startTag: part-2
  endTag: part-3
  compareUrl: https://github.com/BenakKishanJ/langgraph-deep-research/compare/part-2...part-3
  treeUrl: https://github.com/BenakKishanJ/langgraph-deep-research/tree/part-3
  commits:
  - sha: f0cc570
    message: 'part-3: add planner node and state extensions'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/f0cc570431ab73789ea89e50e411f0cb205b2caf
  - sha: ad306c2
    message: 'part-3: add search fan-out, evidence accumulation, and citation brief'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/ad306c22ab0e8543d4a2e0b399d50b6bdc2b18bf
  - sha: 94b05f8
    message: 'part-3: update docs and fix ui_api newline'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/94b05f862915ee2734e5ec4b1c2b3ddb79e955ec
  files:
  - docs/ARCHITECTURE.md
  - docs/PARTS.md
  - src/langgraph_deep_research/brief.py
  - src/langgraph_deep_research/graph.py
  - src/langgraph_deep_research/planner.py
  - src/langgraph_deep_research/tools.py
  - src/langgraph_deep_research/ui_api.py
  - tests/test_deep_research.py
quiz:
- id: q1
  question: In a Plan-and-Fan-Out graph, what should the planner node return so that downstream nodes can execute the fan-out step?
  type: single
  options:
  - id: a
    text: A single combined search query string
  - id: b
    text: The final brief with numbered citations
  - id: c
    text: A list of independent sub-queries, each targeting a distinct aspect of the topic
  - id: d
    text: A merged list of URLs and snippets from previous runs
  correct:
  - c
  explanation: 'The planner''s job is decomposition: it analyzes the topic and emits multiple independent sub-queries. Downstream fan-out nodes then run these in parallel. The planner does not execute searches or write the final brief.'
  difficulty: medium
  hint: Think about what must exist before parallel search nodes can run.
- id: q2
  question: Why is a reducer function used to update the evidence field in graph state when several parallel search nodes finish at different times?
  type: single
  options:
  - id: a
    text: To merge each node's new evidence into the existing list instead of overwriting it
  - id: b
    text: To encrypt each snippet before it is stored in state
  - id: c
    text: To automatically assign citation numbers to every snippet
  - id: d
    text: To filter out any evidence that contains the topic keyword
  correct:
  - a
  explanation: Parallel branches writing to the same state key would clobber one another with plain assignment. A reducer combines incoming updates (for example, appending new url/title/snippet records) so no evidence is lost.
  difficulty: medium
  hint: Consider what happens if two nodes try to set the same state field simultaneously.
- id: q3
  question: When writing the final brief, how should the brief node reference evidence so that citations are accurate and traceable?
  type: single
  options:
  - id: a
    text: Cite sources in the order the planner originally listed the sub-queries
  - id: b
    text: Use the internal ranking returned by the search engine
  - id: c
    text: Assign random numbers to make the brief appear neutral
  - id: d
    text: Use the index of each evidence entry in the accumulated state list as its citation number
  correct:
  - d
  explanation: Numbering citations by position in the accumulated evidence list creates a stable, deterministic mapping between a citation in the text and a specific url/title/snippet in state.
  difficulty: medium
  hint: The brief writer reads from the same evidence accumulator that the search nodes wrote to.
- id: q4
  question: If two parallel search nodes return the same URL with different snippets, what is a reasonable reducer behavior for the evidence list?
  type: single
  options:
  - id: a
    text: Discard the older snippet and keep only the newest one
  - id: b
    text: Append both entries and let the brief node decide how to handle repetition
  - id: c
    text: Replace the entire evidence list with only the duplicate entry
  - id: d
    text: Stop the graph and raise an error
  correct:
  - b
  explanation: A reducer typically appends new evidence to the existing list. Deduplication or snippet selection is better handled later, such as in the brief node, rather than losing potentially useful context during accumulation.
  difficulty: medium
  hint: Accumulation and deduplication are separate concerns.
lastReviewed: *id001
draft: false
pipelineRunId: 030c8433a4
---

## What we add

You'll add a planner node that breaks a user's topic into 3–5 sub‑queries, extend the graph state with `sub_queries`, `evidence` (a list that accumulates via a reducer), and `brief`. Then you'll wire a fan‑out that launches one search per sub‑query in parallel, collect every result as evidence, and finally produce a markdown brief with numbered citations.

## How it works

The deep research graph uses a `DeepResearchState` that adds three channels to the base `State`:

- `sub_queries` — a plain list of strings written once by the planner.
- `evidence` — an `Annotated[list[dict[str, str]], operator.add]` channel. The `operator.add` reducer appends each search's output, so the brief node sees all sources regardless of how many searches ran.
- `brief` — the final markdown string.

The flow is:

1. `planner_node` calls the model with a planning prompt, parses the lines, and returns `sub_queries` plus an assistant message.
2. `fan_out_node` is a join node that returns an empty dict; the real fan‑out happens in the conditional edge registered on it. The router `fan_out_router` returns one `Send` per sub‑query, each invoking `search_node` with `{"query": q}` [S1].
3. `search_node` runs `web_search_results` and returns `evidence` entries. Because `evidence` uses `operator.add`, the results from all parallel searches accumulate.
4. `brief_node` calls `build_brief` from `brief.py`, which formats the evidence list into a markdown string with `[1]`, `[2]`, … citations, and writes both the brief and a final assistant message.

## Step by step

### f0cc570 — add planner node and state extensions

This commit introduces `planner.py` and extends the state schema.

In `planner.py` you'll see a prompt template that asks the model to output one sub‑query per line, and a `planner_node` function that extracts the topic from the first user message, invokes the model, and returns the parsed lines as `sub_queries`:

```python
def planner_node(state: DeepResearchState) -> dict:
    user_message = state["messages"][0]
    topic = user_message.content if hasattr(user_message, "content") else str(user_message)
    model = graph_module._default_model()
    prompt = _PLANNER_PROMPT.format(topic=topic)
    response = model.invoke(prompt)
    lines = [line.strip() for line in response.content.splitlines() if line.strip()]
    return {"sub_queries": lines, "messages": [AIMessage(content=f"Sub-queries: {lines}")]}
```

The state class in `graph.py` gains two new keys:

```python
class DeepResearchState(TypedDict):
    messages: Annotated[list, operator.add]
    sub_queries: list[str]
    evidence: Annotated[list[dict[str, str]], operator.add]
    brief: str
```

`evidence` is the only channel with a reducer; without `operator.add` each search would overwrite the previous results.

### ad306c2 — add search fan‑out, evidence accumulation, and citation brief

This commit adds the fan‑out machinery and the brief builder.

`fan_out_node` is deliberately empty — it exists only as a target for the conditional edge:

```python
def fan_out_node(state: DeepResearchState) -> dict:
    return {}
```

The router creates one `Send` per sub‑query:

```python
def fan_out_router(state: DeepResearchState) -> list:
    return [Send("search", {"query": q}) for q in state["sub_queries"]]
```

`search_node` calls the existing `web_search_results` helper and returns the list of `{url, title, snippet}` dicts:

```python
def search_node(state: dict) -> dict:
    from .tools import web_search_results
    results = web_search_results(state["query"])
    return {"evidence": results}
```

`brief_node` builds the final markdown and appends an assistant message:

```python
def brief_node(state: DeepResearchState) -> dict:
    from .brief import build_brief
    brief = build_brief(state["evidence"])
    return {"brief": brief, "messages": [AIMessage(content=brief)]}
```

`build_brief` in `brief.py` iterates over the evidence list and formats each entry as `[i] Title (URL)`, or returns a placeholder when the list is empty.

The graph wiring in `build_deep_research_graph` connects the nodes and registers the conditional edge:

```python
g.add_conditional_edges("fan_out", fan_out_router)
g.add_edge("search", "brief")
```

Because every `Send` targets `search`, and `search` always flows to `brief`, the brief runs exactly once after all parallel branches finish.

### 94b05f8 — update docs and fix ui_api newline

The documentation in `ARCHITECTURE.md` now describes the deep research graph, its state channels, and the four nodes. In `ui_api.py` a stray newline was removed so `ask()` returns the brief without an extra line break:

```python
def ask(question: str) -> str:
    result = build_deep_research_graph().invoke({"messages": [("user", question)]})
    return result["brief"]
```

## Wrap-up

You now have a graph that plans, fans out, searches in parallel, and writes a cited brief. The key patterns are the `operator.add` reducer on `evidence` and the `Send`‑based fan‑out from a router function.

## Exercises

**Exercise 1: make the planner return exactly three sub-queries.**  
*Acceptance:*  
- `planner_node` returns a `sub_queries` list of length 3 even when the raw model output has extra lines.  
- The existing offline tests still pass: `uv run pytest` is green.  
*Hint:* Trim to the first three parsed lines in `planner_node` (or adjust `_PLANNER_PROMPT` in `planner.py` to demand exactly three).

**Exercise 2: cap the brief at five citations.**  
*Acceptance:*  
- `build_brief` includes at most five `[n]` entries when `evidence` has more than five items.  
- The empty-evidence message (`# Research Brief\n\nNo sources found.`) is unchanged.  
*Hint:* Slice `evidence[:5]` in `build_brief` and follow the existing formatting loop; `test_build_brief_with_evidence` shows the pattern.

**Exercise 3: track which sub-query produced each evidence item.**  
*Acceptance:*  
- Each evidence dict gains a `query` key set from `state["query"]` in `search_node`.  
- The brief shows the originating sub-query next to each citation, and all tests still pass.  
*Hint:* Change `search_node` to spread the result dicts and add `"query": state["query"]`; update `build_brief` to read the new field.
