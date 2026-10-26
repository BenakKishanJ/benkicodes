---
title: "Your first structured output call with the Gemini API"
description: "Ask the Gemini API for JSON that matches a schema, parse it safely, and handle the case where the model still gets it wrong."
pubDate: 2026-10-09
lastReviewed: 2026-10-24
tags: ["gemini", "ai", "api"]
category: "tutorial"
draft: false
featured: false
sources:
  - title: "Gemini API documentation"
    url: "https://ai.google.dev/gemini-api/docs"
    publisher: "Google"
aiAssisted: true
---

Free-form text is hard to build on. Structured output gives you data your code can trust a little more.

## Define the shape

Describe the fields you want as a schema and pass it with the request.

```python
schema = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "tags"],
}
```

## Parse defensively

Even with a schema, validate the result before using it. A failed parse should retry once, then fail loudly.

## Keep prompts boring

The more creative the prompt, the more creative the failures. State the task, the shape, and one example.
