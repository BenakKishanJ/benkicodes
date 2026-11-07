---
title: Setup and First Graph
order: 1
estimatedMinutes: 90
objectives:
- Create a uv project with langgraph and langchain-openai dependencies.
- Write config.py that reads OPENROUTER_API_KEY and TAVILY_API_KEY from .env.
- Build a single-node StateGraph and connect it to the pre-built UI via ui_api.py.
- Run the local web UI and receive a model reply.
sources:
- title: Quickstart - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/quickstart
  accessed: &id001 2026-11-07
- title: Graph API overview - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/graph-api
  accessed: *id001
- title: Chat model integrations - Docs by LangChain
  url: https://docs.langchain.com/oss/python/integrations/chat
  accessed: *id001
- title: OpenRouter Quickstart Guide
  url: https://openrouter.ai/docs/quickstart
  accessed: *id001
- title: LangGraph overview - Docs by LangChain
  url: https://docs.langchain.com/oss/python/langgraph/overview
  accessed: *id001
resources: []
code:
  startTag: part-0
  endTag: part-1
  compareUrl: https://github.com/BenakKishanJ/langgraph-deep-research/compare/part-0...part-1
  treeUrl: https://github.com/BenakKishanJ/langgraph-deep-research/tree/part-1
  commits:
  - sha: b5bb290
    message: 'part-1: project skeleton, uv dependencies, and config module'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/b5bb290cef66e4528fd7c7844c24d18eb8adca5d
  - sha: 7d689bf
    message: 'part-1: single-node StateGraph and ui_api adapter'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/7d689bf5822065fe1c8835307eb6ec97e72df4b3
  - sha: d9c2d19
    message: 'part-1: pre-built FastAPI UI on localhost:5102'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/d9c2d19f77600cdb66322af8915d7bbbf2834e6c
  - sha: 68b7747
    message: 'part-1: architecture, parts index, and README UI section'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/68b774771e60aefce0b970f22551596bb8e9090c
  - sha: dae4072
    message: 'part-1: fix ui_api import in the pre-built UI server'
    url: https://github.com/BenakKishanJ/langgraph-deep-research/commit/dae4072aa13942f9002804b39da61c89599a0924
  files:
  - README.md
  - docs/ARCHITECTURE.md
  - docs/PARTS.md
  - pyproject.toml
  - src/langgraph_deep_research/config.py
  - src/langgraph_deep_research/graph.py
  - src/langgraph_deep_research/ui/__init__.py
  - src/langgraph_deep_research/ui/server.py
  - src/langgraph_deep_research/ui_api.py
  - tests/test_config.py
  - tests/test_graph.py
  - tests/test_ui.py
quiz:
- id: q1
  question: You initialized a new folder with `uv init` and need to declare LangGraph and LangChain OpenAI as project dependencies. Which command adds both packages to `pyproject.toml` and updates the lockfile?
  type: single
  options:
  - id: a
    text: '`uv install langgraph langchain-openai`'
  - id: b
    text: '`uv add langgraph langchain-openai`'
  - id: c
    text: '`pip install langgraph langchain-openai`'
  - id: d
    text: '`uv sync --package langgraph --package langchain-openai`'
  correct:
  - b
  explanation: '`uv add` registers new dependencies in `pyproject.toml` and updates `uv.lock`. `uv install` is not used to add packages, `pip install` bypasses uv''s lockfile management, and `uv sync` only installs from an existing lockfile without modifying project metadata.'
  difficulty: medium
  hint: Which uv subcommand modifies project metadata to declare a new dependency?
- id: q2
  question: In config.py, you must read OPENROUTER_API_KEY and TAVILY_API_KEY from a .env file. Which implementation correctly loads and accesses these variables?
  type: single
  options:
  - id: a
    text: Access `os.environ[`OPENROUTER_API_KEY`]` before calling `load_dotenv()`.
  - id: b
    text: Hardcode both keys as string literals in config.py.
  - id: c
    text: Call `load_dotenv()` at import time, then use `os.getenv(`OPENROUTER_API_KEY`)` and `os.getenv(`TAVILY_API_KEY`)`.
  - id: d
    text: Import the .env file as a Python module and read its attributes.
  correct:
  - c
  explanation: '`load_dotenv()` from python-dotenv injects .env values into the environment, after which `os.getenv()` safely retrieves them. Reading `os.environ` first can raise KeyError, hardcoding secrets is insecure, and .env is not a Python module.'
  difficulty: medium
  hint: What must happen before `os.getenv` can see values defined in .env?
