---
title: "A Linux terminal setup that stays out of your way"
description: "A small, boring terminal setup: one shell, one multiplexer, a handful of aliases. Fast to rebuild on a new machine, easy to explain to a friend."
pubDate: 2026-10-20
lastReviewed: 2026-10-24
tags: ["linux", "terminal", "productivity"]
category: "tooling"
draft: false
featured: false
sources:
  - title: "The GNU Bash manual"
    url: "https://www.gnu.org/software/bash/manual/"
    publisher: "GNU"
  - title: "tmux wiki"
    url: "https://github.com/tmux/tmux/wiki"
    publisher: "tmux"
aiAssisted: true
---

A terminal setup is good when you stop noticing it. Mine has three parts.

## One shell, few aliases

Keep aliases you actually type every day. Everything else is noise.

```bash
alias ll='ls -lah'
alias gs='git status -sb'
alias ..='cd ..'
```

## A multiplexer for sessions

tmux keeps your work alive when the connection drops. Learn five keys: new window, next window, split, detach, attach.

## Dotfiles in Git

Put your config in a repository and symlink it. A new machine is then one clone and one script away from familiar.

> The best setup is the one you can rebuild in ten minutes.
