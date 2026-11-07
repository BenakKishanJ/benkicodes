---
title: Reflection and Refinement
order: 4
estimatedMinutes: 120
objectives:
- Add a reflection node that critiques collected evidence.
- Implement follow-up searches bounded by a rounds budget.
- Stream progress updates to the UI.
sources:
- title: Streaming - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/streaming
  accessed: &id001 2026-11-07
- title: Persistence - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/persistence
  accessed: *id001
- title: Fault tolerance - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/fault-tolerance
  accessed: *id001
- title: Event streaming - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/event-streaming
  accessed: *id001
- title: Interrupts - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/interrupts
  accessed: *id001
resources: []
code:
  startTag: part-3
  endTag: part-4
  compareUrl: https://github.com/BenakKishanJ/langgraph-deep-research/compare/part-3...part-4
  treeUrl: https://github.com/BenakKishanJ/langgraph-deep-research/tree/part-4
  commits:
  - sha: afae481
    message: 'part-4: add reflection node and rounds budget'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/afae4811867f56d260455ad06b2dfbf1b098b1b8
  - sha: 45df8b9
    message: 'part-4: stream progress updates to the UI'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/45df8b961fa5587fb7e57554067b75cb8d43247d
  - sha: 03a5403
    message: 'part-4: update architecture docs and parts index'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/03a5403106bcd517ab3cc75610eac1e5f08cedaf
  files:
  - docs/ARCHITECTURE.md
  - docs/PARTS.md
  - src/langgraph_deep_research/graph.py
  - src/langgraph_deep_research/reflection.py
  - src/langgraph_deep_research/ui/server.py
  - src/langgraph_deep_research/ui_api.py
  - tests/test_deep_research.py
  - tests/test_streaming.py
quiz:
- id: q1
  question: In an agentic research graph, what is the primary role of a reflection node positioned after evidence collection?
  type: single
  options:
  - id: a
    text: To compose the final cited answer and persist it to disk.
  - id: b
    text: To evaluate whether the gathered evidence is sufficient, relevant, and consistent, and to identify any remaining gaps.
  - id: c
    text: To broaden all search queries before the first retrieval round begins.
  - id: d
    text: To cache raw search-result HTML for later replay.
  correct:
  - b
  explanation: 'The reflection node acts as a critic: it reviews the evidence collected so far, judges whether it adequately supports the answer, spots contradictions or missing pieces, and decides whether the loop should continue or conclude. It does not author the final answer, replace retrieval, or manage raw HTML caching.'
  difficulty: medium
  hint: Focus on what happens between gathering evidence and producing the final answer.
- id: q2
  question: Why should follow-up searches in a research loop be constrained by a maximum number of rounds?
  type: single
  options:
  - id: a
    text: To guarantee that every relevant source on the web is visited.
  - id: b
    text: To ensure the reflection node executes at least once per search result.
  - id: c
    text: To bound execution time and cost by preventing the agent from endlessly issuing new searches.
  - id: d
    text: To automatically promote intermediate findings into the final answer.
  correct:
  - c
  explanation: If the reflection node can always identify a gap, it could trigger another search indefinitely, causing unbounded latency and API cost. A rounds budget forces termination after a fixed number of iterations, making the process predictable.
  difficulty: medium
  hint: Consider what could happen if the agent never decides it has enough evidence.
- id: q3
  question: Which pattern best supports streaming progress updates to the frontend during a bounded multi-round research process?
  type: single
  options:
  - id: a
    text: Emit structured events (for example, round_started, evidence_collected, reflection_critiqued) through a stream as each node executes.
  - id: b
    text: Buffer all node outputs in memory and send them as one large JSON payload after the final round completes.
  - id: c
    text: Write progress to a server log and ask the user to refresh the browser to see updates.
  - id: d
    text: Suppress all intermediate output and stream only the final answer once the budget is exhausted.
  correct:
  - a
  explanation: 'Streaming incremental events lets the UI render a live trace (e.g., ''Round 2: searching…'', ''Reflection: evidence insufficient'') instead of making the user wait for a single monolithic response. This improves transparency and perceived performance during long-running agent tasks.'
  difficulty: medium
  hint: Think about how a user experiences latency while waiting for a multi-step process to finish.
lastReviewed: *id001
draft: false
pipelineRunId: 030c8433a4
---

## What we add

You can now add a reflection step to the deep research graph. After the planner fans out searches and the search nodes collect evidence, a reflection node asks the LLM to critique that evidence and suggest up to three follow-up queries. A rounds budget (default 2) caps how many times the loop can iterate, so the agent refines its research instead of looping forever. Finally, the UI streams progress events — one per node execution — as Server-Sent Events, so the front end can show the planner, search, reflection, and brief nodes running in real time.

