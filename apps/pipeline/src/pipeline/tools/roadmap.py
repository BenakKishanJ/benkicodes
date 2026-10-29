"""Builds and publishes one course part across the two repos (03-prd §7.7).

Order matters and is enforced by the caller (publish_part node):
  1. course repo: merge wip/part-N -> main (ff), tag part-N, push, verify
  2. build module md + roadmap index md (deterministically — no model calls)
  3. site repo: worktree commit + push with rebase-retry (publish_mode=git)
     or dry-run files mode for staging previews.

Every GitHub link on the live page points at the tag pushed in step 1, so a
step-3 failure leaves public state consistent (tag exists, page not live yet).
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from ..schemas import (ModuleFrontmatter, ModuleResource, ModuleSource, RoadmapPlanned,
                       RoadmapFrontmatter, CodePanel, CodeCommitRef)
from .publisher import PublishError, _git, _prepare_worktree, render_frontmatter
from .repo import CourseRepo


def _https_base(repo_url: str) -> str:
    """git@host:owner/repo(.git) and ssh://git@host/owner/repo(.git) → https://host/owner/repo."""
    m = re.match(r"(?:git@|ssh://git@)([\w.-]+)[:/]([^/]+)/(.+?)(?:\.git)?/?$", repo_url)
    return f"https://{m[1]}/{m[2]}/{m[3]}" if m else repo_url


def github_urls(repo_url: str | None, name: str, start: int, n: int) -> dict:
    """compare/tree/commit URL builders for a part. Without a remote the urls still
    point at the canonical github location (links go live when the repo is pushed).
    SSH remotes are normalized to https (site schema requires https GitHub URLs)."""
    base = _https_base(repo_url) if repo_url else f"https://github.com/benkicodes/{name}"
    base = re.sub(r"\.git/?$", "", base)
    return {
        "base": base.rstrip("/"),
        "compare": f"{base.rstrip('/')}/compare/part-{start}...part-{n}",
        "tree": f"{base.rstrip('/')}/tree/part-{n}",
        "commit": lambda sha: f"{base.rstrip('/')}/commit/{sha}",
        "blob": f"{base.rstrip('/')}/blob/part-{n}",
    }


def lesson_url(site_base_url: str, course_slug: str, module_slug: str) -> str:
    return f"{site_base_url.rstrip('/')}/roadmaps/{course_slug}/{module_slug}/"


def build_module_md(*, order: int, title: str, minutes: int, objectives: list[str],
                    sources: list[dict], resources: list[dict], code: dict,
                    quiz: list[dict], body: str, run_id: str, today: date | None = None) -> str:
    """Frontmatter (validated against the moduleSchema mirror) + expanded lesson body."""
    today = today or datetime.now(UTC).date()
    fm = ModuleFrontmatter(
        title=title[:70], order=order, estimatedMinutes=minutes, objectives=objectives,
        sources=[ModuleSource(title=x["title"], url=x["url"], accessed=today) for x in sources],
        resources=[ModuleResource(**{k: v for k, v in x.items() if k in
                                     ("title", "url", "type", "why", "illustrated")}) for x in resources],
        code=CodePanel(
            startTag=code["startTag"], endTag=code["endTag"], compareUrl=code["compareUrl"],
            treeUrl=code["treeUrl"],
            commits=[CodeCommitRef(sha=c["sha"][:7], message=c["message"], url=c["url"]) for c in code["commits"]],
            files=code.get("files", [])),
        quiz=quiz, lastReviewed=today, draft=False, pipelineRunId=run_id)
    return render_frontmatter(fm.model_dump(mode="python", exclude_none=True), body)


def build_index_md(*, plan: dict, req: dict, repo_url: str | None, kept_refs: list[dict],
                   inspired_by_ids: list[str], refs: list[dict], published: list[dict],
                   run_id: str, today: date | None = None) -> str:
    """Roadmap index.md: created on the first part, re-rendered on each later part."""
    today = today or datetime.now(UTC).date()
    parts = plan["parts"]
    n_done = len(published)
    ref_by_id = {r["id"]: r for r in refs}
    inspired = [{"title": ref_by_id[i]["title"], "url": ref_by_id[i]["url"],
                 "note": ref_by_id[i].get("why") or ""}
                for i in inspired_by_ids if i in ref_by_id]
    planned = [RoadmapPlanned(slug=p["slug"], title=p["title"], estimatedMinutes=p.get("estimatedMinutes", 90))
               for p in parts[n_done:]]
    hours = round(sum(p.get("estimatedMinutes", 90) for p in parts) / 60, 1)
    obj = sorted({o for p in parts for o in p["objectives"]})
    if len(obj) < 3:  # top up from the project's final features (schema needs >= 3)
        obj = (obj + [f for f in plan["project"].get("final_features", []) if f not in obj])[:6]
    if len(obj) < 3:
        raise PublishError(f"the plan yields only {len(obj)} roadmap outcomes (schema needs 3); "
                           "add distinct objectives or final_features to the plan")
    fm = RoadmapFrontmatter(
        title=f"{plan['project']['name']}: build it, part by part"[:70],
        description=plan["project"]["summary"][:160],
        level=req.get("level", "intermediate"),
        estimatedHours=hours,
        prerequisites=[],  # derived later if the plan names any; empty is schema-valid
        outcomes=obj,
        tags=[], status="complete" if planned == [] and n_done >= 1 else "in-progress",
        planned=[p.model_dump() for p in planned],
        project={"repo": repo_url or f"https://github.com/benkicodes/{req['repo_name']}",
                 "defaultBranch": "main", "template": False, "license": "MIT",
                 "stack": plan["project"]["stack"][:8], "summary": plan["project"]["summary"][:240]},
        inspiredBy=inspired,
        lastReviewed=today, version="1.0", draft=False, featured=False, pipelineRunId=run_id)
    body = (f"> {plan['project']['summary']}\n\n"
            "## How this works\n\n"
            "Every module is a working step of the same project. Clone the repo, check out the "
            "tag of the module you are reading (`git checkout part-N`), and code along — the lesson "
            "shows the exact diff that step adds.\n\n")
    if inspired:
        body += "## Inspired by\n\n" + "\n".join(f"- [{x['title']}]({x['url']})" + (f" — {x['note']}" if x["note"] else "")
                                                 for x in inspired) + "\n"
    return render_frontmatter(fm.model_dump(mode="python", exclude_none=True), body)


