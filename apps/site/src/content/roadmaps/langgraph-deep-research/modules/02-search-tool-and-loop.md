---
title: Search Tool and Loop
order: 2
estimatedMinutes: 120
objectives:
- Wrap Tavily search as a langchain @tool.
- Add a tool node and conditional edge to create an ask/tool loop.
- Ask a question and receive an answer with listed web sources.
sources:
- title: Graph API overview - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/graph-api
  accessed: &id001 2026-11-07
- title: tools | langchain
  url: https://reference.langchain.com/python/langchain/tools/
  accessed: *id001
- title: Tavily Search - Tavily Docs
  url: https://docs.tavily.com/documentation/api-reference/endpoint/search
  accessed: *id001
- title: Quickstart - Tavily Docs
  url: https://docs.tavily.com/sdk/python/quick-start
  accessed: *id001
- title: Build - Docs by LangChain
  url: https://docs.langchain.com/build-overview
  accessed: *id001
resources: []
code:
  startTag: part-1
  endTag: part-2
  compareUrl: https://github.com/BenakKishanJ/langgraph-deep-research/compare/part-1...part-2
  treeUrl: https://github.com/BenakKishanJ/langgraph-deep-research/tree/part-2
  commits:
  - sha: f665621
    message: 'part-2: Add operator.add reducer to State.messages so ask/tool loop accumulates history'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/f665621544f9c6e6c382af1d78cf36b97c3ce467
  - sha: 98aae9a
    message: 'part-2: Document the accumulate reducer in architecture docs'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/98aae9aab604364215eb325c7a1cb077473ba771
  files:
  - docs/ARCHITECTURE.md
  - src/langgraph_deep_research/graph.py
quiz:
- id: q1
  question: Which of the following best describes how to wrap a Tavily search call as a LangChain tool using the @tool decorator?
  type: single
  options:
  - id: a
    text: Decorate a Python function that accepts a query string, calls Tavily, and returns the results as a string or JSON-serializable payload.
  - id: b
    text: Decorate a class that inherits from BaseRetriever and returns LangChain Document objects.
  - id: c
    text: Decorate a function that returns an AgentAction object to tell LangGraph which tool to run.
  - id: d
    text: Decorate an async generator that yields partial search results to the model.
  correct:
  - a
  explanation: The @tool decorator turns a plain function into a LangChain tool; the function's return value becomes the tool output sent back to the model, so it should be a simple string or JSON-serializable result, not a retriever Document or AgentAction.
  difficulty: medium
  hint: Think about what the model receives back after a tool call—just the output payload, not a retriever or internal agent action.
- id: q2
  question: In a LangGraph ask/tool loop, what should the conditional edge after the model node inspect to decide whether to go to the tool node or end?
  type: single
  options:
  - id: a
    text: Whether the latest message contains a tool_call from the model.
  - id: b
    text: Whether the user's original question contains a question mark.
  - id: c
    text: Whether the Tavily API key is present in environment variables.
  - id: d
    text: Whether the tool node has already been visited once.
  correct:
  - a
  explanation: The conditional edge checks the model's output for a requested tool call; if present, route to the tool node, otherwise finish. It does not depend on punctuation, API keys, or visit counts.
  difficulty: medium
  hint: Look at the model's message, not the user's input or environment, to decide if a tool was requested.
- id: q3
  question: After the tool node returns Tavily search results, how should the agent incorporate web sources into the final answer?
  type: single
  options:
  - id: a
    text: Return the raw Tavily response object directly as the assistant's final message.
  - id: b
    text: Parse the results for URLs and titles, then cite them explicitly in the answer text.
  - id: c
    text: Instruct the user to search Tavily manually for the sources.
  - id: d
    text: Substitute the model's chain-of-thought trace for the list of web sources.
  correct:
  - b
  explanation: The final answer should be human-readable and verifiable, so relevant URLs/titles from the search results should be extracted and cited. Raw JSON is not user-friendly, and the reasoning trace is not a web source.
  difficulty: medium
  hint: The user wants to see where the information came from, not the internal API response.
lastReviewed: *id001
draft: false
pipelineRunId: 030c8433a4
---

## What we add

You now turn the Tavily search into a LangChain `@tool`, wire it into the graph with a `ToolNode`, and add a conditional edge that loops back to the agent while the model issues tool calls. After this part you can ask a question and get an answer that lists the web sources the agent consulted.

## How it works