- id: q3
  question: You are defining a single-node StateGraph that will be exposed through ui_api.py. Which code correctly builds and compiles the graph?
  type: single
  options:
  - id: a
    text: '`builder = StateGraph(MyState); builder.add_node(`chat`, chat_node); builder.add_edge(START, `chat`); graph = builder.compile()`'
  - id: b
    text: '`builder = StateGraph(); builder.add_node(chat_node); graph = builder.compile()`'
  - id: c
    text: '`graph = StateGraph(MyState); graph.add_node(`chat`, chat_node); graph.add_edge(`chat`, END)`'
  - id: d
    text: '`builder = StateGraph(MyState); builder.add_node(`chat`, chat_node); builder.add_edge(`chat`, START); graph = builder.compile()`'
  correct:
  - a
  explanation: A StateGraph needs a state schema, a named node, an entry edge from START to that node, and compilation via `compile()`. Option B omits the schema and edge; C misuses the graph object as a builder and skips compile; D reverses the edge direction, which is invalid.
  difficulty: medium
  hint: How does the graph know where execution should begin?
- id: q4
  question: After wiring the graph into ui_api.py, which command starts the local web UI so you can send a message and receive a model reply?
  type: single
  options:
  - id: a
    text: '`uv run main.py`'
  - id: b
    text: '`streamlit run config.py`'
  - id: c
    text: '`python langgraph up`'
  - id: d
    text: '`uv run ui_api.py`'
  correct:
  - d
  explanation: The pre-built UI is served by ui_api.py, so `uv run ui_api.py` starts the local web server. main.py is not the UI entry point, config.py only holds settings, and `langgraph up` targets LangGraph Platform deployment rather than the local UI.
  difficulty: medium
  hint: Which filename contains the UI server code mentioned in the objective?
lastReviewed: *id001
draft: false
pipelineRunId: 030c8433a4
---

## What we add
You will create a `uv` project, add `langgraph` and `langchain-openai` as dependencies, write a `config.py` that reads `OPENROUTER_API_KEY` and `TAVILY_API_KEY` from `.env`, build a single‑node `StateGraph`, wire it to a pre‑built FastAPI UI, and run the server to see a model reply.

## How it works
The core is a `StateGraph` from LangGraph. State is a `TypedDict` with a `messages` channel; the default reducer is last‑write‑wins. A node (`answer_node`) calls an OpenRouter chat model and returns the assistant message. The graph is compiled with `build_graph()` and exposed as `graph`. The UI adapter (`ui_api.py`) invokes `graph.invoke` and returns the last message’s content. The FastAPI app serves an HTML page and a `/api/ask` endpoint that calls the adapter. Configuration lives in `config.py`; `load_settings()` reads environment variables (with `.env` loaded via `python‑dotenv`) and supplies the API key, base URL, and default model to `ChatOpenAI` [S3][S4].

## Step by step

### Commit `b5bb290` – project skeleton, uv dependencies, and config module
This commit adds `pyproject.toml` with the required dependencies and creates `config.py`.  
`pyproject.toml` lists `langgraph>=0.2`, `langchain-openai>=0.2`, `fastapi`, `uvicorn`, and `python‑dotenv` [S1].  
`config.py` defines a `Settings` dataclass and `load_settings()`:

```python
@dataclass
class Settings:
    openrouter_api_key: str
    openrouter_base_url: str
    tavily_api_key: str
    model: str
```

Each setting maps to one environment variable. The loader fills them in:

```python
def load_settings() -> Settings:
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        model=os.getenv("DEFAULT_MODEL", "nvidia/nemotron-3.5-lightning:free"),
    )
```

The function reads each variable from the environment, defaulting to the free model `nvidia/nemotron-3.5-lightning:free` (the verified free alternates are listed in `config.py`). A `.env` file in the project root is loaded automatically, but explicit environment variables take precedence.

