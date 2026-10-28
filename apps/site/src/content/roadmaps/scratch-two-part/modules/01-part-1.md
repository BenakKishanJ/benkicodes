---
title: 'Part 1: Project Setup and Basic Commands'
order: 1
estimatedMinutes: 90
objectives:
- Initialize a Python project with uv and pytest
- Create an argparse-based CLI with add and list subcommands
- Persist notes to a JSON file using pathlib and json
sources:
- title: argparse — Parser for command-line options, arguments and subcommands
  url: https://docs.python.org/3/library/argparse.html
  accessed: &id001 2026-10-28
- title: pathlib — Object-oriented filesystem paths
  url: https://docs.python.org/3/library/pathlib.html
  accessed: *id001
resources: []
code:
  startTag: part-0
  endTag: part-1
  compareUrl: https://github.com/BenakKishanJ/scratch-two-part/compare/part-0...part-1
  treeUrl: https://github.com/BenakKishanJ/scratch-two-part/tree/part-1
  commits:
  - sha: '8938598'
    message: 'part-1: Add JSON storage layer with load_notes and save_notes'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/8938598f578e0a03fa83fe3104806dec5d29c9f2
  - sha: c648a09
    message: 'part-1: Add argparse CLI with add and list subcommands wired to storage'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/c648a094263611e901ed095966445fcfba7ad556
  - sha: ff8217c
    message: 'part-1: update docs (architecture, parts index)'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/ff8217c96fe54ad19ec49bb0ae8eb105a22e54ca
  - sha: 1bba99b
    message: 'part-1: manual adjustments'
    url: https://github.com/BenakKishanJ/scratch-two-part/commit/1bba99b4a07f9027894e3beccb821c22785e02c9
  files:
  - pyproject.toml
  - src/scratch_two_part/cli.py
  - src/scratch_two_part/storage.py
  - tests/test_cli.py
  - tests/test_storage.py
quiz:
- id: q1
  question: You want to create a new project directory `notes_cli` and add `pytest` as a development dependency using `uv`. Which command sequence is correct?
  type: single
  options:
  - id: a
    text: '`uv init --dev pytest notes_cli`'
  - id: b
    text: '`uv init notes_cli`, then `cd notes_cli`, then `uv add --dev pytest`'
  - id: c
    text: '`uv new notes_cli --add-dev pytest`'
  - id: d
    text: '`uv add --dev pytest notes_cli`'
  correct:
  - b
  explanation: uv init creates the project folder and pyproject.toml. Dependency commands like uv add must run inside that project directory, and --dev records pytest as a development dependency rather than a runtime dependency.
  difficulty: medium
  hint: uv init creates the directory; uv add manages dependencies in the current project.
- id: q2
  question: Which argparse pattern correctly creates `add` and `list` subcommands so the CLI can distinguish which one was invoked?
  type: single
  options:
  - id: a
    text: '`parser.add_argument(''add''); parser.add_argument(''list'')`'
  - id: b
    text: '`subparsers = parser.add_subparsers()` without setting `dest`, then adding `add` and `list` parsers'
  - id: c
    text: '`subparsers = parser.add_subparsers(dest=''command'')`, then `subparsers.add_parser(''add'')` and `subparsers.add_parser(''list'')`'
  - id: d
    text: '`group = parser.add_mutually_exclusive_group(); group.add_argument(''--add''); group.add_argument(''--list'')`'
  correct:
  - c
  explanation: add_subparsers(dest='command') stores the chosen subcommand name in args.command. Each subparser can define its own arguments (e.g., the note text for add). Plain positional arguments or mutually exclusive flags do not create true subcommands.
  difficulty: medium
  hint: The dest argument on add_subparsers is what tells you which subcommand the user ran.
