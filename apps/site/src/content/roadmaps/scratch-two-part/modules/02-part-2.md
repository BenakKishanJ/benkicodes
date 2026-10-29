---
title: 'Part 2: Advanced Commands and Testing'
order: 2
estimatedMinutes: 120
objectives:
- Implement delete and edit commands with validation
- Add search functionality to filter notes
- Handle errors gracefully and improve CLI feedback
- Write comprehensive pytest suite covering all commands
sources:
- title: argparse — Parser for command-line options, arguments and subcommands
  url: https://docs.python.org/3/library/argparse.html
  accessed: &id001 2026-10-29
- title: pathlib — Object-oriented filesystem paths
  url: https://docs.python.org/3/library/pathlib.html
  accessed: *id001
resources: []
code:
  startTag: part-1
  endTag: part-2
  compareUrl: https://github.com/BenakKishanJ/scratch-two-part/compare/part-1...part-2
  treeUrl: https://github.com/BenakKishanJ/scratch-two-part/tree/part-2
  commits:
  - sha: "4e75658"
    message: 'part-2: Implement delete and edit commands with storage validation and tests'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/4e75658a81b1532d9e0a28538bf310dbca5cf766
  - sha: 67205ad
    message: 'part-2: Implement search command with keyword filtering and tests'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/67205adb0cd30f0ec7e60a011199fe320f9df2c8
  - sha: 85c27b1
    message: 'part-2: Record part-2 in the parts index'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/85c27b1cc086f6d3904c77d1d4f057179592921f
  - sha: 897ca2f
    message: 'part-2: update docs (architecture, parts index)'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/897ca2fb7873a7a4ecdd3baa764f8b47edc19510
  files:
  - docs/PARTS.md
  - src/scratch_two_part/cli.py
  - src/scratch_two_part/storage.py
  - tests/test_cli.py
  - tests/test_search.py
quiz:
- id: q1
  question: You are extending a notes CLI with `delete` and `edit` subcommands using argparse. Which approach is the most idiomatic and maintainable?
  type: single
  options:
  - id: a
    text: Use `add_subparsers()` to create a parser for each subcommand and define required arguments (such as note ID and new content) on those subparsers.
  - id: b
    text: Use a single `--command` flag and manually inspect `sys.argv` to decide behavior.
  - id: c
    text: Create a separate `ArgumentParser` instance for every subcommand and merge results manually.
  - id: d
    text: Read the subcommand name from an environment variable at runtime.
  correct:
  - a
  explanation: '`add_subparsers()` is argparse''s built-in mechanism for subcommands. It lets each subcommand define its own arguments, help text, and required fields while still sharing global options, making validation and parsing straightforward.'
  difficulty: medium
  hint: Think about how argparse groups related arguments under a single command name.
- id: q2
  question: When implementing a `search` subcommand that filters notes by keyword, which matching strategy is most user-friendly?
  type: single
  options:
  - id: a
    text: Return only exact, case-sensitive matches to avoid irrelevant results.
  - id: b
    text: Require users to pass `--case-sensitive` on every search invocation.
  - id: c
    text: Normalize both the search query and note text to lowercase, then perform a substring match.
  - id: d
    text: Search only note titles and ignore note bodies to improve performance.
  correct:
  - c
  explanation: Case-insensitive substring matching finds relevant notes regardless of capitalization and does not burden the user with extra flags. Searching only titles would miss matches in note content.
  difficulty: medium
  hint: Consider how users typically expect search to behave in everyday applications.
- id: q3
  question: A user runs `notes delete 42`, but note 42 does not exist. Which response best follows graceful CLI error handling?
  type: single
  options:
  - id: a
    text: Let Python raise an unhandled exception and display the full traceback to the user.
  - id: b
    text: Print a success message because the note is effectively absent after the command runs.
  - id: c
    text: Automatically restart the program so the user can try again.
  - id: d
    text: Catch the specific exception, print a clear message to stderr, and exit with a non-zero status code.
  correct:
  - d
  explanation: Catching the specific exception (for example, `KeyError` or a custom validation error) lets you give the user a readable message. Writing to stderr and exiting non-zero signals failure to both humans and calling scripts without exposing internal stack traces.
  difficulty: medium
  hint: What should a CLI do when an operation cannot complete, and how do scripts detect that failure?
- id: q4
  question: Which pytest practice best ensures that tests for mutating commands like `delete` and `edit` do not interfere with each other?
  type: single
  options:
  - id: a
    text: Use one shared global notes list that all test functions read and write.
  - id: b
    text: Use the `tmp_path` fixture to provide each test with an isolated temporary file or directory.
  - id: c
    text: Name tests `test_01_delete`, `test_02_edit`, and so on to enforce execution order.
  - id: d
    text: Skip error-case tests and only verify successful operations to keep the suite fast.
  correct:
  - b
  explanation: '`tmp_path` creates a unique temporary directory for each test function, so `delete` and `edit` operations in one test cannot corrupt state used by another test. This keeps tests independent and repeatable.'
  difficulty: medium
  hint: Fixtures are the standard pytest tool for setup and teardown of isolated test resources.
