---
title: "RAG without the buzzwords: retrieve, then answer"
description: "Retrieval-augmented generation is two steps: find relevant text, then ask the model to answer using only that text. Here is the plain version."
pubDate: 2026-10-18
lastReviewed: 2026-10-24
tags: ["rag", "ai", "python"]
category: "guide"
draft: false
featured: false
sources:
  - title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    url: "https://arxiv.org/abs/2005.11401"
    publisher: "arXiv"
aiAssisted: true
---

RAG sounds complicated because of the vocabulary. The idea is small.

## Step one: retrieve

Split your documents into chunks, turn each chunk into a vector, and store them. At question time, turn the question into a vector and fetch the closest chunks.

## Step two: answer

Put those chunks in the prompt and tell the model to answer only from them. If the answer is not there, it should say so.

```python
def answer(question: str, chunks: list[str]) -> str:
    context = "\n---\n".join(chunks)
    return llm(f"Answer using only this context:\n{context}\n\nQ: {question}")
```

## What usually goes wrong

Chunks that are too big, chunks that are too small, and no check that retrieval found anything useful. Fix those before changing models.
