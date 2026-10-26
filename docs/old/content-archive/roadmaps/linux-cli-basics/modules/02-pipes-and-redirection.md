---
title: "Pipes and redirection"
order: 2
estimatedMinutes: 35
objectives:
  - "Send command output to a file with redirection"
  - "Chain small commands together with pipes"
resources: []
lastReviewed: 2026-10-24
draft: false
quiz:
  - id: q1
    question: "What does the | symbol do between two commands?"
    type: single
    options:
      - { id: a, text: "Feeds the output of the first into the second" }
      - { id: b, text: "Runs both commands at the same time on separate files" }
      - { id: c, text: "Comments out the second command" }
    correct: [a]
    explanation: "A pipe connects standard output of one command to standard input of the next."
    difficulty: easy
  - id: q2
    question: "Which operator appends output to a file instead of overwriting it?"
    type: single
    options:
      - { id: a, text: ">" }
      - { id: b, text: ">>" }
      - { id: c, text: "<" }
    correct: [b]
    explanation: "> overwrites, >> appends."
    difficulty: easy
  - id: q3
    question: "Which of these are good reasons to use small chained commands?"
    type: multi
    options:
      - { id: a, text: "Each tool does one job well" }
      - { id: b, text: "You can test each step on its own" }
      - { id: c, text: "It is required by the shell" }
    correct: [a, b]
    explanation: "Composition is the point. Nothing forces you to chain commands."
    difficulty: medium
---

## Redirection

```bash
ls -la > files.txt
echo "done" >> files.txt
```

## Pipes

```bash
cat files.txt | grep ".md" | wc -l
```

Build pipelines one step at a time, checking the output after each `|`.
