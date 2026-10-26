"""Turns an approved draft into a post file in the Astro repo and (optionally) commits + pushes it to main."""
from __future__ import annotations
import re, subprocess
from datetime import date
from pathlib import Path
import yaml
from pydantic import ValidationError
from ..config import Settings
from ..schemas import Frontmatter, SourceRef
from .gates import CITE_RE


class PublishError(Exception):
    pass


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
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise PublishError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()[:500]}")
    return r.stdout.strip()


def publish_post(content: str, slug: str, title: str, run_id: str, s: Settings) -> dict:
    repo = Path(s.site_repo_path).expanduser().resolve()
    target_dir = repo / s.site_blog_dir
    if not repo.exists() or not target_dir.exists():
        raise PublishError(f"site repo not found at {target_dir}. Set SITE_REPO_PATH in .env")
    target = target_dir / f"{slug}.md"
    if target.exists() and f"pipelineRunId: {run_id}" not in target.read_text(encoding="utf-8"):
        raise PublishError(f"{target.name} already exists and was not created by this run. Change the slug in the metadata tab.")

    if s.publish_mode == "files":
        target.write_text(content, encoding="utf-8")
        return {"mode": "files", "path": str(target), "url": f"{s.site_base_url}/blog/{slug}/", "commit": None}

    if not (repo / ".git").exists():
        raise PublishError("PUBLISH_MODE=git but the site repo is not a git repository")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != s.git_branch:
        raise PublishError(f"site repo is on '{branch}', expected '{s.git_branch}'. Switch branches or change GIT_BRANCH.")
    _git(repo, "pull", "--rebase", "--autostash", s.git_remote, s.git_branch)
    target.write_text(content, encoding="utf-8")
    rel = str(target.relative_to(repo))
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-m", f"content: {title[:60]}", "--", rel)
    try:
        _git(repo, "push", s.git_remote, s.git_branch)
    except PublishError:
        _git(repo, "reset", "--soft", "HEAD~1")  # keep the file, drop the unpushed commit so a retry is clean
        raise
    return {"mode": "git", "path": rel, "url": f"{s.site_base_url}/blog/{slug}/", "commit": _git(repo, "rev-parse", "--short", "HEAD")}
