---
title: "Git habits that save you at 2 a.m."
description: "Five small Git habits, from small commits to using the reflog, that turn a scary broken-repo moment into a two-minute fix."
pubDate: 2026-10-12
lastReviewed: 2026-10-24
tags: ["git", "tooling"]
category: "tutorial"
draft: false
featured: false
sources:
  - title: "Pro Git book"
    url: "https://git-scm.com/book/en/v2"
    publisher: "Git"
aiAssisted: true
---

Git feels dangerous until you know the safety nets.

## Commit small

A commit you can describe in one line is a commit you can revert in one command.

## Look before you leap

```bash
git status -sb
git diff --stat
git log --oneline -5
```

## The reflog remembers

Even after a bad reset, `git reflog` lists where HEAD has been. Find the hash, then `git reset --hard <hash>` and breathe.

## Branch for anything risky

Branches are free. Use one for every experiment.