def merge_tag_push(repo: CourseRepo, n: int, remote_url: str | None) -> dict:
    """Course-repo half of publishing: ff-merge wip/part-N into main, tag, push, verify."""
    branch = f"wip/part-{n}"
    tag = f"part-{n}"
    if not repo.is_clean():
        raise PublishError(f"{branch} has uncommitted changes; commit them first")
    repo.git("checkout", "main")
    cp = repo.git("rev-parse", "--verify", tag + "^{commit}", check=False)
    tagged_commit = cp.stdout.strip() if cp.returncode == 0 else ""
    if tagged_commit:
        # idempotent retry: a prior attempt already merged+tagged — only main must match
        if tagged_commit == repo.git("rev-parse", "main").stdout.strip():
            head = repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            if head != "main":
                repo.git("checkout", "main")
        else:
            raise PublishError(f"tag {tag} already exists — refusing to republish")
    elif repo.git("merge", "--ff-only", branch, check=False).returncode != 0:
        repo.git("checkout", branch)  # leave the repo where Ben's work is
        raise PublishError(f"main cannot fast-forward to {branch} (diverged); fix manually")
    if not tagged_commit:
        repo.tag(n, f"part-{n}")
    pushed = False
    detail = ""
    if remote_url:
        cp = repo.git("push", "origin", "main", tag, check=False)
        pushed = cp.returncode == 0
        if not pushed:
            detail = (cp.stderr or cp.stdout).strip()[-300:]
        else:
            v = repo.git("ls-remote", "--tags", "origin", tag, check=False)
            pushed = tag in v.stdout
    return {"tag": tag, "pushed": pushed, "detail": detail}


def publish_site(files: dict[str, str], commit_message: str, s) -> dict:
    """Site-repo half: write files in the detached worktree, commit, push (rebase-retry ×3).

    publish_mode=files is the dry run: writes nothing public, returns diffs.
    """
    repo = Path(s.site_repo_path).expanduser().resolve()
    if not repo.exists() or not (repo / ".git").exists():
        raise PublishError(f"site repo not found at {repo}. Set SITE_REPO_PATH in .env")
    wt = s.worktree_dir
    if not wt.is_absolute():
        wt = repo / wt
    _prepare_worktree(repo, wt, s.git_branch, s.git_remote)
    rels = []
    for rel, content in files.items():
        target = wt / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rels.append(rel)
    if s.publish_mode == "files":
        import difflib
        diffs = {}
        for rel in rels:
            old = ""
            try:
                old = _git(wt, "show", f"{s.git_remote}/{s.git_branch}:{rel}")
            except PublishError:
                pass
            diffs[rel] = "\n".join(difflib.unified_diff(old.splitlines(), files[rel].splitlines(),
                                                        f"origin/{s.git_branch}", "proposed", lineterm="", n=2))
        _git(wt, "reset", "--hard", f"{s.git_remote}/{s.git_branch}")
        _git(repo, "worktree", "prune")
        return {"mode": "files", "paths": rels, "commit": None, "diffs": diffs}
    _git(wt, "add", "--", *rels)
    _git(wt, "commit", "-m", commit_message, "--", *rels)
    push_err = None
    for _ in range(3):
        try:
            _git(wt, "push", s.git_remote, f"HEAD:{s.git_branch}")
            push_err = None
            break
        except PublishError as e:
            push_err = e
            try:
                _git(wt, "fetch", s.git_remote, s.git_branch)
                _git(wt, "rebase", f"{s.git_remote}/{s.git_branch}")
            except PublishError:
                pass
    if push_err:
        raise PublishError(f"push failed after 3 attempts (commit kept on the worktree): {push_err}")
    head = _git(wt, "rev-parse", "--short", "HEAD")
    try:
        _git(wt, "reset", "--hard", f"{s.git_remote}/{s.git_branch}")
        _git(repo, "worktree", "prune")
    except PublishError:
        pass
    return {"mode": "git", "paths": rels, "commit": head}