lastReviewed: *id001
draft: false
pipelineRunId: 9eccb038d0
---

## What we add

You'll extend the notes app with three new commands — delete, edit, and search — plus the tests that prove they work. By the end of this part you can remove a note by its 1-based number, rewrite an existing note, filter notes case-insensitively by keyword, and see clean error messages on stderr when something goes wrong. Every command is backed by a pytest test, and the whole suite runs green. [S1]

## How it works

The storage layer (`src/scratch_two_part/storage.py`) gains three pure functions — `delete_note`, `edit_note`, and `search_notes` — that operate on the in-memory list of note dicts and return a new list. None of them mutate the input; they build fresh lists, which keeps the boundary between load and save clean. The CLI (`src/scratch_two_part/cli.py`) wires each function to an argparse subcommand [S1] and handles `IndexError` by printing to stderr and returning exit code 1. Argparse exits with code 2 on argument-parsing errors, so a non-integer index like `delete abc` will produce exit code 2, not 1.

Three conventions matter here and they're easy to get wrong:

- **1-based indexes.** Humans count from 1, so `delete 1` means the first note. Internally the list is 0-based, so the functions subtract one before indexing. The storage functions validate the range themselves and raise `IndexError` when the number is below 1 or above the list length.
- **Case-insensitive search.** `search_notes` lowercases both the keyword and each note's content before comparing, so "buy" matches "Buy Bread".
- **capsys is cumulative.** `capsys.readouterr()` returns everything captured since the last read and clears the buffer, so call it between commands to isolate output. For example, if you run `add` then `search` in one test and only read output at the end, the "Added:" line leaks into your assertion.

## Step by step

### Commit 4e75658 — delete and edit with validation and tests

This commit adds the delete and edit commands end to end. In storage, `delete_note` filters out the note at the 1-based position and `edit_note` rebuilds the list with the target replaced:



<figure class="snippet-fig">
```python
def delete_note(
    notes: list[dict[str, Any]], index: int
) -> list[dict[str, Any]]:
    """Return *notes* with the note at 1-based *index* removed.

    Raises ``IndexError`` when *index* is out of range.
    """
    if index < 1 or index > len(notes):
        raise IndexError(f"Note {index} does not exist.")
    return [note for position, note in enumerate(notes) if position != index - 1]


def edit_note(
    notes: list[dict[str, Any]], index: int, new_content: str
) -> list[dict[str, Any]]:
    """Return *notes* with the note at 1-based *index* replaced by *new_content*.

    Raises ``IndexError`` when *index* is out of range.
    """
    if index < 1 or index > len(notes):
        raise IndexError(f"Note {index} does not exist.")
    updated = [dict(note) for note in notes]
    updated[index - 1] = {"content": new_content}
    return updated
```
<figcaption><code>src/scratch_two_part/storage.py</code>, lines 42–65 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-2/src/scratch_two_part/storage.py#L42-L65">view on GitHub</a></figcaption>
</figure>



The range check happens before any list work, so a bad index raises immediately instead of returning a confusing empty list. In the CLI, both commands wrap the storage call in a try/except that catches `IndexError`, prints the message to `sys.stderr`, and returns 1 — the standard signal to the shell that something went wrong:



<figure class="snippet-fig">
```python
    if args.command == "delete":
        try:
            notes = delete_note(load_notes(args.file), args.index)
        except IndexError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        save_notes(notes, args.file)
        print(f"Deleted note {args.index}.")
        return 0

    if args.command == "edit":
        try:
            notes = edit_note(load_notes(args.file), args.index, args.content)
        except IndexError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        save_notes(notes, args.file)
        print(f"Edited note {args.index}: {args.content}")
        return 0
```
<figcaption><code>src/scratch_two_part/cli.py</code>, lines 98–116 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-2/src/scratch_two_part/cli.py#L98-L116">view on GitHub</a></figcaption>
</figure>



A successful delete or edit calls `save_notes` to persist, then prints a confirmation to stdout. Skipping that `save_notes` call is the most common bug here: the in-memory list changes but the file stays stale, and the next `list` shows the old data.

The tests in `tests/test_cli.py` cover the happy path and the error path for each command. Notice how `test_delete_removes_note` calls `capsys.readouterr()` after the two `add` calls before it asserts on the delete output — that's the cumulative-output trap in action. The invalid-index tests assert the error message lands in `captured.err` and that `main` returns 1. There's also a parser test confirming `delete` takes an int index and `edit` takes an int index plus content.

### Commit 67205ad — search with keyword filtering and tests

Search adds a fourth subcommand and its own test file. The `search_notes` function lowercases the keyword and the content, then filters with a comprehension:



<figure class="snippet-fig">
```python
def search_notes(
    notes: list[dict[str, Any]], keyword: str
) -> list[dict[str, Any]]:
    """Return notes whose content contains *keyword*, case-insensitively."""
    match = keyword.lower()
    return [
        note for note in notes if match in note.get("content", "").lower()
    ]
```
<figcaption><code>src/scratch_two_part/storage.py</code>, lines 68–75 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-2/src/scratch_two_part/storage.py#L68-L75">view on GitHub</a></figcaption>
</figure>