### Commit `7d689bf` – single‑node StateGraph and `ui_api` adapter
Here you add `graph.py` and `ui_api.py`.  
`graph.py` defines the state, a helper that builds a `ChatOpenAI` from settings, the `answer_node` function, and the `build_graph` factory:

```python
class State(TypedDict):
    messages: list
```

One node does the whole job for now: build a model client and answer.

```python
def answer_node(state: State) -> State:
    model = _default_model()
    response = model.invoke(state["messages"])
    return {"messages": [response]}
```

Then wire the node into the graph and compile it:

```python
def build_graph():
    g = StateGraph(State)
    g.add_node("answer", answer_node)
    g.set_entry_point("answer")
    g.set_finish_point("answer")
    return g.compile()
```

`ui_api.py` exposes a single `ask(question)` function that runs the graph and returns the assistant’s reply:

```python
def ask(question: str) -> str:
    result = graph.invoke({"messages": [("user", question)]})
    return result["messages"][-1].content
```

The graph is compiled once at import time, so every call reuses the same compiled instance [S2].

### Commit `d9c2d19` – pre‑built FastAPI UI on `localhost:5102`
This commit introduces `ui/server.py`, a FastAPI app that serves a minimal HTML page and a `/api/ask` endpoint. The endpoint parses the JSON body, calls `ui_api.ask`, and returns `{"answer": ...}`. The `main()` function runs uvicorn on `0.0.0.0:5102`. You can start it with:

```sh
uv run deep-research-ui
```

Afterwards, open <http://localhost:5102> in a browser, type a question, and the UI will POST to `/api/ask` and display the model’s answer.

### Commit `68b7747` – architecture, parts index, and README UI section
The docs are updated: `docs/ARCHITECTURE.md` describes the state, graph, configuration, and UI; `docs/PARTS.md` lists the part tags; `README.md` gains a “Run the web UI” section with the `uv run deep-research-ui` command. These documents help you navigate the project as more parts land.

### Commit `dae4072` – fix `ui_api` import in the pre‑built UI server
The import in `ui/server.py` was corrected to `from ..ui_api import ask`. This ensures the FastAPI app can locate the adapter module when the package is installed.

## Wrap‑up
You now have a working `uv` project, a configurable OpenRouter‑backed chat model, a single‑node LangGraph, and a local web UI that returns model replies. The next parts will extend the graph with search nodes and multi‑step reasoning.

## Exercises

**Exercise 1: Add a second node that echoes the user’s question.**  
*Acceptance:*  
- The graph contains two nodes.  
- Invoking the graph returns a state with both the echo and the model reply.  
- `uv run pytest` passes.  
*Hint:* Add a new function `echo_node` that returns `{"messages": [("assistant", state["messages"][-1].content)]}`, then connect it before `answer_node` using `g.add_edge("echo", "answer")`.

**Exercise 2: swap the default model to a verified alternate.  
*Acceptance:  
- `os.environ["DEFAULT_MODEL"]` is unset, `load_settings().model` equals `"nvidia/nemotron-3-ultra-550b-a55b:free"`.  
- `uv run pytest` still passes offline.  
*Hint:* Edit the fallback string inside `load_settings()` in `config.py`; the verified alternates are listed in the module docstring.

**Exercise 3: Write a test that verifies `TAVILY_API_KEY` is read from a `.env` file.**  
*Acceptance:*  
- The test creates a temporary `.env` file, calls `load_settings()`, and asserts `s.tavily_api_key` matches the file’s value.  
- The test runs offline and does not require network access.  
*Hint:* Use `monkeypatch.setenv` to point `BASE_DIR` at a `tmp_path` and write the key there before calling `load_settings()`.

**Exercise 4: Extend the UI to show request latency.**  
*Acceptance:*  
- The `/api/ask` response includes a `latency_ms` field.  
- The HTML page displays the latency alongside the answer.  
- The change does not break existing tests.  
*Hint:* In `ui/server.py`, wrap the call to `ask` with `time.perf_counter()` and add the elapsed time to the returned dictionary.
