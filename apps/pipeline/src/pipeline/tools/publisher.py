"""Turns an approved draft into a post file and pushes it to the site repo's main
through a detached worktree (03-prd §11.2). The author's working tree is never touched.

PUBLISH_MODE=git   -> fetch, worktree reset to origin/main, write, commit, push (rebase-retry)
PUBLISH_MODE=files -> dry run: write into the worktree and return the diff, no commit
"""
from __future__ import annotations

import difflib
import re
import subprocess
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from ..config import Settings
from ..schemas import SLUG_RE, Frontmatter, SourceRef
from .gates import CITE_RE


class PublishError(Exception):
    pass


def trust_of(url: str | None) -> str:
    """Cheap heuristic trust rating (no model call): primary-source domains rate high."""
    u = (url or "").lower()
    d = u.split("/")[2] if "://" in u and len(u.split("/")) > 2 else ""
    if not d:
        return "medium"
    if d.startswith(("docs.", "developers.", "learn.", "") ) or "official" in d or d in (
            "github.com", "developer.mozilla.org"):
        return "high"
    if d.count(".") > 2 or "blog" in d or "medium.com" in d or "substack.com" in d:
        return "low"
    return "medium"


def renumber_citations(body: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """[S3] -> a numbered link to the Sources section; sources are numbered by first citation."""
    by_id = {s["id"]: s for s in sources}
    order: list[str] = []

    def num(sid: str) -> int:
        if sid not in order:
            order.append(sid)
        return order.index(sid) + 1

    def repl(m: re.Match) -> str:
        ids = [x for x in re.split(r"\s*,\s*", m.group(1)) if x in by_id]
        return "".join(f"[\\[{num(i)}\\]](#sources-h)" for i in ids)

    out = CITE_RE.sub(repl, body)
    return out, [by_id[i] for i in order]


def build_frontmatter(seo: dict, cited: list[dict], run_id: str, today: date | None = None) -> tuple[Frontmatter | None, str | None]:
    today = today or date.today()
    try:
        fm = Frontmatter(
            title=seo["title"], description=seo["description"], pubDate=today, lastReviewed=today,
            tags=seo["tags"], category=seo["category"],
            sources=[SourceRef(title=s["title"], url=s["url"], accessed=today) for s in cited if s.get("url")] or [],
            pipelineRunId=run_id,
        )
        return fm, None
    except (ValidationError, KeyError) as e:
        if isinstance(e, ValidationError):
            msg = "; ".join(f'{".".join(map(str, x["loc"]))}: {x["msg"]}' for x in e.errors()[:4])
        else:
            msg = f"missing {e}"
        return None, msg


def render_post(fm: Frontmatter, body: str) -> str:
    data = fm.model_dump(mode="python", exclude_none=True)
    head = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    return f"---\n{head}---\n\n{body.strip()}\n"


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise PublishError(f"git {' '.join(args[:3])} failed: {(r.stderr or r.stdout).strip()[:500]}")
    return r.stdout.strip()


def _prepare_worktree(repo: Path, wt: Path, branch: str, remote: str) -> None:
    """Detach `wt` at origin/<branch>, creating or resetting it as needed."""
    _git(repo, "fetch", remote, branch)
    if wt.exists():
        out = _git(repo, "worktree", "list", "--porcelain")
        listed = {ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("worktree ")}
        if wt.resolve().as_posix() not in listed:
            raise PublishError(f"{wt} exists but is not a registered git worktree; move or delete it")
        _git(wt, "reset", "--hard", f"{remote}/{branch}")
        _git(wt, "clean", "-fd")
    else:
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "--detach", str(wt), f"{remote}/{branch}")


def publish_post(content: str, slug: str, title: str, run_id: str, s: Settings) -> dict:
    if not SLUG_RE.match(slug):
        raise PublishError(f"invalid slug {slug!r}: lowercase-kebab-case only")
    repo = Path(s.site_repo_path).expanduser().resolve()
    if not repo.exists() or not (repo / ".git").exists():
        raise PublishError(f"site repo not found at {repo}. Set SITE_REPO_PATH in .env")
    rel = f"{s.site_blog_dir}/{slug}.md"
    wt = s.worktree_dir
    if not wt.is_absolute():
        # git runs with cwd=repo, so a relative path must be anchored the same way —
        # otherwise git registers the worktree under <repo>/<wt> while this code
        # looks for <cwd>/<wt> and _prepare_worktree raises "not a registered worktree".
        wt = repo / wt
    _prepare_worktree(repo, wt, s.git_branch, s.git_remote)

    target = wt / s.site_blog_dir / f"{slug}.md"
    if not target.parent.exists():
        target.parent.mkdir(parents=True)   # new blog dir in a fresh worktree
    if target.exists() and run_id not in target.read_text(encoding="utf-8"):
        raise PublishError(f"{slug}.md already exists on main and was not created by this run. Change the slug in the metadata tab.")

    old = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(content, encoding="utf-8")

    if s.publish_mode == "files":
        diff = "\n".join(difflib.unified_diff(old.splitlines() if old else ["<new file>"],
                                              content.splitlines(), "origin/main", "proposed", lineterm="", n=3))
        _git(wt, "reset", "--hard", f"{s.git_remote}/{s.git_branch}")  # leave nothing behind
        _git(repo, "worktree", "prune")
        return {"mode": "files", "path": rel, "url": f"{s.site_base_url}/blog/{slug}/",
                "commit": None, "diff": diff}

    _git(wt, "add", "--", rel)
    _git(wt, "commit", "-m", f"content: {title[:60]}", "--", rel)
    push_err = None
    for attempt in range(3):
        try:
            _git(wt, "push", s.git_remote, f"HEAD:{s.git_branch}")
            push_err = None
            break
        except PublishError as e:
            push_err = e                      # main moved; rebase this one commit and retry
            try:
                _git(wt, "fetch", s.git_remote, s.git_branch)
                _git(wt, "rebase", f"{s.git_remote}/{s.git_branch}")
            except PublishError:
                pass
    if push_err:
        # keep the commit for inspection; the retry button runs steps 2-3 again
        raise PublishError(f"push failed after 3 attempts (commit kept on the worktree): {push_err}")
    head = _git(wt, "rev-parse", "--short", "HEAD")
    # leave the worktree clean for the next publish
    try:
        _git(wt, "reset", "--hard", f"{s.git_remote}/{s.git_branch}")
        _git(repo, "worktree", "prune")
    except PublishError:
        pass
    return {"mode": "git", "path": rel, "url": f"{s.site_base_url}/blog/{slug}/", "commit": head}
