---
title: "Files and navigation"
order: 1
estimatedMinutes: 30
objectives:
  - "Use pwd, ls and cd to move around"
  - "Create and remove files and folders safely"
resources:
  - title: "GNU Coreutils manual"
    url: "https://www.gnu.org/software/coreutils/manual/"
    type: docs
lastReviewed: 2026-10-24
draft: false
quiz:
  - id: q1
    question: "Which command prints the directory you are currently in?"
    type: single
    options:
      - { id: a, text: "pwd" }
      - { id: b, text: "ls" }
      - { id: c, text: "cd" }
    correct: [a]
    explanation: "pwd stands for print working directory."
    difficulty: easy
  - id: q2
    question: "Which of these commands list the contents of a directory?"
    type: multi
    options:
      - { id: a, text: "ls" }
      - { id: b, text: "ls -la" }
      - { id: c, text: "cd" }
      - { id: d, text: "pwd" }
    correct: [a, b]
    explanation: "ls lists directory contents, and flags like -la add detail."
    difficulty: easy
  - id: q3
    question: "What does cd .. do?"
    type: single
    options:
      - { id: a, text: "Moves up to the parent directory" }
      - { id: b, text: "Deletes the current folder" }
      - { id: c, text: "Lists hidden files" }
    correct: [a]
    explanation: "Two dots always mean the parent directory."
    difficulty: easy
---

## Where am I?

```bash
pwd
ls -la
cd ~/projects
```

## Make and remove things

```bash
mkdir notes
touch notes/todo.txt
rm notes/todo.txt
```

`rm` does not ask twice. Check the path before you press Enter.