By the end of this part you can:
- Add a reflection node that critiques evidence and proposes follow-up searches.
- Bound a LangGraph loop with a rounds counter.
- Emit progress events from `graph.stream` with `stream_mode="updates"`.

## How it works

The reflection node is a normal LangGraph node: it takes the current state, builds a prompt from the accumulated evidence, calls the model, and parses the response into a list of follow-up query strings [S1]. The node also increments a `round` counter and appends an assistant message describing what it decided.

The loop is bounded by `should_continue_reflection`, a conditional edge that routes back to `fan_out` when two conditions hold: `follow_up_queries` is non-empty and `round` is below `max_rounds` (2). Otherwise it routes to `brief`. Each iteration re-runs the fan-out and search nodes, and the `evidence` channel — which uses `operator.add` — keeps accumulating entries from every search.

A subtle point: `fan_out_node` returns an empty dict on purpose. It must NOT clear `follow_up_queries`, because the router that follows it reads `follow_up_queries` to decide which queries to run this round. If the node wiped them, the loop would fall back to the original `sub_queries` and re-search the same topics forever. The reflection node overwrites `follow_up_queries` on every call, so the list naturally refreshes each round; the rounds counter is what actually stops the loop.

For streaming, `ask_stream` calls `graph.stream` with `stream_mode="updates"`. In this mode LangGraph yields one chunk per node execution, where each chunk is a dict mapping node name to that node's return value. The endpoint wraps each chunk as a Server-Sent Event (`event: <node>\ndata: <json>`) and yields it to the browser [S1].

## Step by step

### Commit afae481 — add reflection node and rounds budget

Create `src/langgraph_deep_research/reflection.py`. The file defines a prompt template, the `reflection_node` function, and the `should_continue_reflection` router.



<figure class="snippet-fig">
```python
_REFLECT_SYSTEM = (
    "You are a research referee. Review the following evidence and decide "
    "whether more research is needed. If yes, suggest up to 3 follow-up "
    "queries, each on a new line. If no more research is needed, respond "
    "with an empty line."
)
_REFLECT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _REFLECT_SYSTEM),
    ("human", "{evidence}"),
])


def reflection_node(state: DeepResearchState) -> dict:
    """Produce follow-up queries from the current evidence."""
    evidence = state.get("evidence", [])
    evidence_text = "\n".join(
        f"- {item.get('title', '')}: {item.get('snippet', '')}" for item in evidence
    )
    model = graph_module._default_model()
    prompt = _REFLECT_PROMPT.format(evidence=evidence_text)
    response = model.invoke(prompt)
    lines = [line.strip() for line in response.content.splitlines() if line.strip()]
    round_number = state.get("round", 0) + 1
    return {
        "follow_up_queries": lines,
        "round": round_number,
        "messages": [AIMessage(content=f"Reflection round {round_number}: {lines}")],
    }


def should_continue_reflection(state: DeepResearchState) -> str:
    """Route to fan_out if there are follow-up queries and budget remains."""
    max_rounds = 2
    if state.get("follow_up_queries") and state.get("round", 0) < max_rounds:
        return "more"
    return "end"
```
<figcaption><code>src/langgraph_deep_research/reflection.py</code>, lines 10–45 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-4/src/langgraph_deep_research/reflection.py#L10-L45">view on GitHub</a></figcaption>
</figure>



The prompt asks the model to act as a research referee and suggest up to three follow-up queries, one per line. The node joins the evidence entries into a bulleted text block, invokes the model, and splits the response on newlines. It returns the parsed lines as `follow_up_queries`, increments `round`, and appends an assistant message. Notice the use of `state.get("round", 0)` — if `round` is missing from the state, it defaults to 0 rather than crashing.

Wire it into the graph in `graph.py`. The `build_deep_research_graph` function already imports `reflection_node` and `should_continue_reflection` and registers the `reflection` node between `search` and `brief`:



<figure class="snippet-fig">
```python
def build_deep_research_graph():
    """Compile planner → fan-out → search → reflection → (loop or brief)."""
    from .planner import planner_node
    from .reflection import reflection_node, should_continue_reflection

    g = StateGraph(DeepResearchState)
    g.add_node("planner", planner_node)
    g.add_node("fan_out", fan_out_node)
    g.add_node("search", search_node)
    g.add_node("reflection", reflection_node)
    g.add_node("brief", brief_node)
    g.set_entry_point("planner")
    g.add_edge("planner", "fan_out")
    # no path map: the router returns Send objects, so LangGraph starts one
    # search invocation per Send and then joins the parallel branches.
    g.add_conditional_edges("fan_out", fan_out_router)
    # search results flow into reflection, which may loop back to fan_out
    # or end at the brief.
    g.add_edge("search", "reflection")
    g.add_conditional_edges(
        "reflection",
        should_continue_reflection,
        {"more": "fan_out", "end": "brief"},
    )
    return g.compile()
```
<figcaption><code>src/langgraph_deep_research/graph.py</code>, lines 113–137 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-4/src/langgraph_deep_research/graph.py#L113-L137">view on GitHub</a></figcaption>
</figure>