Using `.get("content", "")` means a malformed note dict can't crash the search — it just won't match. The CLI prints "No notes matching '<keyword>'." when the filtered list is empty and returns 0, because an empty result is a normal outcome, not an error:



<figure class="snippet-fig">
```python
    if args.command == "search":
        notes = search_notes(load_notes(args.file), args.keyword)
        if not notes:
            print(f"No notes matching '{args.keyword}'.")
            return 0
        for index, note in enumerate(notes, start=1):
            print(f"{index}. {note['content']}")
        return 0
```
<figcaption><code>src/scratch_two_part/cli.py</code>, lines 118–125 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-2/src/scratch_two_part/cli.py#L118-L125">view on GitHub</a></figcaption>
</figure>



`tests/test_search.py` has three tests: matching notes are found, matching is case-insensitive, and no matches produces the friendly message. Each test clears captured output with `capsys.readouterr()` after setup and before the search call, so the assertions only see the search output.

### Commit 85c27b1 — record part-2 in the parts index

A one-line table update in `docs/PARTS.md` adding the `part-2` row. Keep this kind of index current — it's how the course stays navigable.

### Commit 897ca2f — update docs (architecture, parts index)

Documentation refresh across the architecture notes and the parts index. Nothing in code changes here; the lesson text and cross-references get aligned with what the code actually does now.

[S1]

## Wrap-up

You now have a notes app with add, list, delete, edit, and search, each with tests covering the happy path, the error path, and the parser shape. The patterns you've used — 1-based user-facing indexes with 0-based internals, stderr for errors with a non-zero exit code, and clearing capsys before each assertion — will keep your CLI tests brittle-free as the app grows. Run the suite with `uv run pytest -q` to confirm everything is green before moving on. [S1]

## Exercises

**Exercise 1: delete the note at index 2 and verify the file on disk.**

Run the app with three notes, delete the second one, then confirm the file on disk only contains the remaining two notes.

```bash
# create a file with three notes
uv run python -m scratch_two_part add "First note" --file /tmp/notes.json
uv run python -m scratch_two_part add "Second note" --file /tmp/notes.json
uv run python -m scratch_two_part add "Third note" --file /tmp/notes.json
```

Then delete note 2 and check the CLI response:

```bash
uv run python -m scratch_two_part delete 2 --file /tmp/notes.json
# expected stdout: "Deleted note 2."
```

Finally verify what actually landed on disk (only two notes remain, and "Second note" is gone):

```bash
uv run python -m scratch_two_part list --file /tmp/notes.json
# expected stdout:
# 1. First note
# 2. Third note
```

- acceptance: `delete 2` exits 0 and prints "Deleted note 2."; the subsequent `list` shows exactly two notes and the deleted content is absent
- hint: after the delete, the file on disk is the source of truth — `list` reads from it, so if you see the old note you forgot the `save_notes` call

**Exercise 2: edit note 1 to change its text.**

Change the first note's content and confirm both the CLI output and the persisted file reflect the new text.

```bash
# start with one note
uv run python -m scratch_two_part add "Old text" --file /tmp/notes.json
```

Then edit note 1 and confirm both the CLI output and the file:

```bash
uv run python -m scratch_two_part edit 1 "New text" --file /tmp/notes.json
# expected stdout: "Edited note 1."

uv run python -m scratch_two_part list --file /tmp/notes.json
# expected stdout: "1. New text"
```

- acceptance: `edit 1 "New text"` exits 0 and prints "Edited note 1."; `list` shows the updated text and the old text is nowhere in the file
- hint: `edit` takes the index as the first argument and the replacement content as the second — argparse splits these for you, so the test just checks the outcome

**3. Search for a term that matches nothing.**

Run a search for a keyword that doesn't appear in any note and confirm the friendly message and exit code 0.

```bash
# file already has notes from earlier steps
uv run python -m scratch_two_part search "nonexistent" --file /tmp/notes.json
# expected stdout: "No notes matching 'nonexistent'."
# expected exit code: 0
```

- acceptance: exit code 0; stdout is exactly "No notes matching 'nonexistent'." with no extra lines
- hint: an empty search result is not an error — the CLI returns 0 and prints the message, unlike a bad index which returns 1 to stderr

**4. Delete the last note and confirm the list is empty.**

Delete the final remaining note and verify that `list` shows nothing and `count` (or a direct file read) confirms zero stored notes.

```bash
# after the previous steps only one note remains
uv run python -m scratch_two_part delete 1 --file /tmp/notes.json
# expected stdout: "Deleted note 1."

uv run python -m scratch_two_part list --file /tmp/notes.json
# expected stdout: (nothing — no output)
```

- acceptance: `delete 1` exits 0; `list` produces no stdout lines; the file on disk contains an empty list `[]`
- hint: deleting the last note is the boundary case — make sure your storage function handles an index equal to the list length and doesn't leave a stale single-element list behind