- id: q3
  question: Which snippet correctly writes a Python list to `notes.json` and reads it back using pathlib and json?
  type: single
  options:
  - id: a
    text: '`json.dump(notes, Path(''notes.json''))`'
  - id: b
    text: '`Path(''notes.json'').write_text(json.dump(notes))`'
  - id: c
    text: '`Path(''notes.json'').write_json(notes)` and `Path(''notes.json'').read_json()`'
  - id: d
    text: '`Path(''notes.json'').write_text(json.dumps(notes))` and `json.loads(Path(''notes.json'').read_text())`'
  correct:
  - d
  explanation: Path objects are not file handles, so json.dump/json.load cannot accept them directly. Path has no write_json/read_json methods. write_text/write_text accept strings, so pair them with json.dumps/json.loads.
  difficulty: medium
  hint: Use read_text/write_text for the file I/O and dumps/loads for the JSON conversion.
- id: q4
  question: After initializing the project with uv, where should tests be placed and how are they executed?
  type: single
  options:
  - id: a
    text: '`tests/test_notes.py`, run with `uv run pytest`'
  - id: b
    text: '`__tests__/notes_test.py`, run with `uv test`'
  - id: c
    text: '`test_notes.py` in the project root, run with `pytest --uv`'
  - id: d
    text: '`src/notes_cli/tests/`, run with `uv run test`'
  correct:
  - a
  explanation: pytest discovers files matching test_*.py, conventionally in a tests directory. uv run pytest executes pytest inside the project's uv environment. uv test and pytest --uv are not valid commands/flags.
  difficulty: medium
  hint: uv run executes a command in the project environment; pytest looks for standard test file names.
lastReviewed: *id001
draft: false
pipelineRunId: 9eccb038d0
---

## What we add

In this part you will set up a uv + pytest project, write a thin argparse CLI with `add` and `list` subcommands, and persist notes to a JSON file using `pathlib`. By the end you can run `notes add "buy milk"` and `notes list`, and the data survives between invocations. You will also learn how to test the storage layer and the CLI without leaving the terminal. The argparse module provides subparsers for building multi‑command CLIs [S1], and `pathlib.Path` offers convenient methods for file system operations [S2].

## How it works

The project uses `uv` to manage the environment and `pytest` for tests. The CLI is built with `argparse`; subparsers let each command have its own arguments. We mark the subparser group as `required=True` so that calling `notes` without a command fails with a helpful message [S1]. All file I/O goes through `pathlib.Path`, which lets us create parent directories with `mkdir(parents=True, exist_ok=True)` and read/write with explicit `encoding="utf-8"` [S2]. The storage layer wraps `json.dumps` and `json.loads`, returning an empty list when the file is missing or contains invalid JSON. Keeping the CLI thin means `main` only parses arguments, calls storage functions, and prints results. This separation makes it easy to swap the storage backend or add new commands later. I'd skip a database for now — the notes list is small and a JSON file keeps the project dependency‑free. A common mistake is forgetting `required=True` on the subparsers, which leaves `args.command` as `None` and produces an obscure error. Another pitfall is hardcoding a path in tests instead of using `tmp_path`, which pollutes the repository.

## Step by step

### 8938598 — JSON storage layer

The first commit adds `src/scratch_two_part/storage.py`. It defines `DEFAULT_NOTES_FILE = Path("notes.json")`, `load_notes(path)`, and `save_notes(notes, path)`. `load_notes` checks `path.exists()`; if the file is missing it returns `[]`. It then tries `json.loads(path.read_text(encoding="utf-8"))`. On `json.JSONDecodeError` it returns `[]`. If the parsed value is not a list, it also returns `[]`. `save_notes` calls `path.parent.mkdir(parents=True, exist_ok=True)` and writes `json.dumps(notes, indent=2, ensure_ascii=False) + "\n"` with `encoding="utf-8"`. This implements the persistence layer, achieving the objective of storing notes in a JSON file. You can test this module by running `uv run pytest tests/test_storage.py`. The `pathlib` documentation details these methods [S2].

### c648a09 — argparse CLI

Next we wire the storage to a command line interface. `src/scratch_two_part/cli.py` builds a parser with two subcommands: `add` (positional `content`, optional `--file`) and `list` (optional `--file`). The subparser group uses `required=True` so `args.command` is never `None`. The `main` function parses `argv`, calls `load_notes`, mutates the list, and calls `save_notes`. The parser setup is at:



