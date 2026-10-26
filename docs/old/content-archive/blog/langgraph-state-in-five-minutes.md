---
title: "LangGraph state in five minutes"
description: "What the state object in LangGraph really is, how nodes update it, and the one mistake that makes agents forget everything between steps."
pubDate: 2026-10-22
lastReviewed: 2026-10-24
tags: ["langgraph", "python", "ai"]
category: "guide"
draft: false
featured: false
sources:
  - title: "LangGraph documentation"
    url: "https://langchain-ai.github.io/langgraph/"
    publisher: "LangChain"
aiAssisted: true
---

State is the single object every node reads from and writes to. If you remember one thing, remember that nodes return *updates*, not a whole new state.

## The smallest graph

```python
from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    topic: str
    draft: str

def write(state: State) -> dict:
    return {"draft": f"Notes about {state["topic"]}"}

graph = StateGraph(State)
graph.add_node("write", write)
graph.set_entry_point("write")
graph.add_edge("write", END)
app = graph.compile()
```

## The mistake everyone makes

Returning the full state from a node works, but it hides bugs. Return only the keys you changed and let the graph merge them.

## Where to go next

Conditional edges let a node decide where the run goes next. That is the next module in the roadmap.
