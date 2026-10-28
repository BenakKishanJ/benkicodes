"""Expand `{{code:path#L10-34}}` placeholders from the repo at HEAD (03-prd §7.6).

The model sees line-numbered files and types placeholders instead of pasting
code. Expansion is deterministic: read the file, verify the range exists and is
<= 40 lines, emit a fenced block plus a caption linking to the tag on GitHub.
Anything unresolved is a hard gate failure.
"""
from __future__ import annotations

import re

PLACEHOLDER_RE = re.compile(r"\{\{code:([^#\s}]+)#L(\d+)-L?(\d+)\}\}")
MAX_LINES = 40
MAX_INLINE_BLOCK = 8   # non-placeholder typed code blocks

_LANG = {".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "bash",
         ".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
         ".md": "markdown", ".cfg": "ini", ".txt": "text", ".html": "html", ".css": "css"}


def find_placeholders(md: str) -> list[tuple[str, int, int]]:
    return [(m.group(1), int(m.group(2)), int(m.group(3))) for m in PLACEHOLDER_RE.finditer(md)]


def expand_placeholders(md: str, read_head, blob_base: str) -> tuple[str, list[str]]:
    """Replace every placeholder with a fenced block + caption.

    read_head(path) -> str | None (the file at HEAD); blob_base is the GitHub
    URL prefix, e.g. https://github.com/owner/repo/blob/part-2 — the caption
    links to `{blob_base}/{path}#L{a}-L{b}`. Returns (md, problems).
    """
    out, problems, seen = [], [], set()
    last = 0
    for m in PLACEHOLDER_RE.finditer(md):
        path, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        key = (path, a, b)
        text = None
        if key in seen:
            problems.append(f"duplicate placeholder {key}")
        seen.add(key)
        if b < a:
            problems.append(f"{path}: range end before start (L{a}-L{b})")
        elif b - a + 1 > MAX_LINES:
            problems.append(f"{path}: placeholder spans {b - a + 1} lines (max {MAX_LINES})")
        else:
            content = read_head(path)
            if content is None:
                problems.append(f"{path}: not in the repo at HEAD")
            else:
                lines = content.splitlines()
                if a < 1 or b > len(lines):
                    problems.append(f"{path}: range L{a}-L{b} outside the file ({len(lines)} lines at HEAD)")
                else:
                    text = "\n".join(lines[a - 1:b])
        if text is None:
            continue
        lang = _LANG.get(("." + path.rsplit(".", 1)[-1].lower()) if "." in path else "", "text")
        caption = (f"\n\n<figure class=\"snippet-fig\">\n```{lang}\n{text}\n```\n"
                   f"<figcaption><code>{path}</code>, lines {a}–{b} · "
                   f"<a href=\"{blob_base}/{path}#L{a}-L{b}\">view on GitHub</a></figcaption>\n</figure>\n\n")
        out.append(md[last:m.start()])
        out.append(caption)
        last = m.end()
    out.append(md[last:])
    return "".join(out), problems


def inline_block_problems(md: str) -> list[str]:
    """Typed (non-placeholder) code blocks must be <= 8 lines."""
    problems = []
    blocks = re.findall(r"```([^\n]*)\n(.*?)```", md, re.S)
    for lang, body in blocks:
        if "snippet-fig" in body or body.lstrip().startswith("<figure"):
            continue
        n = len(body.rstrip("\n").splitlines())
        if n > MAX_INLINE_BLOCK:
            problems.append(f"a {lang.strip() or 'code'} block is {n} lines (max {MAX_INLINE_BLOCK}); use a {{code:…}} placeholder")
    return problems
