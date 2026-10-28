"""Renders templates/course-repo/ into a new course repo (03-prd §7.4 init_repo).

Placeholders in template files: __NAME__ (repo name), __PROJECT__ (pretty name),
__SUMMARY__ (from the plan), __PKG__ (python package name), __GITHUB__ (owner/org).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

TXT_SUFFIXES = {".md", ".toml", ".py", ".txt", ".yml", ".yaml", ".cfg", ".ini", ".example", ".rst"}


def package_name(repo_name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", repo_name.strip().lower()).strip("_")
    return name or "course"


def owner_from_remote(remote_url: str | None) -> str:
    if not remote_url:
        return "benkicodes"
    m = re.search(r"github\.com[/:]([^/]+)/", remote_url)
    if m:
        return m.group(1).rstrip("/")
    return "benkicodes"

def render_course_template(template_dir: Path, dest: Path, *, name: str, project: str,
                           summary: str, github_owner: str | None = None) -> tuple[int, str]:
    """Copy the template into `dest` with substitutions. Returns (file_count, package_name)."""
    if not template_dir.exists():
        raise FileNotFoundError(f"course template missing: {template_dir}")
    if dest.exists():
        raise FileExistsError(f"refusing to overwrite existing repo dir: {dest}")
    pkg = package_name(name)
    sub = {
        "__NAME__": name,
        "__PROJECT__": project,
        "__SUMMARY__": summary.replace("\n", " "),
        "__PKG__": pkg,
        "__GITHUB__": github_owner or "benkicodes",
    }
    n = 0
    src_root = Path(template_dir)
    skip = {".venv", "__pycache__", ".git"}
    for src in sorted(src_root.rglob("*")):
        if skip & set(src.parts[len(src_root.parts):]):
            continue
        rel = src.relative_to(src_root)
        rel_parts = [p.replace("__PKG__", pkg) for p in rel.parts]
        out = dest.joinpath(*rel_parts)
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        if src.suffix in TXT_SUFFIXES or src.name == ".gitignore":
            for k, v in sub.items():
                text = text.replace(k, v)
        out.write_text(text, encoding="utf-8")
        n += 1
    return n, pkg
