---
title: "State and nodes"
order: 1
estimatedMinutes: 40
objectives:
  - "Describe what a LangGraph state object holds"
  - "Write a node as a plain function"
resources:
  - title: "LangGraph documentation"
    url: "https://langchain-ai.github.io/langgraph/"
    type: docs
lastReviewed: 2026-10-24
draft: false
quiz:
  - id: q1
    question: "In LangGraph, what does a node receive and return?"
    type: single
    options:
      - { id: a, text: "The current state, and an update to the state" }
      - { id: b, text: "A prompt string, and a model response string" }
      - { id: c, text: "An HTTP request, and an HTTP response" }
    correct: [a]
    explanation: "Nodes are functions that read the shared state and return the part of the state they want to change."
    difficulty: easy
  - id: q2
    question: "Which of these can be a node?"
    type: multi
    options:
      - { id: a, text: "A function that calls an LLM" }
      - { id: b, text: "A function that calls a search API" }
      - { id: c, text: "A function that edits a database row" }
      - { id: d, text: "Only functions decorated with @agent" }
    correct: [a, b, c]
    explanation: "A node is any callable that takes state and returns an update. There is no special decorator."
    difficulty: medium
  - id: q3
    question: "Why keep state in one shared object instead of passing arguments between nodes?"
    type: single
    options:
      - { id: a, text: "It makes the run resumable and inspectable at any step" }
      - { id: b, text: "It makes nodes run faster" }
      - { id: c, text: "It is required by Python" }
    correct: [a]
    explanation: "A single state object can be saved by a checkpointer, which is what enables pausing, resuming and replaying runs."
    difficulty: medium
---

## What is state?

State is the single object every node reads from and writes to. Think of it as the whiteboard in a meeting room.

## Writing a node

A node is just a function.

```python
def draft_node(state: dict) -> dict:
    return {"draft": f"Draft about {state['topic']}"}
```

## Recap

Nodes read state, return updates, and LangGraph merges them.
