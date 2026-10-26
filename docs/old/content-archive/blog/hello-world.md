---
title: "Why this site has a review step"
description: "How articles on this site are drafted with AI from chosen sources, then checked and rewritten by a human before publishing."
pubDate: 2026-10-24
lastReviewed: 2026-10-24
tags: ["meta", "ai"]
category: "opinion"
draft: false
featured: true
sources:
  - title: "Astro documentation: content collections"
    url: "https://docs.astro.build/en/guides/content-collections/"
    publisher: "Astro"
aiAssisted: false
---

This is a sample post so every page has something to render. Replace it with your first real article.

## What a post looks like

Posts are plain Markdown files with validated frontmatter. If a required field is missing, the build fails instead of publishing a broken page.

```ts title="example.ts"
export function greet(name: string) {
  return `hello, ${name}`;
}
```

## Why the review step matters

A draft is only useful if someone checked it. The pipeline drafts; a person decides.

### Sources

Every post lists where its facts came from, so readers can check them too.