The graph keeps a single list of messages in `State.messages`. LangGraph channels are last‑write‑win by default, so a plain `list` would be replaced on every node return and the ask/tool loop would lose the user question and the tool results. To make history accumulate you attach the `operator.add` reducer to the channel: `messages: Annotated[list, operator.add]` [S1]. Each node returns a partial update — the agent appends its reply (which may carry tool calls), the tool node appends `ToolMessage`s with the search results, and the agent appends the final answer. The reducer concatenates these updates, so the full conversation survives the loop.

The loop itself is built from three pieces:

- `agent_node` — calls the model with `web_search` bound as a tool and appends the assistant reply.
- `tools` — a `ToolNode` that runs `web_search` for every tool call the model issued and appends the results.
- `should_continue` — a conditional edge from `agent` that routes to `tools` while the last message has tool calls, or ends the run when the model gives a final answer.

When you invoke the graph with `{"messages": [("user", "...")]}`, the agent first returns a message with a tool call, the tool node executes the search and returns a `ToolMessage`, the conditional edge sends the flow back to the agent, and the agent produces the final answer. The final state contains the user question, the tool‑call message, the tool result, and the answer — four messages in total for one search.

## Step by step

### Commit `62ae3b9` — Add `web_search` tool in `tools.py`

This commit introduces the search tool. It defines a function decorated with `@tool` that wraps the Tavily Search API [S2]. The function takes a query string, creates a `TavilyClient` using the API key from `load_settings()` [S3], calls `search` with the default depth and `max_results=5`, and formats the response into readable blocks.

The trimmed diff shows the core of the new function:

```python
@tool
def web_search(query: str) -> str:
    """Search the web and return results."""
    settings = load_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)
    results = client.search(query, max_results=5)
```

The formatting logic turns each result into a `Title:` / `URL:` / `Content:` block. You can see the full implementation at 

<figure class="snippet-fig">
```python


def _client() -> TavilyClient:
    """Build a Tavily client from current settings."""
    return TavilyClient(api_key=load_settings().tavily_api_key)


@tool
def web_search(query: Annotated[str, "The search query to run."]) -> str:
    """Search the web for recent information about a topic.

    Returns formatted results with titles, URLs, and content snippets.
    """
    client = _client()
    response = client.search(query, max_results=5, search_depth="basic")
    results = response.get("results", [])
    if not results:
        return "No results found."
    blocks = []
    for item in results:
        blocks.append(
            f"Title: {item.get('title', '')}\n"
            f"URL: {item.get('url', '')}\n"
            f"Content: {item.get('content', '')}"
        )
```
<figcaption><code>src/langgraph_deep_research/tools.py</code>, lines 10–34 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-2/src/langgraph_deep_research/tools.py#L10-L34">view on GitHub</a></figcaption>
</figure>

.

### Commit `f665621` — Add `operator.add` reducer to `State.messages`

The diff modifies `src/langgraph_deep_research/graph.py`. It imports `operator` and changes the `State` definition:

```python
import operator
from typing import Annotated, TypedDict

class State(TypedDict):
    messages: Annotated[list, operator.add]
```

Before this change `messages` was a plain `list`; after it, every node return is appended to the existing list instead of replacing it. This is the minimal fix that makes the ask/tool loop work. You can see the current definition at 

<figure class="snippet-fig">
```python
class State(TypedDict):
    # LangGraph channels without a reducer are last-write-wins: a plain
    # list would be replaced on every node return, so the ask/tool loop
    # would lose the user question and tool results. operator.add makes the
    # messages channel accumulate across nodes.
    messages: Annotated[list, operator.add]
```
<figcaption><code>src/langgraph_deep_research/graph.py</code>, lines 15–20 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-2/src/langgraph_deep_research/graph.py#L15-L20">view on GitHub</a></figcaption>
</figure>

.

### Commit `ff2d677` — Wire the tool into the graph

This commit updates `graph.py` to connect the agent, the tool node, and the conditional edge. The `agent_node` binds `web_search` to the model so the model can issue tool calls:

```python
agent_node = model.bind_tools([web_search])
```

A `ToolNode` runs the tool whenever the model issues a call:

```python
tools = ToolNode([web_search])
```

The `should_continue` conditional edge checks whether the last message carries tool calls and routes back to `tools` or ends the run:

```python
def should_continue(state):
    if state["messages"][-1].tool_calls:
        return "tools"
    return "end"
```

