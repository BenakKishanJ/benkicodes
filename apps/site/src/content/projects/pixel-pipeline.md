---
title: "Content pipeline"
summary: "A Python and LangGraph pipeline that drafts articles from chosen sources and opens a pull request for review."
status: active
stack: ["Python", "LangGraph", "Gemini", "GitHub Actions"]
repo: "https://github.com/your-username/content-pipeline"
featured: false
order: 2
startDate: 2026-09-15
---

## Problem

Writing source-cited articles by hand is slow, and unchecked AI output is not trustworthy.

## Approach

A graph of nodes: collect sources, draft, critique, revise with a loop cap, then open a pull request. A human reviews every one.

## What I'd change next

A review dashboard and automatic link checking.
