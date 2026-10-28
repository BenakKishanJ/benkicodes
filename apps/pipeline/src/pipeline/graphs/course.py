"""Course-mode LangGraph (03-prd §7). One run builds one guided course, part by part.

PLANNING
 intake -> seed_docs -> research_refs -> refs_review ⟲ -> plan_course -> plan_review ⟲ -> init_repo
 (interrupts: refs_review, plan_review; resume payloads: RefsDecision, CoursePlanDecision)

PART LOOP (03-prd §7.5–7.7; runs once per part, in order)
 init_repo -> select_part -> code_step -> apply_commits ⟲(one retry) -> code_review ⟲(fix ×2)
   -> lesson_step -> quiz_step -> lesson_check -> part_gates -> lesson_review ⟲(fix ×2, back-to-code)
   -> publish_part -> more_parts -> (select_part | END)
 (interrupts: code_review, lesson_review; payloads: CodeReviewDecision, LessonReviewDecision)

No subgraphs, no fan-out: parts run in order, each seeing the real result of the
previous one. State is checkpointed; every interrupt survives restarts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .. import prompts as P
from ..config import Settings
from ..gateway.client import Gateway
from ..schemas import (CodeReviewDecision, CodeStepOutput, CoursePlan, CoursePlanDecision,
                       CourseRef, LessonCheckOutput, LessonReviewDecision, QuizOutput,
                       RefsDecision, ResearchOutput)
from ..state import CourseState, ev
from ..tools import roadmap as RM
from ..tools import scaffold, snippets as SN
from ..tools import gates as G
from ..tools.crawl import crawl_docs
from ..tools.ingest import IngestError, fetch_url
from ..tools.repo import CourseRepo, doctor, repo_dir

# planning-only terminal status (Phase A compatibility: runs that end after planning)
PLANNING_DONE = "planning_done"
MAX_CODE_FIXES = 2
MAX_LESSON_FIXES = 2
DIFF_CHARS = 8000
RETRY_MARKER = "[edit retry]"   # marks a code_feedback entry produced by an apply_commits failure


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip() + "\n"


def build_course_graph(gw: Gateway | None, s: Settings, checkpointer,
                       check_urls: bool = True):
    if gw is None:
        from ..gateway.client import get_gateway
        gw = get_gateway(s)

    # ------------------------------------------------------------------ helpers
    def _guard(state: CourseState, node: str):
        """Budget pause check before a model call, mirroring the blog graph."""
        from ..gateway.budget import ensure_allowed
        cap = state.get("budget_usd") or None
        spent = float(state.get("usage", {}).get("usd", 0.0))
        try:
            ensure_allowed(spent, cap)
        except Exception as e:
            e.args = (*e.args, node) if e.args else (node,)
            raise
        return cap, spent

    def _cache_pages(rid: str, pages: list[dict]) -> None:
        base = Path(s.data_dir) / "courses" / rid / "docs"
        base.mkdir(parents=True, exist_ok=True)
        for p in pages:
            (base / f"{p['id']}.txt").write_text(p["text"], encoding="utf-8")

    def _doc_excerpts(rid: str, docs: list[dict], urls: list[str], chars: int = 3500) -> list[dict]:
        """Docs entries for the cited urls, with bigger excerpts read from the disk cache.
        Ids are renumbered S1..Sn (part-local, like the blog's sources) so [S#] citations match."""
        want = [d for d in docs if d["url"] in urls]
        base = Path(s.data_dir) / "courses" / rid / "docs"
        out = []
        for i, d in enumerate(want, 1):
            text = ""
            try:
                text = (base / f"{d['id']}.txt").read_text(encoding="utf-8")
            except OSError:
                pass
            out.append({**d, "id": f"S{i}", "excerpt": text[:chars] or d.get("excerpt", "")})
        return out

    def _voice() -> tuple[str, list[str]]:
        voice = ""
        try:
            voice = s.voice_file.read_text(encoding="utf-8")
        except OSError:
            pass
        banned: list[str] = []
        try:
            banned = [x.strip() for x in s.banned_file.read_text(encoding="utf-8").splitlines() if x.strip()]
        except OSError:
            pass
        return voice, banned

    def _repo(state: CourseState) -> CourseRepo:
        rp = (state.get("repo") or {}).get("path")
        if not rp:
            raise RuntimeError("no course repo in state — run init_repo first")
        return CourseRepo(Path(rp), cmds=s.repo_cmds, timeout=s.repo_cmd_timeout)

    def _tests_of(state: CourseState) -> dict | None:
        """Last manual test run (written by POST /runs/{id}/repo/tests). Read fresh
        from disk rather than state so Ben can re-run after edits, mid-interrupt.
        Keyed by part_n so a previous part's result never leaks into this one."""
        try:
            t = json.loads((Path(s.data_dir) / "courses" / state["run_id"] / "tests.json").read_text())
            return t if t.get("part_n") == state.get("part_n") else None
        except (OSError, ValueError):
            return None

    # ------------------------------------------------------------------ nodes
    def intake(state: CourseState):
        req = state["inputs"]
        cap = float(req.get("budget_usd") or s.course_budget_usd)
        return {"status": "planning", "budget_usd": cap,
                "code_fixes": 0, "lesson_fixes": 0, "published_parts": [],
                "events": [ev("intake", f'Course: "{req["subject"]}" ({req["level"]}, '
                                       f'{req["min_parts"]}-{req["max_parts"]} parts, cap ${cap:.2f})'),
                           ev("intake", f"Repo: {req['repo_name']}"
                                        + (f" → {req['remote_url']}" if req.get("remote_url")
                                           else " (no remote yet — doctor will warn)"))]}

    def seed_docs(state: CourseState):
        req = state["inputs"]
        pages, skip = crawl_docs(req["docs_urls"], s.request_timeout, max_pages=30,
                                 allow_private=s.allow_private_urls)
        events = [ev("seed_docs", note, "warn") for note in skip]
        if not pages:
            raise RuntimeError("none of the official docs URLs could be read; see the activity log")
        docs = []
        for i, pg in enumerate(pages, 1):
            docs.append({"id": f"D{i}", "title": pg.get("title") or pg["url"], "url": pg["url"],
                         "chars": pg.get("chars") or len(pg.get("text", "")),
                         "excerpt": pg.get("text", "")[:600],
                         "has_images": bool(pg.get("has_images"))})
            pg["id"] = f"D{i}"
        _cache_pages(state["run_id"], pages)
        events.append(ev("seed_docs", f"Docs map: {len(docs)} official pages "
                                       f"({sum(d['chars'] for d in docs):,} chars cached)"))
        return {"docs": docs, "status": "planning", "events": events}

    def research_refs(state: CourseState):
        req = state["inputs"]
        cap, spent = _guard(state, "research_refs")
        o, u = gw.structured("research", ResearchOutput, P.RESEARCH_SYSTEM,
                             P.research_user(req["subject"], req.get("level", ""),
                                             req.get("audience", ""),
                                             req.get("docs_urls", []), req.get("hints", "")),
                             budget=cap, spent=spent)
        events = [ev("research_refs", f"Candidate references found in search: {len(o.refs)}")]
        refs: list[dict] = []
        for i, r in enumerate(o.refs, 1):
            ref = CourseRef(id=f"R{i}", title=r.title.strip()[:160], url=r.url, type=r.type,
                            illustrated=r.illustrated, level=r.level.strip(),
                            why=r.why.strip(), verified=False).model_dump()
            if check_urls:
                try:
                    _, text = fetch_url(r.url, s.request_timeout, s.allow_private_urls)
                    if len(text) >= 80:
                        ref["verified"] = True
                    else:
                        events.append(ev("research_refs", f"R{i} not verified: page too thin", "warn"))
                except (IngestError, OSError, ValueError) as e:
                    events.append(ev("research_refs", f"R{i} not verified: {type(e).__name__}: {e}", "warn"))
            else:
                ref["verified"] = True
            refs.append(ref)
        ok = sum(1 for r in refs if r["verified"])
        events.append(ev("research_refs", f"{ok}/{len(refs)} references verified by fetching"))
        return {"refs": refs, "status": "planning", "events": events, "usage": u, "calls": [u]}

    def refs_review(state: CourseState):
        raw = interrupt({"type": "refs", "refs": state.get("refs", []),
                         "docs": [{"id": d["id"], "title": d["title"], "url": d["url"]}
                                  for d in state.get("docs", [])]})
        d = RefsDecision.model_validate(raw)
        source = {r["id"]: r for r in state.get("refs", [])}
        kept = [source[rid] for rid in d.keep if rid in source]
        events = []
        for a in d.added:
            ref = {"id": "RA-new", "title": a.title.strip()[:160], "url": a.url, "type": a.type,
                   "illustrated": a.illustrated, "level": a.level.strip(), "why": a.why.strip(),
                   "verified": False}
            try:
                _, text = fetch_url(a.url, s.request_timeout, s.allow_private_urls)
                if len(text) >= 80:
                    ref["verified"] = True
                else:
                    events.append(ev("refs_review", f'added "{ref["title"][:40]}": too thin to verify', "warn"))
            except (IngestError, OSError, ValueError) as e:
                events.append(ev("refs_review",
                                 f'added "{ref["title"][:40]}": not verified ({type(e).__name__})', "warn"))
            kept.append(ref)
        if not kept:
            raise RuntimeError("refs_review approved with zero kept references — the plan needs at least one")
        kept = [dict(r, id=f"R{i + 1}") for i, r in enumerate(kept)]  # renumber contiguously
        valid_ids = {r["id"] for r in kept}
        inspired_by = [i for i in d.inspired_by if i in valid_ids]
        events.append(ev("refs_review",
                         f"References locked: {len(kept)} kept ({sum(1 for r in kept if r['verified'])} verified), "
                         f"{len(inspired_by)} credited as inspired-by"))
        return {"refs": kept, "inspired_by": inspired_by, "status": "planning", "events": events}

    def plan_course(state: CourseState):
        req = state["inputs"]
        cap, spent = _guard(state, "plan_course")
        events, retry_note, o, u = [], "", None, {}
        for attempt in (1, 2):
            prompt = P.plan_course_user(
                req, state.get("docs", []), state.get("refs", []),
                state.get("plan_feedback", []),
                json.dumps(state["plan"], ensure_ascii=False) if attempt == 2 and state.get("plan") else None)
            if retry_note:
                prompt += retry_note
            invalid = ""
            try:
                o, u = gw.structured("plan", CoursePlan, P.PLAN_COURSE_SYSTEM, prompt,
                                     budget=cap, spent=spent)
            except RuntimeError as e:
                events.append(ev("plan_course",
                                 f"attempt {attempt} produced no valid plan: {str(e)[:240]}", "warn"))
                retry_note = "\n\nYour previous answer was invalid. Return a corrected CoursePlan."
                continue
            docs_urls = {d["url"] for d in state.get("docs", [])}
            ref_ids = {r["id"] for r in state.get("refs", [])}
            bad_u = sorted({x for p in o.parts for x in p.doc_urls if x not in docs_urls})
            bad_r = sorted({x for p in o.parts for x in p.ref_ids if x not in ref_ids})
            if not bad_u and not bad_r:
                break
            invalid = "; ".join(filter(None, [
                f"doc_urls not in the docs map: {', '.join(bad_u)}" if bad_u else "",
                f"ref_ids not in the kept references: {', '.join(bad_r)}" if bad_r else ""]))
            events.append(ev("plan_course", f"plan invalid (attempt {attempt}): {invalid}", "warn"))
            retry_note = f"\n\nYour previous plan violated these constraints, fix them:\n- {invalid}"
        else:
            raise RuntimeError(
                f"course plan invalid after retry: {invalid or 'no valid structured output'}")
        n = len(o.parts)
        if not (req["min_parts"] <= n <= req["max_parts"] + 2):  # small overshoot tolerated; review trims
            events.append(ev("plan_course",
                             f"plan has {n} parts, requested {req['min_parts']}-{req['max_parts']}", "warn"))
        events.append(ev("plan_course",
                         f'plan: "{o.project.name}" — {n} parts, stack {", ".join(o.project.stack[:4])}'))
        return {"plan": o.model_dump(), "plan_feedback": [], "status": "planning",
                "events": events, "usage": u, "calls": [u]}

    def course_plan_review(state: CourseState):
        raw = interrupt({"type": "course_plan", "plan": state.get("plan"),
                         "refs": state.get("refs", []), "docs": state.get("docs", [])})
        d = CoursePlanDecision.model_validate(raw)
        if d.action != "approve":
            msg = "; ".join(d.comments) or "Please improve the plan."
            return {"plan_feedback": [msg], "status": "planning",
                    "events": [ev("plan_review", f"plan changes requested: {msg[:200]}")]}
        events = [ev("plan_review", "plan approved — slugs and order frozen, creating the repo")]
        upd: dict = {"status": "preparing_repo", "events": events}
        if d.plan:
            try:
                plan = CoursePlan.model_validate(d.plan)  # Ben's edits win, but must still validate
            except Exception as e:
                evs = ev("plan_review", f"edited plan invalid ({str(e)[:160]}) — treated as a change request", "warn")
                return {"plan_feedback": [evs["msg"]], "status": "planning", "events": [evs]}
            bad_r = sorted({x for p in plan.parts for x in p.ref_ids
                            if x not in {r["id"] for r in state.get("refs", [])}})
            bad_u = sorted({x for p in plan.parts for x in p.doc_urls
                            if x not in {dd["url"] for dd in state.get("docs", [])}})
            if bad_r or bad_u:
                evs = ev("plan_review",
                         f"edited plan references unknown ids ({', '.join((bad_r + bad_u)[:4])}) — treated as a change request", "warn")
                return {"plan_feedback": [evs["msg"]], "status": "planning", "events": [evs]}
            upd["plan"] = plan.model_dump()
        return upd

    def route_plan(state: CourseState) -> str:
        return "plan_course" if state.get("plan_feedback") else "init_repo"

    def init_repo(state: CourseState):
        req = state["inputs"]
        plan = CoursePlan.model_validate(state["plan"])
        dest = repo_dir(s.courses_root, req["repo_name"])
        owner = scaffold.owner_from_remote(req.get("remote_url"))
        n_files, pkg = scaffold.render_course_template(
            s.templates_dir, dest, name=req["repo_name"], project=plan.project.name,
            summary=plan.project.summary, github_owner=owner)
        import subprocess
        subprocess.run(["git", "init", "-b", "main", str(dest)], check=True, capture_output=True)
        repo = CourseRepo(dest)
        if req.get("remote_url"):
            repo.git("remote", "add", "origin", req["remote_url"], check=False)
        repo.stage_and_commit(f"part-0: scaffold the {plan.project.name} project")
        arch = plan.project.architecture_md.strip()
        if arch:  # replace the template stub with the plan's architecture
            (Path(dest) / "docs" / "ARCHITECTURE.md").write_text(f"# Architecture\n\n{arch}\n", encoding="utf-8")
            repo.stage_and_commit("part-0: record the planned architecture in docs/ARCHITECTURE.md")
        # tag AFTER all part-0 commits so the tag sits on main's head — the part
        # loop branches wip/part-1 from this tag, and publish ff-merges back
        repo.tag(0, f"part-0: scaffold of {plan.project.name}")
        checks = doctor(dest, req.get("remote_url"))
        events = [ev("init_repo", f"repo created at {dest} ({n_files} files, package `{pkg}`)"),
                  ev("init_repo", "tagged part-0"),
                  ev("init_repo",
                     "remote " + (f"reachable, {'empty (ready for the first push)' if checks['empty_ok'] else f'pre-existing: {str(checks.get('detail', ''))[:140]}'}"
                                  if checks["remote_ok"] else "not provided — add one before the first push"),
                     "info" if checks["remote_ok"] and checks["empty_ok"] else "warn")]
        if arch:
            events.append(ev("init_repo", "docs/ARCHITECTURE.md updated from the plan"))
        return {"repo": {**state.get("repo", {}), "path": str(dest), "name": req["repo_name"], "package": pkg,
                         "remote_url": req.get("remote_url"), "remote_ok": checks["remote_ok"],
                         "empty_ok": checks["empty_ok"], "tagged": ["part-0"]},
                "status": "coding", "events": events}

    # ================================================================== part loop (03-prd §7.5)
    def select_part(state: CourseState):
        plan = CoursePlan.model_validate(state["plan"])
        n = len(state.get("published_parts", []))
        if n >= len(plan.parts):
            return {"status": "published", "events": [ev("select_part", "All parts published — course complete")]}
        part = plan.parts[n].model_dump()
        repo = _repo(state)
        start_sha = repo.start_part(n + 1)
        return {"part_n": n + 1, "part": part, "part_start_sha": start_sha,
                "code_fixes": 0, "code_feedback": [], "commits": [], "tests": None,
                "lesson_md": "", "prev_lesson_md": None, "lesson_html": "", "quiz": [],
                "check": {}, "gates": [], "lesson_fixes": 0, "review_rounds": 0,
                "decision": None, "review_note": "", "status": "coding",
                "events": [ev("select_part", f"Part {n + 1}/{len(plan.parts)}: {part['title']} "
                                              f"(branch wip/part-{n + 1} from {start_sha[:7]})")]}

    def code_step(state: CourseState):
        req = state["inputs"]
        cap, spent = _guard(state, "code_step")
        plan = CoursePlan.model_validate(state["plan"])
        repo = _repo(state)
        arch = ""
        try:
            arch = repo.read("docs/ARCHITECTURE.md")
        except Exception:  # noqa: BLE001 missing file is fine
            pass
        o, u = gw.structured(
            "plan_code", CodeStepOutput, P.CODE_SYSTEM,
            P.code_user(plan.project.model_dump(), state["part"], repo.tree_paths(),
                        repo.files_line_numbered(repo.tree_paths()), arch,
                        state.get("summary_for_next", ""),
                        [d["excerpt"][:2500] for d in _doc_excerpts(state["run_id"], state.get("docs", []),
                                                                    state["part"].get("doc_urls", []), 2500)],
                        feedback=state.get("code_feedback") or None,
                        prev_commits=state.get("commits") or None),
            budget=cap, spent=spent)
        return {"code": o.model_dump(), "status": "coding",
                "events": [ev("code_step", f"Planned {len(o.commits)} commit(s): "
                                           + " | ".join(c.message[:60] for c in o.commits))],
                "usage": u, "calls": [u]}

    def apply_commits(state: CourseState):
        """Apply the CodeStepOutput on wip/part-N. One in-graph retry with the precise
        error; a second failure resets the branch and fails the node (no partial state)."""
        repo = _repo(state)
        n = state["part_n"]
        code = CodeStepOutput.model_validate(state["code"])
        plan = CoursePlan.model_validate(state["plan"])
        events = []
        try:
            commits = []
            for c in code.commits:
                for dep in c.add_dependencies:
                    repo.run(["uv", "add", *(["--dev"] if dep.dev else []), dep.name])
                    events.append(ev("apply_commits", f"added dependency {dep.name}" + (" (dev)" if dep.dev else "")))
                paths = []
                for e in c.edits:
                    repo.apply_file_edit(e.path, e.op, e.content, [x.model_dump() for x in e.edits])
                    paths.append(e.path)
                sha = repo.stage_and_commit(c.message, paths=paths or None)
                commits.append({"sha": sha, "message": c.message})
                events.append(ev("apply_commits", f"{sha[:7]} {c.message}"))
            # deterministic docs upkeep: ARCHITECTURE.md from the model, PARTS.md from the plan
            arch = code.architecture_update.strip()
            if arch:
                (Path(repo.root) / "docs" / "ARCHITECTURE.md").write_text(
                    arch if arch.startswith("#") else f"# Architecture\n\n{arch}\n", encoding="utf-8")
            parts_md = (Path(repo.root) / "docs" / "PARTS.md")
            try:
                parts_md_text = parts_md.read_text(encoding="utf-8")
                row = f"| `part-{n}` | {plan.parts[n - 1].slug} | {plan.parts[n - 1].title} |"
                if f"`part-{n}`" not in parts_md_text:
                    parts_md.write_text(parts_md_text.rstrip("\n") + f"\n| `part-{n}` | {plan.parts[n - 1].slug} | {plan.parts[n - 1].title} |\n",
                                        encoding="utf-8")
            except OSError:
                pass
            if repo.status():
                sha = repo.stage_and_commit(f"part-{n}: update docs (architecture, parts index)")
                commits.append({"sha": sha, "message": f"part-{n}: update docs (architecture, parts index)"})
                events.append(ev("apply_commits", f"{sha[:7]} docs updated"))
            changed = repo.changed_lines()
            note = ""
            if not 200 <= changed <= 600:
                note = f" (outside the 200-600 line budget: {changed})"
            return {"commits": commits, "status": "reviewing_code", "code_feedback": [],
                    "events": events + [ev("apply_commits", f"{len(commits)} commit(s) applied, {changed} changed lines{note}",
                                            "warn" if note else "info")]}
        except Exception as e:  # noqa: BLE001 — one retry with the precise error, then fail clean
            err = f"{type(e).__name__}: {e}"
            repo.git("checkout", f"wip/part-{n}")
            repo.git("reset", "--hard", state.get("part_start_sha", "HEAD"))
            repo.git("clean", "-fd")
            fb = state.get("code_feedback") or []
            already_retried = bool(fb and fb[-1].startswith(RETRY_MARKER))
            if already_retried:
                raise RuntimeError(f"edits failed again after a retry; branch reset to {state.get('part_start_sha', 'HEAD')[:7]}: {err[:400]}") from e
            events.append(ev("apply_commits", f"edits rejected ({err[:200]}) — retrying once from a clean branch", "warn"))
            return {"code_feedback": fb + [f"{RETRY_MARKER}\n{err[:600]}"],
                    "status": "coding", "events": events}

    def route_apply(state: CourseState) -> str:
        return "code_step" if state.get("status") == "coding" else "code_review"

    def commit_diffs(repo: CourseRepo, commits: list[dict], start_sha: str) -> tuple[list[dict], str]:
        """Per-commit diffs + the cumulative diff, bounded for the interrupt payload."""
        per, cum = [], ""
        prev = start_sha
        for c in commits:
            d = repo.git("diff", f"{prev}..{c['sha']}", "--stat", "--patch", "--no-color").stdout
            per.append({**c, "diff": d[:DIFF_CHARS]})
            prev = c["sha"]
        if commits:
            cum = repo.git("diff", f"{start_sha}..{commits[-1]['sha']}", "--stat", "--no-color").stdout
        return per, cum

    def code_review(state: CourseState):
        repo = _repo(state)
        n = state["part_n"]
        commits = state.get("commits", [])
        per, cum = commit_diffs(repo, commits, state.get("part_start_sha", "HEAD"))
        changed = repo.changed_lines()
        raw = interrupt({"type": "code_review", "part_n": n, "part_title": state["part"]["title"],
                         "repo_path": str(repo.root), "commits": per, "cumulative_stat": cum,
                         "changed_lines": changed, "code_fixes": state.get("code_fixes", 0),
                         "max_fixes": MAX_CODE_FIXES, "tests": _tests_of(state),
                         "note": state.get("review_note", "")})
        d = CodeReviewDecision.model_validate(raw)
        if d.action == "accept":
            events = [ev("code_review", "code accepted")]
            upd: dict = {"decision": None, "review_note": "", "status": "writing_lesson", "events": events,
                         "tests": _tests_of(state)}
            if not repo.is_clean():  # Ben's manual edits — commit them as part of the part
                msg = (d.commit_message or f"part-{n}: manual adjustments").strip()
                sha = repo.stage_and_commit(msg if msg.startswith(f"part-{n}") else f"part-{n}: {msg}")
                commits = commits + [{"sha": sha, "message": msg}]
                upd["commits"] = commits
                events.append(ev("code_review", f"manual edits committed: {sha[:7]} {msg}"))
            return upd
        # fix requested
        fixes = state.get("code_fixes", 0) + 1
        if fixes > MAX_CODE_FIXES:
            return {"review_note": f"Code fixes are exhausted ({MAX_CODE_FIXES}/{MAX_CODE_FIXES}). "
                                   "Edit the files yourself and accept, or reject the run.",
                    "events": [ev("code_review", "fix budget exhausted — accept with manual edits or reject", "warn")]}
        return {"code_fixes": fixes, "code_feedback": [d.comment or "Please revise."],
                "review_note": "", "status": "coding",
                "events": [ev("code_review", f"fix requested ({fixes}/{MAX_CODE_FIXES}): {(d.comment or '')[:200]}")]}

    def route_code_review(state: CourseState) -> str:
        if state.get("review_note") and state.get("status") != "writing_lesson":
            return "code_review"   # exhausted note -> interrupt again
        return "lesson_step" if state.get("status") == "writing_lesson" else "code_step"

    def lesson_step(state: CourseState):
        cap, spent = _guard(state, "lesson_step")
        voice, banned = _voice()
        repo = _repo(state)
        n = state["part_n"]
        per, _ = commit_diffs(repo, state.get("commits", []), state.get("part_start_sha", "HEAD"))
        touched = sorted({e["path"] for cm in state.get("code", {}).get("commits", []) for e in cm["edits"]})
        files = repo.files_line_numbered([p for p in repo.tree_paths()
                                          if p in touched or p.startswith("tests/")], max_bytes=30_000)
        doc_ex = _doc_excerpts(state["run_id"], state.get("docs", []), state["part"].get("doc_urls", []))
        glossary = state.get("glossary") or {}
        text, u = gw.text("write", P.lesson_system(voice, banned),
                          P.lesson_user(state["part"], state.get("commits", []), files,
                                        state.get("code", {}).get("notes_for_lesson", ""),
                                        doc_ex, glossary, state.get("summary_for_next", "")),
                          budget=cap, spent=spent)
        lesson = _strip_fence(text)
        return {"lesson_md": lesson, "prev_lesson_md": state.get("lesson_md") or None,
                "status": "quizzing",
                "events": [ev("lesson_step", f"lesson drafted (~{len(lesson.split())} words, "
                                             f"{len(SN.find_placeholders(lesson))} code placeholders)")],
                "usage": u, "calls": [u]}

    def quiz_step(state: CourseState):
        cap, spent = _guard(state, "quiz_step")
        events, o, u, retry = [], None, {}, ""
        for attempt in (1, 2):
            try:
                o, u = gw.structured("fast", QuizOutput, P.QUIZ_SYSTEM,
                                     P.quiz_user(state["part"], state.get("glossary") or {}) + retry,
                                     budget=cap, spent=spent)
            except RuntimeError as e:
                retry = f"\n\nYour previous answer was invalid: {str(e)[:200]}. Return corrected questions."
                continue
            # deterministic validation beyond the schema: correct ids spread across positions
            # (flag the lazy pattern where EVERY question's answer sits first, not one question)
            flagged = [q.id for q in o.questions if q.correct and all(
                q.options.index(next((x for x in q.options if x.id == cid), q.options[0])) == 0
                for cid in q.correct)]
            problems = []
            if len(o.questions) > 1 and len(flagged) == len(o.questions):
                problems.append("every question's correct option is first; spread them across positions")
            if problems:
                retry = "\n\nFix these and return the questions again:\n- " + "\n- ".join(problems)
                events.append(ev("quiz_step", f"quiz invalid (attempt {attempt}): {'; '.join(problems)}", "warn"))
                continue
            break
        else:
            raise RuntimeError("quiz invalid after retry")
        return {"quiz": [q.model_dump() for q in o.questions], "status": "checking_lesson",
                "events": events + [ev("quiz_step", f"{len(o.questions)} quiz question(s) validated")],
                "usage": u, "calls": [u]}

    def lesson_check(state: CourseState):
        cap, spent = _guard(state, "lesson_check")
        doc_ex = _doc_excerpts(state["run_id"], state.get("docs", []), state["part"].get("doc_urls", []), 2500)
        c, u = gw.structured("check", LessonCheckOutput, P.LESSON_CHECK_SYSTEM,
                             P.lesson_check_user(state["part"], state["lesson_md"],
                                                 state.get("commits", []), doc_ex),
                             budget=cap, spent=spent)
        part = state["part"]
        glossary = dict(state.get("glossary") or {})
        for term in part.get("concepts", []):
            glossary.setdefault(term, f"taught in part {part['n']}")
        return {"check": c.model_dump(), "summary_for_next": c.summary_for_next,
                "glossary": glossary, "status": "gating",
                "events": [ev("lesson_check", f"reviewer scored {sum(c.scores.values()) / max(len(c.scores), 1):.1f}/5, "
                                              f"{len(c.issues)} issue(s), {len(c.unsupported_claims)} unsupported")],
                "usage": u, "calls": [u]}

    def part_gates(state: CourseState):
        """Expand snippets, validate the module frontmatter, run the §10.2 gates."""
        repo = _repo(state)
        n = state["part_n"]
        plan = CoursePlan.model_validate(state["plan"])
        req = state["inputs"]
        urls = RM.github_urls((state.get("repo") or {}).get("remote_url"),
                              req["repo_name"], n - 1, n)
        lesson_html, problems = SN.expand_placeholders(
            state["lesson_md"], repo.read_head, urls["blob"])
        problems += SN.inline_block_problems(state["lesson_md"])
        # the module frontmatter is built deterministically — it either validates or the gate fails
        fm_error = ""
        try:
            sources = [{"title": d["title"], "url": d["url"]}
                       for d in _doc_excerpts(state["run_id"], state.get("docs", []),
                                              state["part"].get("doc_urls", []), 200)]
            if not sources:
                fm_error = "the part cites no official docs (doc_urls empty) — module schema needs >= 1 source"
            resources = [dict(r) for r in state.get("refs", []) if r["id"] in set(state["part"].get("ref_ids", []))]
            code = {"startTag": f"part-{n - 1}", "endTag": f"part-{n}",
                    "compareUrl": urls["compare"], "treeUrl": urls["tree"],
                    "commits": [{"sha": c["sha"], "message": c["message"],
                                 "url": urls["commit"](c["sha"])} for c in state.get("commits", [])],
                    "files": sorted({e["path"] for cm in state.get("code", {}).get("commits", [])
                                     for e in cm["edits"]})}
            MD = RM.build_module_md(order=n, title=state["part"]["title"],
                                    minutes=state["part"].get("estimatedMinutes", 90),
                                    objectives=state["part"]["objectives"], sources=sources,
                                    resources=resources, code=code, quiz=state.get("quiz", []),
                                    body=lesson_html, run_id=state["run_id"])
        except Exception as e:  # noqa: BLE001 — frontmatter construction errors surface in the gate
            MD, fm_error = "", f"{type(e).__name__}: {str(e)[:300]}"
        tags_ok = bool(state.get("commits")) and repo.git(
            "rev-parse", "--verify", "--quiet", f"refs/tags/part-{n - 1}", check=False).returncode == 0
        kept_urls = {r["url"] for r in state.get("refs", []) if r.get("verified")}
        gs = G.run_part_gates(
            lesson=lesson_html, module_fm_error=fm_error, snippet_problems=problems,
            inline_problems=[], commits=state.get("commits", []), tags_ok=tags_ok,
            sources=[{**d, "text": d.get("excerpt", "")} for d in _doc_excerpts(state["run_id"], state.get("docs", []),
                                                                                   state["part"].get("doc_urls", []), 200)],
            cited=G.cited_ids(state["lesson_md"]), critique=state.get("check"),
            objectives=state["part"]["objectives"], resources=resources, kept_urls=kept_urls,
            tests=_tests_of(state), similarity_limit=s.max_similarity,
            banned=_voice()[1], check_urls=check_urls)
        n_fail = sum(g["status"] == "fail" for g in gs)
        n_warn = sum(g["status"] == "warn" for g in gs)
        return {"gates": gs, "lesson_html": lesson_html, "status": "awaiting_review",
                "review_note": "", "module_md": MD,
                "events": [ev("part_gates", f"Part gates: {n_fail} fail, {n_warn} warn", "warn" if n_fail else "info")]}

    def lesson_review(state: CourseState):
        hard = [g for g in state.get("gates", []) if g["name"] in ("schema", "snippets", "code state", "quiz", "resources")
                and g["status"] == "fail"]
        raw = interrupt({"type": "lesson_review", "part_n": state["part_n"],
                         "round": state.get("review_rounds", 0) + 1, "note": state.get("review_note", ""),
                         "hard_fail": hard[0]["detail"] if hard else None})
        d = LessonReviewDecision.model_validate(raw)
        if d.action == "approve":
            if hard:
                return {"review_note": f"Cannot publish: {hard[0]['name']} — {hard[0]['detail']}",
                        "events": [ev("lesson_review", "approve blocked by a hard gate", "warn")]}
            upd: dict = {"decision": d.model_dump(), "review_note": "", "status": "publishing",
                         "events": [ev("lesson_review", "lesson approved — publishing the part")]}
            if d.edited_md and d.edited_md.strip() != state["lesson_md"].strip():
                upd["lesson_md"] = d.edited_md.strip() + "\n"   # Ben's edits win; gates re-run in publish
                upd["events"] = [ev("lesson_review", "applied the author's direct edits")] + upd["events"]
            return upd
        if d.action == "back_to_code":
            fixes = state.get("code_fixes", 0) + 1   # counts against the code budget
            if fixes > MAX_CODE_FIXES:
                return {"review_note": "Back-to-code budget exhausted; edit the lesson text or reject.",
                        "events": [ev("lesson_review", "back-to-code budget exhausted", "warn")]}
            return {"code_fixes": fixes, "status": "reviewing_code", "review_note": "",
                    "code_feedback": [d.comment or "The lesson revealed a code problem — revisit."],
                    "events": [ev("lesson_review", f"back to code ({fixes}/{MAX_CODE_FIXES})")]}
        fixes = state.get("lesson_fixes", 0) + 1
        if fixes > MAX_LESSON_FIXES:
            return {"review_note": "Lesson fixes exhausted — edit the markdown yourself and approve, or go back to code.",
                    "events": [ev("lesson_review", "lesson fix budget exhausted", "warn")]}
        return {"lesson_fixes": fixes, "lesson_feedback": [d.comment or "Please revise the lesson."],
                "review_note": "", "status": "fixing_lesson",
                "events": [ev("lesson_review", f"lesson fix requested ({fixes}/{MAX_LESSON_FIXES}): {(d.comment or '')[:200]}")]}

    def route_lesson_review(state: CourseState) -> str:
        st = state.get("status")
        if st == "publishing":
            return "publish_part"
        if st == "reviewing_code":
            return "code_review"
        if st == "fixing_lesson":
            return "lesson_fix"
        return "lesson_review"   # exhausted note -> interrupt again

    def lesson_fix(state: CourseState):
        cap, spent = _guard(state, "lesson_fix")
        voice, banned = _voice()
        comments = state.get("lesson_feedback", [])
        text, u = gw.text("write", P.lesson_system(voice, banned),
                          P.feedback_user(state["lesson_md"], comments),
                          temperature=0.3, budget=cap, spent=spent)
        return {"lesson_md": _strip_fence(text), "status": "gating", "lesson_feedback": [],
                "events": [ev("lesson_fix", f"applied {len(comments)} comment(s)")], "usage": u, "calls": [u]}

    def publish_part(state: CourseState):
        """Safe order (03-prd §7.7): course repo (tag+push) → build files → site repo → record."""
        d = state.get("decision") or {}
        lesson = (d.get("edited_md") or state["lesson_md"])
        repo = _repo(state)
        n = state["part_n"]
        req = state["inputs"]
        plan = CoursePlan.model_validate(state["plan"])
        events = []
        # 1. preconditions
        if repo.status():
            raise RuntimeError(f"repo has uncommitted changes:\n{repo.status()[:400]}")
        # 2. course repo: ff-merge, tag, push, verify
        res = RM.merge_tag_push(repo, n, (state.get("repo") or {}).get("remote_url"))
        if res["pushed"]:
            events.append(ev("publish_part", f"pushed main + {res['tag']} (verified on the remote)"))
        else:
            events.append(ev("publish_part", f"tagged {res['tag']} locally"
                             + (f"; push FAILED: {res['detail']}" if (state.get('repo') or {}).get("remote_url") else " — no remote configured"),
                             "warn" if (state.get("repo") or {}).get("remote_url") else "info"))
        tagged = sorted({*((state.get("repo") or {}).get("tagged") or []), res["tag"]})
        # 3. build module md + roadmap index (deterministic)
        urls = RM.github_urls((state.get("repo") or {}).get("remote_url"), req["repo_name"], n - 1, n)
        lesson_html, problems = SN.expand_placeholders(lesson, repo.read_head, urls["blob"])
        if problems:
            raise RuntimeError("lesson snippets unresolved at publish: " + "; ".join(problems[:3]))
        sources = [{"title": x["title"], "url": x["url"]}
                   for x in _doc_excerpts(state["run_id"], state.get("docs", []), state["part"].get("doc_urls", []), 200)]
        resources = [dict(r) for r in state.get("refs", []) if r["id"] in set(state["part"].get("ref_ids", []))]
        code = {"startTag": f"part-{n - 1}", "endTag": f"part-{n}", "compareUrl": urls["compare"],
                "treeUrl": urls["tree"],
                "commits": [{"sha": c["sha"], "message": c["message"], "url": urls["commit"](c["sha"])}
                            for c in state.get("commits", [])],
                "files": sorted({e["path"] for cm in state.get("code", {}).get("commits", []) for e in cm["edits"]})}
        module_md = RM.build_module_md(order=n, title=state["part"]["title"],
                                       minutes=state["part"].get("estimatedMinutes", 90),
                                       objectives=state["part"]["objectives"], sources=sources,
                                       resources=resources, code=code, quiz=state.get("quiz", []),
                                       body=lesson_html, run_id=state["run_id"])
        course_slug = req["repo_name"].lower()
        # record the part first so the index reflects it (site fields backfilled after the push)
        published = state.get("published_parts", []) + [{
            "n": n, "slug": state["part"]["slug"], "title": state["part"]["title"],
            "tag": res["tag"], "tag_url": f"{urls['base']}/releases/tag/{res['tag']}",
            "compare_url": urls["compare"], "tree_url": urls["tree"],
            "lesson_url": RM.lesson_url(s.site_base_url, course_slug, f"{n:02d}-{state['part']['slug']}"),
            "site_commit": None, "paths": []}]
        index_md = RM.build_index_md(plan=plan.model_dump(), req=req,
                                     repo_url=(state.get("repo") or {}).get("remote_url"),
                                     kept_refs=state.get("refs", []), inspired_by_ids=state.get("inspired_by", []),
                                     refs=state.get("refs", []), published=published,
                                     run_id=state["run_id"])
        files = {f"{s.site_roadmaps_dir}/{course_slug}/index.md": index_md,
                 f"{s.site_roadmaps_dir}/{course_slug}/modules/{n:02d}-{state['part']['slug']}.md": module_md}
        # 4. site repo
        site = RM.publish_site(files, f"content(roadmap): {plan.project.name} part {n} - {state['part']['title']}", s)
        published[-1]["site_commit"] = site.get("commit")
        published[-1]["paths"] = site["paths"]
        events.append(ev("publish_part", "site files " +
                         ("committed " + (site.get("commit") or "") if site["mode"] == "git" else "written (files mode — not committed)")))
        events.append(ev("publish_part", f"part {n} recorded: {published[-1]['lesson_url']}"))
        return {"published_parts": published, "decision": None, "status": "between_parts",
                "repo": {**state.get("repo", {}), "tagged": tagged}, "events": events}

    def more_parts(state: CourseState) -> str:
        plan = CoursePlan.model_validate(state["plan"])
        return "select_part" if len(state.get("published_parts", [])) < len(plan.parts) else "complete"

    def complete(state: CourseState):
        return {"status": "published", "events": [ev("complete", "course complete — every part published")]}

    # ------------------------------------------------------------------ wiring
    g = StateGraph(CourseState)
    for name, fn in [("intake", intake), ("seed_docs", seed_docs), ("research_refs", research_refs),
                     ("refs_review", refs_review), ("plan_course", plan_course),
                     ("plan_review", course_plan_review), ("init_repo", init_repo),
                     ("select_part", select_part), ("code_step", code_step), ("apply_commits", apply_commits),
                     ("code_review", code_review), ("lesson_step", lesson_step), ("quiz_step", quiz_step),
                     ("lesson_check", lesson_check), ("part_gates", part_gates),
                     ("lesson_review", lesson_review), ("lesson_fix", lesson_fix),
                     ("publish_part", publish_part), ("complete", complete)]:
        g.add_node(name, fn)
    g.add_edge(START, "intake")
    g.add_edge("intake", "seed_docs")
    g.add_edge("seed_docs", "research_refs")
    g.add_edge("research_refs", "refs_review")
    g.add_edge("refs_review", "plan_course")
    g.add_edge("plan_course", "plan_review")
    g.add_conditional_edges("plan_review", route_plan,
                            {"plan_course": "plan_course", "init_repo": "init_repo"})
    # ---- part loop ----
    g.add_edge("init_repo", "select_part")
    g.add_edge("select_part", "code_step")
    g.add_edge("code_step", "apply_commits")
    g.add_conditional_edges("apply_commits", route_apply,
                            {"code_step": "code_step", "code_review": "code_review"})
    g.add_conditional_edges("code_review", route_code_review,
                            {"code_step": "code_step", "lesson_step": "lesson_step", "code_review": "code_review"})
    g.add_edge("lesson_step", "quiz_step")
    g.add_edge("quiz_step", "lesson_check")
    g.add_edge("lesson_check", "part_gates")
    g.add_edge("part_gates", "lesson_review")
    g.add_conditional_edges("lesson_review", route_lesson_review,
                            {"publish_part": "publish_part", "code_review": "code_review",
                             "lesson_fix": "lesson_fix", "lesson_review": "lesson_review"})
    g.add_edge("lesson_fix", "part_gates")
    g.add_conditional_edges("publish_part", more_parts,
                            {"select_part": "select_part", "complete": "complete"})
    g.add_edge("complete", END)
    return g.compile(checkpointer=checkpointer)
