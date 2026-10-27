---
title: "Seed part: schema smoke test"
order: 1
estimatedMinutes: 15
objectives:
  - Exercise the extended module schema
  - Prove placeholders, sources and code panels parse
sources:
  - title: Astro Content Collections
    url: https://docs.astro.build/en/reference/content-collection-reference/
    accessed: 2026-10-26
resources:
  - title: Zod docs
    url: https://zod.dev/
    type: docs
    why: Where the frontmatter schemas come from.
code:
  startTag: part-0
  endTag: part-1
  compareUrl: https://github.com/your-username/seed-course-repo/compare/part-0...part-1
  treeUrl: https://github.com/your-username/seed-course-repo/tree/part-1
  commits:
    - sha: "0000000"
      message: "part-1: seed commit"
      url: https://github.com/your-username/seed-course-repo/commit/0000000000000000000000000000000000000000
  files: [src/seed.py]
quiz:
  - id: q1
    question: "What role does this seed module play?"
    type: single
    options:
      - { id: a, text: "Schema smoke test" }
      - { id: b, text: "A user-facing lesson" }
      - { id: c, text: "A graded exam" }
    correct: [a]
    explanation: "It validates the module frontmatter contract and nothing more."
    difficulty: easy
  - id: q2
    question: "Which two repos does publishing a part touch?"
    type: single
    options:
      - { id: a, text: "Course repo and site repo" }
      - { id: b, text: "Only the site repo" }
      - { id: c, text: "Only the course repo" }
    correct: [a]
    explanation: "The tag is pushed to the course repo first; the lesson is committed to the site repo."
    difficulty: easy
  - id: q3
    question: "When does a part go live?"
    type: single
    options:
      - { id: a, text: "When its agent finishes drafting" }
      - { id: b, text: "Only after a human approves it" }
      - { id: c, text: "Randomly, on a schedule" }
    correct: [b]
    explanation: "Every part is approved by a human before publishing."
    difficulty: easy
lastReviewed: 2026-10-26
draft: true
---

Draft-only seed module. Filtered from production like the rest of the `_seed-course` folder — its job is to render every lesson block once so CI catches schema regressions before the flagship course lands.

## Follow along with the repo

Every part is one slice of the seed project. The **repo workbench** panel below the lesson lists the tags, the `git checkout` command, the commits, and the files this part adds — everything is plain text, straight from frontmatter.

The flow is always the same: `start` tag → your edits → `end` tag. The panel builds its `compare tags on github` link from those two tags, so a broken `compareUrl` fails loudly in review, not in production.

```python
def part_tag(n: int) -> str:
    # every part pins exactly one tag
    return f"part-{n}"
```

*Figure 1: the tag helper. Nothing fancy — it exists so captions and checkouts can be exercised.*

Astro content collections validate this frontmatter at build time [1](#sources-h). Inline source links point down to the sources list at the bottom of every part.

## Exercise: pin a part number

**Goal:** implement `part_tag` so every lesson can check out its own state of the repo.

Acceptance criteria:

- returns `part-N` for any `N >= 0`
- raises `ValueError` for negative inputs

<details>
<summary>Hint 1 — where to start</summary>

f-strings are all you need; the check is a single `if`.
</details>

<details>
<summary>Hint 2 — the rejection test</summary>

Assert on `ValueError` with `pytest.raises`, not `assert ...  is True`.
</details>

