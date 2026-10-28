"""Course-mode LangGraph (03-prd §7). One run builds one guided course, part by part.

PLANNING (implemented in Phase A)
 intake -> seed_docs -> research_refs -> refs_review ⟲ -> plan_course -> plan_review ⟲ -> init_repo
 (interrupts: refs_review, plan_review; resume payloads: RefsDecision, CoursePlanDecision)

PART LOOP (Phase B inserts select_part → … → publish_part between init_repo and END;
 `init_repo -> publish_part -> END defeats the stub today and disappears with Phase B.)

No subgraphs, no fan-out: parts run in order, each seeing the real result of the
previous one. State is checkpointed; both interrupts survive restarts.
"""
from __future__ import annotations

import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .. import prompts as P
from ..config import Settings
from ..gateway.client import Gateway
from ..schemas import CoursePlan, CoursePlanDecision, CourseRef, RefsDecision, ResearchOutput
from ..state import CourseState, ev
from ..tools import scaffold
from ..tools.crawl import crawl_docs
from ..tools.ingest import IngestError, fetch_url
from ..tools.repo import CourseRepo, doctor, repo_dir

# planning-only terminal status for Phase A; Phase B replaces it with the part loop
PLANNING_DONE = "planning_done"


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
        repo.tag(0, f"part-0: scaffold of {plan.project.name}")
        checks = doctor(dest, req.get("remote_url"))
        events = [ev("init_repo", f"repo created at {dest} ({n_files} files, package `{pkg}`)"),
                  ev("init_repo", "tagged part-0"),
                  ev("init_repo",
                     "remote " + (f"reachable, {'empty (ready for the first push)' if checks['empty_ok'] else f'pre-existing: {str(checks.get('detail', ''))[:140]}'}"
                                  if checks["remote_ok"] else "not provided — add one before the first push"),
                     "info" if checks["remote_ok"] and checks["empty_ok"] else "warn")]
        arch = plan.project.architecture_md.strip()
        if arch:  # replace the template stub with the plan's architecture
            (Path(dest) / "docs" / "ARCHITECTURE.md").write_text(f"# Architecture\n\n{arch}\n", encoding="utf-8")
            repo.stage_and_commit("part-0: record the planned architecture in docs/ARCHITECTURE.md")
            events.append(ev("init_repo", "docs/ARCHITECTURE.md updated from the plan"))
        return {"repo": {"path": str(dest), "name": req["repo_name"], "package": pkg,
                         "remote_url": req.get("remote_url"), "remote_ok": checks["remote_ok"],
                         "empty_ok": checks["empty_ok"], "tagged": ["part-0"]},
                "status": PLANNING_DONE, "events": events}

    # ------------------------------------------------------------------ wiring
    g = StateGraph(CourseState)
    for name, fn in [("intake", intake), ("seed_docs", seed_docs), ("research_refs", research_refs),
                     ("refs_review", refs_review), ("plan_course", plan_course),
                     ("plan_review", course_plan_review), ("init_repo", init_repo)]:
        g.add_node(name, fn)
    g.add_edge(START, "intake")
    g.add_edge("intake", "seed_docs")
    g.add_edge("seed_docs", "research_refs")
    g.add_edge("research_refs", "refs_review")
    g.add_edge("refs_review", "plan_course")
    g.add_edge("plan_course", "plan_review")
    g.add_conditional_edges("plan_review", route_plan,
                            {"plan_course": "plan_course", "init_repo": "init_repo"})
    # Phase B inserts: init_repo -> select_part -> ... -> publish_part -> more_parts -> END
    g.add_edge("init_repo", END)
    return g.compile(checkpointer=checkpointer)
