---
title: 'langgraph-deep-research: build it, part by part'
description: A beginner course that builds a deep research agent with LangGraph, Tavily search, and OpenRouter free models.
level: beginner
estimatedHours: 10.5
prerequisites: []
outcomes:
- Accumulate evidence (url, title, snippet) in graph state using a reducer.
- Add a reflection node that critiques collected evidence.
- Add a tool node and conditional edge to create an ask/tool loop.
- Ask a question and receive an answer with listed web sources.
- Build a single-node StateGraph and connect it to the pre-built UI via ui_api.py.
- Create a planner node that breaks a topic into sub-queries.
- Create a pytest suite with fakes for both the chat model and Tavily, fully offline.
- Create a uv project with langgraph and langchain-openai dependencies.
- Implement follow-up searches bounded by a rounds budget.
- Produce a brief with numbered citations.
- Run the agent via `uv run deep-research-ui` and verify end-to-end.
- Run the local web UI and receive a model reply.
- Stream progress updates to the UI.
- Wrap Tavily search as a langchain @tool.
- Write a synthesis node that produces a structured markdown report with bibliography.
- Write config.py that reads OPENROUTER_API_KEY and TAVILY_API_KEY from .env.
tags: []
status: in-progress
planned:
- slug: plan-and-fan-out
  title: Plan and Fan-Out
  estimatedMinutes: 150
- slug: reflection-and-refinement
  title: Reflection and Refinement
  estimatedMinutes: 120
- slug: report-and-tests
  title: Report and Tests
  estimatedMinutes: 150
project:
  repo: https://github.com/BenakKishanJ/langgraph-deep-research.git
  defaultBranch: main
  template: false
  license: MIT
  stack:
  - python
  - uv
  - pytest
  - ruff
  summary: A beginner course that builds a deep research agent with LangGraph, Tavily search, and OpenRouter free models.
inspiredBy:
- title: GitHub - langchain-ai/deep_research_from_scratch
  url: https://github.com/langchain-ai/deep_research_from_scratch
  note: Canonical reference repository from LangChain showing a complete deep research agent with Tavily, iterative loops, and content summarization - directly aligns with all 5 course parts.
- title: Tavily LangChain Integration Documentation
  url: https://docs.tavily.com/documentation/integrations/langchain
  note: Official Tavily-LangChain integration docs showing TavilySearch tool instantiation with parameters - supports the course's @tool wrapping approach and parameter explanations.
lastReviewed: 2026-11-07
version: "1.0"
draft: false
featured: false
pipelineRunId: 030c8433a4
---

> A beginner course that builds a deep research agent with LangGraph, Tavily search, and OpenRouter free models.

## How this works

Every module is a working step of the same project. Clone the repo, check out the tag of the module you are reading (`git checkout part-N`), and code along — the lesson shows the exact diff that step adds.

## Inspired by

- [GitHub - langchain-ai/deep_research_from_scratch](https://github.com/langchain-ai/deep_research_from_scratch) — Canonical reference repository from LangChain showing a complete deep research agent with Tavily, iterative loops, and content summarization - directly aligns with all 5 course parts.
- [Tavily LangChain Integration Documentation](https://docs.tavily.com/documentation/integrations/langchain) — Official Tavily-LangChain integration docs showing TavilySearch tool instantiation with parameters - supports the course's @tool wrapping approach and parameter explanations.
