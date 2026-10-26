---
title: "Why Astro ships so little JavaScript"
description: "Astro renders pages to HTML and only hydrates the parts you mark as interactive. That one decision explains most of its speed."
pubDate: 2026-10-15
lastReviewed: 2026-10-24
tags: ["astro", "web", "performance"]
category: "opinion"
draft: false
featured: false
sources:
  - title: "Astro islands architecture"
    url: "https://docs.astro.build/en/concepts/islands/"
    publisher: "Astro"
aiAssisted: true
---

Most sites are mostly text. Astro takes that seriously.

## Islands

A page is HTML by default. A component only becomes interactive if you ask, with a directive such as `client:visible`. The rest never sends a byte of JavaScript.

## What that means for you

Faster first paint, less to debug, and a lower chance that a slow phone struggles with your blog. The quiz on this site is one island. Everything around it is static.

## The trade-off

If most of your page is interactive, you gain little. Pick the tool for the page you have, not the one you like.