The conditional edge on `reflection` routes to `fan_out` when the router returns `"more"`, or to `brief` when it returns `"end"`. The tests in `test_deep_research.py` cover both paths: one starts at `round: 2` so reflection stops immediately, and another uses a count-based fake model that produces a follow-up on the second call to verify the loop runs exactly once.

### Commit 45df8b9 — stream progress updates to the UI

The non-streaming path already worked. This commit adds a streaming variant in `ui_api.py`:



<figure class="snippet-fig">
```python
def ask_stream(question: str):
    """Yield progress events as Server-Sent Events while running the graph."""
    for chunk in build_deep_research_graph().stream(
        {"messages": [("user", question)]},
        stream_mode="updates",
    ):
        for node, update in chunk.items():
            # default=str: node updates may contain AIMessage objects
            yield f"event: {node}\ndata: {json.dumps(update, default=str)}\n\n"
```
<figcaption><code>src/langgraph_deep_research/ui_api.py</code>, lines 15–23 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-4/src/langgraph_deep_research/ui_api.py#L15-L23">view on GitHub</a></figcaption>
</figure>



`stream_mode="updates"` gives you one chunk per node execution. Each chunk is a dict like `{"planner": {...}}` or `{"search": {...}}`. The inner loop iterates over the dict items, serializes the update to JSON (with `default=str` because node updates may contain `AIMessage` objects), and formats it as an SSE event.

The server already exposes the endpoint; this commit wires `ask_stream` into it:



<figure class="snippet-fig">
```python
@app.post("/api/ask-stream")
async def ask_stream_endpoint(request: Request) -> StreamingResponse:
    body = await request.json()
    question = body.get("question", "")
    return StreamingResponse(ask_stream(question), media_type="text/event-stream")
```
<figcaption><code>src/langgraph_deep_research/ui/server.py</code>, lines 54–58 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-4/src/langgraph_deep_research/ui/server.py#L54-L58">view on GitHub</a></figcaption>
</figure>



The test in `test_streaming.py` streams a request through `TestClient` and asserts that events containing `planner`, `search`, `reflection`, and `brief` all arrive. That test exercises the full loop with a fake model and fake Tavily client, so it runs offline.

### Commit 03a5403 — update architecture docs and parts index

The docs get a new "Reflection and Refinement" section describing the bounded loop and the streaming endpoint. The state table in `docs/ARCHITECTURE.md` already lists `follow_up_queries`, `round`, `evidence`, and `brief`; this commit adds the explanation of how the reflection node produces follow-ups and how the rounds budget gates the loop. The `docs/PARTS.md` table gets the `part-4` row so the index stays current.

## Wrap-up

You now have a deep research graph that plans, searches, reflects, and writes a cited brief — with a hard cap on how many refinement rounds it can run. The streaming endpoint turns the graph's node-by-node progress into Server-Sent Events, so the UI can show progress instead of hanging until the whole run finishes. The next part wires this into a real front end and adds the missing pieces (threading, error handling, and a proper HTML page) so the app is usable end to end.

## Exercises

**Exercise 1: make the rounds budget configurable.**  
*Acceptance:*  
- `should_continue_reflection` reads the budget from state (`state.get("max_rounds", 2)`), not a module constant.  
- Existing tests still pass with the default budget of 2.  
- A new test asserts that starting at `round: 0` with `max_rounds: 0` routes straight to `brief`.  
*Hint:* The router already reads `state.get("round", 0)`; add the budget lookup next to it in `reflection.py`.

**Exercise 2: prove the loop stops when reflection returns no follow-ups.**  
*Acceptance:*  
- A graph-level test starts with a model that returns no follow-up queries on its second call and asserts the graph searches exactly one batch of queries.  
- The brief is generated after that single batch.  
*Hint:* Reuse the shared count-based fake model pattern from `test_deep_research_graph_reflection_loop`; `test_reflection_node_no_followups` shows the node-level version.

**Exercise 3: cap evidence growth across rounds.**  
*Acceptance:*  
- After a two-round run the `evidence` list length equals the number of searches actually executed, counted with a recording fake client.  
- The brief contains one `[n]` entry per search.  
*Hint:* Wrapping `FakeClient.search` with a call counter makes the search count assertable; the streaming test's fake is the pattern to copy.