The graph is then compiled with these nodes and edges. The full wiring is at 

<figure class="snippet-fig">
```python
    return ChatOpenAI(
        model=s.model,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
    )


def agent_node(state: State) -> State:
    """Call the model with tools bound; append the assistant reply."""
    model = _default_model().bind_tools([web_search])
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def should_continue(state: State) -> str:
    """Route to the tool node when the model asks for a tool call."""
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return "end"


def build_graph():
    tool_node = ToolNode([web_search])
    g = StateGraph(State)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "end": END}
    )
    g.add_edge("tools", "agent")
    return g.compile()


graph = build_graph()
```
<figcaption><code>src/langgraph_deep_research/graph.py</code>, lines 25–60 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-2/src/langgraph_deep_research/graph.py#L25-L60">view on GitHub</a></figcaption>
</figure>

.

### Commit `98aae9a` — Document the accumulate reducer in architecture docs

This commit updates `docs/ARCHITECTURE.md` to explain why the reducer is necessary. The added paragraph describes the last‑write‑win default, the role of `operator.add`, and how messages accumulate across the agent/tool loop. The documentation now matches the implementation, so a new developer can read the file and understand the state design without inspecting the code. The relevant section is at 

<figure class="snippet-fig">
```markdown
## State

`State` is a `TypedDict` with a single `messages` channel (list of
`BaseMessage`). The channel uses the `operator.add` accumulator reducer:
without it, LangGraph channels are last-write-wins and each node return
would wipe the previous messages, breaking the ask/tool loop. Messages
accumulate across the loop: the agent appends its reply (which may carry
tool calls), the tool node appends the tool results, and the agent appends
the final answer.
```
<figcaption><code>docs/ARCHITECTURE.md</code>, lines 9–17 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-2/docs/ARCHITECTURE.md#L9-L17">view on GitHub</a></figcaption>
</figure>

.

### Commit `7c8c9be` — Add `tavily-python` dependency

This one-line change adds `tavily-python` to the project dependencies so the `TavilyClient` import in `tools.py` resolves. The entry appears in `pyproject.toml` alongside the other runtime packages. You can see it at 

<figure class="snippet-fig">
```toml
[dependency-groups]
dev = ["pytest>=8", "ruff>=0.11"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
<figcaption><code>pyproject.toml</code>, lines 20–25 · <a href="https://github.com/BenakKishanJ/langgraph-deep-research/blob/part-2/pyproject.toml#L20-L25">view on GitHub</a></figcaption>
</figure>

.

## Wrap-up

You have added a search tool and a loop that lets the agent call it as many times as needed. The key insight is the `operator.add` reducer: without it the loop collapses to a single final message, and with it the full conversation — user question, tool calls, tool results, final answer — is preserved. The tests use a fake model and a fake Tavily client, so you can run them offline and verify the loop behaviour.

## Exercises

**Exercise 1: Break the reducer and watch the loop fail**
- Task: temporarily change `messages: Annotated[list, operator.add]` back to a plain `list` in `graph.py`, run `pytest tests/test_graph.py`, and observe that the assertion on message count fails.
- Acceptance:
  - The test `test_agent_loop_runs_tool_then_answers` reports a mismatch in the number of messages.
  - You understand that the tool result disappears because the channel is overwritten.
- Hint: the test expects four messages; with last‑write‑win you will only see the final answer.

**Exercise 2: Add a second tool and verify accumulation**
- Task: create a second `@tool` (for example a dummy `echo` tool) in `tools.py`, bind it alongside `web_search` in `agent_node`, and write a small script that invokes the graph with a question that triggers both tools. Print the full `messages` list to confirm each tool result is appended.
- Acceptance:
  - The printed list contains the user message, two tool‑call messages, two `ToolMessage`s, and the final answer.
  - The order matches the sequence of tool calls.
- Hint: you can reuse the `FakeModel` pattern from the tests to force two consecutive tool calls.

**Exercise 3: Write a test that checks the reducer directly**
- Task: add a test in `tests/test_graph.py` that builds the graph, calls it with a user message, and asserts that `result["messages"][0]` is the original user message and that `len(result["messages"])` equals the expected number of turns.
- Acceptance:
  - The test passes with the current implementation.
  - The test fails if you revert the reducer, proving the reducer is what preserves the history.
- Hint: use the same `monkeypatch` pattern already present in the file to inject a fake model and fake client.