<figure class="snippet-fig">
```python
def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with ``add`` and ``list`` subcommands."""
    parser = argparse.ArgumentParser(
        prog="notes",
        description="A command-line notes app built with argparse and JSON storage.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new note.")
    add_parser.add_argument("content", help="The note text to store.")
    add_parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_NOTES_FILE,
        help="JSON storage file (default: notes.json).",
    )

    list_parser = subparsers.add_parser("list", help="List all stored notes.")
```
<figcaption><code>src/scratch_two_part/cli.py</code>, lines 13–30 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-1/src/scratch_two_part/cli.py#L13-L30">view on GitHub</a></figcaption>
</figure>



and the main function is at:



<figure class="snippet-fig">
```python
    list_parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_NOTES_FILE,
        help="JSON storage file (default: notes.json).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse *argv* and run the requested command. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "add":
        notes = load_notes(args.file)
        notes.append({"content": args.content})
        save_notes(notes, args.file)
        print(f"Added: {args.content}")
        return 0

    if args.command == "list":
        notes = load_notes(args.file)
        if not notes:
            print("No notes found.")
            return 0
        for index, note in enumerate(notes, start=1):
            print(f"{index}. {note['content']}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1
```
<figcaption><code>src/scratch_two_part/cli.py</code>, lines 31–63 · <a href="https://github.com/BenakKishanJ/scratch-two-part/blob/part-1/src/scratch_two_part/cli.py#L31-L63">view on GitHub</a></figcaption>
</figure>



This creates a thin CLI that only parses arguments and calls storage, fulfilling the objective of a simple command‑line interface. To try it out, run `uv run notes add "hello"` and then `uv run notes list`. The argparse docs explain subparser configuration [S1].

### ff8217c — docs update

This commit adds an architecture diagram and a parts index to the documentation. It does not change runtime behavior, but it records how the CLI, storage, and tests fit together. The docs live in the `docs/` directory and are written in Markdown.

### 1bba99b — manual adjustments

A final tidy‑up commit fixes a stray import, adjusts the `__all__` list, and ensures the `notes` entry point points to `cli:main`. After this the project is ready for the next part. You can verify the entry point by running `uv run notes --help`.

## Wrap-up

You now have a working notes app that can add and list items, with all data stored in a JSON file. The code is thin: argparse parses, storage handles persistence, and the CLI just prints. In the next part we will extend the CLI with edit and delete, add validation, and write more tests. Run `uv run pytest` to see the existing tests pass. The argparse and pathlib docs provide further reading [S1][S2].

## Exercises

**Exercise 1: Add a `delete` subcommand**
- Implement a `delete` subcommand that removes a note by its 1‑based index.
- Acceptance:
  - `notes delete 1 --file test.json` removes the first note.
  - Running `notes list` afterwards shows the remaining notes.
  - Deleting an out‑of‑range index prints an error and returns a non‑zero exit code.
- Hint: reuse `load_notes` / `save_notes` and check `index` against `len(notes)`.

**Exercise 2: Support a `--output` format**
- Add a `--output` flag to `list` that can be `text` (default) or `json`.
- Acceptance:
  - `notes list --output json` prints a JSON array of note objects.
  - `notes list --output text` prints the numbered list as before.
  - Invalid values cause argparse to error.
- Hint: add the argument to the `list` subparser and branch on its value in `main`.

**Exercise 3: Write edge‑case tests**
- Create tests for:
  - Adding a note with special characters (e.g., unicode, quotes).
  - Loading a file that contains a JSON object instead of a list.
  - Saving to a path whose parent directory does not exist.
- Acceptance:
  - Each test passes and uses `tmp_path` for isolation.
  - The test for non‑list JSON asserts `load_notes` returns `[]`.
- Hint: use `json.dumps` to craft the invalid file content and `pathlib.Path.write_text` to create it.
