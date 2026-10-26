---
title: "Edges and routing"
order: 2
estimatedMinutes: 45
objectives:
  - "Connect nodes with normal and conditional edges"
  - "Route a run based on the current state"
resources: []
lastReviewed: 2026-10-24
draft: false
quiz:
  - id: q1
    question: "What does a conditional edge do?"
    type: single
    options:
      - { id: a, text: "Chooses the next node based on the state" }
      - { id: b, text: "Runs two nodes at the same time" }
      - { id: c, text: "Retries a failed node automatically" }
    correct: [a]
    explanation: "A conditional edge calls a routing function with the state and follows whichever path it returns."
  - id: q2
    question: "A critic node scores a draft below the threshold. What should the router usually do?"
    type: single
    options:
      - { id: a, text: "Send the draft back to the writer, up to a retry limit" }
      - { id: b, text: "Publish anyway" }
      - { id: c, text: "Delete the state" }
    correct: [a]
    explanation: "Loops need a cap, otherwise a stubborn critic and a stubborn writer can run forever."
  - id: q3
    question: "Why cap the number of revision loops?"
    type: single
    options:
      - { id: a, text: "To control cost and avoid infinite loops" }
      - { id: b, text: "Because LangGraph forbids cycles" }
      - { id: c, text: "To make the graph look smaller" }
    correct: [a]
    explanation: "LangGraph allows cycles, so you must bound them yourself."
---

## Normal edges

A normal edge always goes from one node to the next.

## Conditional edges

A routing function reads the state and returns the name of the next node.

```python
def route(state: dict) -> str:
    return "publish" if state["score"] >= 4 else "revise"
```
