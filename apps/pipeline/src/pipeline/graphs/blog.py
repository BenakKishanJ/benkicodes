"""Blog-mode LangGraph, lean edition (03-prd §6.1). Three base model calls per run:
plan -> write -> check (SEO included). Optional auto-revise <= 1.

 intake -> ingest -> plan -> [plan_review] -approve-> write -> check
                                           (revise -> plan on feedback)
           check -> revise (max 1) -> gates -> human_review --approve(=publish)--> publish
                                     (changes -> apply_feedback -> check)
                                     (reject  -> rejected)
                                     (hard gate fail -> blocked -> human_review)
Human checkpoints use interrupt(); state is checkpointed, so a run survives restarts
and a budget pause loses no state.
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .. import prompts as P
from ..config import Settings
from ..gateway.budget import ensure_allowed
from ..gateway.client import Gateway
from ..schemas import BlogPlan, CheckResult, Decision, PlanDecision
from ..state import BlogState, ev
from ..tools import gates as G
from ..tools.ingest import IngestError, clean_text, fetch_url, scan_injection
from ..tools.publisher import (
    build_frontmatter,
    publish_post,
    render_post,
    renumber_citations,
    trust_of,
)

PASS_AVG, PASS_MIN = 4.0, 3


def _read(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _banned(s: Settings) -> list[str]:
    return [l.strip() for l in _read(s.banned_file).splitlines() if l.strip() and not l.startswith("#")]


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```") and t.endswith("```") and t.count("```") == 2:
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return t.strip()


def check_passes(c: dict) -> bool:
    sc = list(c["scores"].values())
    high_unsupported = bool(c.get("unsupported_claims")) and any(i["severity"] == "high" for i in c.get("issues", []))
    return sum(sc) / len(sc) >= PASS_AVG and min(sc) >= PASS_MIN and not high_unsupported


def _budget(state: BlogState) -> tuple[float | None, float]:
    """(cap, spent so far). intake resolved the request override / default into the channel;
    POST /runs/{id}/budget updates the channel to resume a paused run."""
    return state.get("budget_usd") or None, float(state.get("usage", {}).get("usd", 0.0))


def _guard(state: BlogState, node: str) -> tuple[float | None, float]:
    """Raise BudgetPause before a model call when the per-run cap is exhausted."""
    cap, spent = _budget(state)
    try:
        ensure_allowed(spent, cap)
    except Exception as e:
        e.args = (*e.args, node) if e.args else (node,)   # tag which node ran out
        raise
    return cap, spent


def build_blog_graph(gw: Gateway | None, s: Settings, checkpointer, check_urls: bool = True):
    if gw is None:
        from ..gateway.client import get_gateway
        gw = get_gateway(s)
    voice = _read(s.voice_file)
    banned = _banned(s)

    # ------------------------------------------------------------------ nodes
    def intake(state: BlogState):
        req = state["inputs"]
        return {"status": "ingesting", "revision_count": 0, "human_rounds": 0,
                "budget_usd": float(req.get("budget_usd") or s.blog_budget_usd),
                "events": [ev("intake", f'Started: "{req["topic"]}" ({len(req["sources"])} source(s), cap ${state.get("budget_usd", s.blog_budget_usd):.2f})'),
                           ev("intake", "Plan checkpoint is " + ("on" if _plan_gate(state) else "off"))]}

    def ingest(state: BlogState):
        out, events = [], []
        for i, src in enumerate(state["inputs"]["sources"], 1):
            sid = f"S{i}"
            title, url, trust = src.get("title") or "", src.get("url"), "medium"
            try:
                if src["kind"] == "url":
                    fetched_title, text = fetch_url(url, s.request_timeout, s.allow_private_urls)
                    title = title or fetched_title
                    trust = trust_of(url)
                else:
                    text = src["text"]
            except (IngestError, OSError, ValueError, TypeError) as e:
                # one unreachable/malformed source must never kill the run
                events.append(ev("ingest", f"{sid} skipped ({url or 'text source'}): {type(e).__name__}: {e}", "warn"))
                continue
            text = clean_text(text, s.max_source_chars)
            if len(text) < 80:
                events.append(ev("ingest", f"{sid} skipped: too little text", "warn"))
                continue
            flags = scan_injection(text)
            out.append({"id": sid, "kind": src["kind"], "title": title or "untitled source", "url": url,
                        "text": text, "trust": trust, "flags": flags, "chars": len(text)})
            events.append(ev("ingest", f'{sid} ready: "{title or "untitled source"}" ({len(text)} chars, trust {trust})'
                             + (f" ⚠ {', '.join(flags)}" if flags else ""), "warn" if flags else "info"))
        if not out:
            raise RuntimeError("none of the sources could be read; see the activity log")
        return {"sources": out, "status": "planning", "events": events}

    def plan(state: BlogState):
        req = state["inputs"]
        cap, spent = _guard(state, "plan")
        o, u = gw.structured("plan", BlogPlan, P.PLAN_SYSTEM,
                             P.plan_user(req, state["sources"], s.max_source_chars,
                                         state.get("plan_feedback", []), state.get("plan")),
                             budget=cap, spent=spent)
        d = o.model_dump()
        return {"plan": d, "plan_feedback": [],
                "status": "awaiting_plan" if _plan_gate(state) else "writing",
                "events": [ev("plan", f'Plan: "{o.working_title}" ({len(o.sections)} sections)')],
                "usage": u, "calls": [u]}

    def _plan_gate(state: BlogState) -> bool:
        flag = state["inputs"].get("checkpoint_plan")
        return s.checkpoint_plan if flag is None else bool(flag)

    def plan_review(state: BlogState):
        if not _plan_gate(state):
            return {}
        raw = interrupt({"type": "plan", "plan": state["plan"], "sources": [
            {"id": x["id"], "title": x["title"], "url": x["url"], "trust": x.get("trust", "medium")}
            for x in state["sources"]]})
        d = PlanDecision.model_validate(raw)
        if d.action == "approve":
            upd = {"status": "writing", "events": [ev("plan_review", "Plan approved")]}
            if d.plan:
                upd["plan"] = BlogPlan.model_validate(d.plan).model_dump()
            return upd
        return {"plan_feedback": d.comments or ["Please improve the plan."], "status": "planning",
                "events": [ev("plan_review", f"Plan changes requested: {' | '.join(d.comments)[:200]}")]}

    def route_plan(state: BlogState) -> str:
        return "plan" if state.get("plan_feedback") else "write"

    def write(state: BlogState):
        lo, hi = P.LENGTH_WORDS[state["inputs"]["length"]]
        cap, spent = _guard(state, "write")
        text, u = gw.text("write", P.writer_system(voice, banned),
                          P.writer_user(state["inputs"], state["plan"], state["sources"],
                                        s.max_source_chars, lo, hi),
                          budget=cap, spent=spent)
        return {"draft_md": _strip_fence(text), "prev_draft": None, "status": "checking",
                "events": [ev("write", f"Draft written (~{len(text.split())} words)")], "usage": u, "calls": [u]}

    def check(state: BlogState):
        cap, spent = _guard(state, "check")
        c, u = gw.structured("check", CheckResult, P.CHECK_SYSTEM,
                             P.check_user(state["inputs"], state["plan"], state["draft_md"],
                                          state["sources"], s.max_source_chars),
                             budget=cap, spent=spent)
        d = c.model_dump()
        d["passed"] = check_passes(d)
        avg = sum(d["scores"].values()) / len(d["scores"])
        done = d["passed"] or state.get("revision_count", 0) >= s.max_auto_revisions
        return {"check": {k: d[k] for k in ("scores", "issues", "unsupported_claims", "seo", "passed")},
                "status": "gating" if done else "checking",
                "events": [ev("check", f'Critic scored {avg:.1f}/5, {len(d["issues"])} issue(s), {len(d["unsupported_claims"])} unsupported'
                              + (" (pass)" if d["passed"] else ""))], "usage": u, "calls": [u]}

    def route_check(state: BlogState) -> str:
        if state["check"]["passed"] or state.get("revision_count", 0) >= s.max_auto_revisions:
            return "gates"
        return "revise"

    def revise(state: BlogState):
        c = state["check"]
        cap, spent = _guard(state, "revise")
        text, u = gw.text("write", P.writer_system(voice, banned),
                          P.revise_user(state["draft_md"], c["issues"], c["unsupported_claims"]),
                          temperature=0.4,
                          budget=cap, spent=spent)
        n = state.get("revision_count", 0) + 1
        return {"prev_draft": state["draft_md"], "draft_md": _strip_fence(text), "revision_count": n,
                "status": "checking", "events": [ev("revise", f"Auto-revision {n} applied")], "usage": u, "calls": [u]}

    def gates(state: BlogState):
        _, cited = renumber_citations(state["draft_md"], state["sources"])
        _, err = build_frontmatter(state["check"]["seo"], cited, state["run_id"])
        lo, hi = P.LENGTH_WORDS[state["inputs"]["length"]]
        gs = G.run_gates(draft=state["draft_md"], sources=state["sources"], critique=state.get("check"),
                         frontmatter_error=err, banned=banned, max_similarity=s.max_similarity,
                         length_range=(lo, hi), check_urls=check_urls)
        n_fail = sum(g["status"] == "fail" for g in gs)
        n_warn = sum(g["status"] == "warn" for g in gs)
        return {"gates": gs, "status": "awaiting_review", "review_note": "",
                "events": [ev("gates", f"Gates: {n_fail} fail, {n_warn} warn", "warn" if n_fail else "info")]}

    def human_review(state: BlogState):
        raw = interrupt({"type": "review", "round": state.get("human_rounds", 0) + 1, "note": state.get("review_note", "")})
        return {"decision": Decision.model_validate(raw).model_dump(), "status": "awaiting_review"}

    def route_review(state: BlogState) -> str:
        d = state["decision"]
        if d["action"] == "reject":
            return "rejected"
        if d["action"] == "changes":
            return "apply_feedback"
        gs = state.get("gates", [])
        hard = any(g["name"] in ("schema", "citations") and g["status"] == "fail" for g in gs)  # cannot be overridden
        if hard or (G.has_blocking(gs) and not d.get("force")):
            return "blocked"
        return "publish"

    def blocked(state: BlogState):
        gs = state.get("gates", [])
        hard = sorted((g for g in gs if g["name"] in ("schema", "citations") and g["status"] == "fail"),
                      key=lambda g: g["name"] != "citations")
        note = (f"Cannot publish: {hard[0]['name']} check failed ({hard[0]['detail']}). Fix it in the draft or metadata, then approve again."
                if hard else "Publishing is blocked by failing checks. Fix the draft, or tick 'publish anyway' if you have verified it yourself.")
        return {"review_note": note, "events": [ev("review", "Approve blocked by failing gates", "warn")]}

    def rejected(state: BlogState):
        return {"status": "rejected", "events": [ev("review", "Run rejected by the author")]}

    def apply_feedback(state: BlogState):
        d, events = state["decision"], []
        draft = state["draft_md"]
        if d.get("edited_md") and d["edited_md"].strip() != draft.strip():
            draft = d["edited_md"].strip()                     # the author's own edits are authoritative
            events.append(ev("review", "Applied the author's direct edits"))
        if d.get("comments"):
            cap, spent = _guard(state, "feedback")
            text, _ = gw.text("write", P.writer_system(voice, banned),
                              P.feedback_user(draft, d["comments"]),
                              temperature=0.3,
                              budget=cap, spent=spent)
            draft = _strip_fence(text)
            events.append(ev("review", f"Applied {len(d['comments'])} comment(s)"))
        upd = {"prev_draft": state["draft_md"], "draft_md": draft,
               "human_rounds": state.get("human_rounds", 0) + 1, "decision": None, "status": "checking",
               "events": events}
        return upd

    def publish(state: BlogState):
        body, cited = renumber_citations(state["draft_md"], state["sources"])
        fm, err = build_frontmatter(state["check"]["seo"], cited, state["run_id"])
        if err or fm is None:
            raise RuntimeError(f"metadata invalid: {err}")
        result = publish_post(render_post(fm, body), state["check"]["seo"]["slug"],
                              fm.title, state["run_id"], s)
        msg = f"Published {result['url']}" + (f" (commit {result['commit']})" if result.get("commit") else " (file written, not committed)")
        return {"published": {**result, "related_paths": [result.get("path")]}, "status": "published",
                "events": [ev("publish", msg)]}

    # ------------------------------------------------------------------ wiring
    g = StateGraph(BlogState)
    for name, fn in [("intake", intake), ("ingest", ingest), ("plan", plan), ("plan_review", plan_review),
                     ("write", write), ("check", check), ("revise", revise), ("gates", gates),
                     ("human_review", human_review), ("blocked", blocked), ("rejected", rejected),
                     ("apply_feedback", apply_feedback), ("recheck", check), ("publish", publish)]:
        g.add_node(name, fn)
    g.add_edge(START, "intake")
    g.add_edge("intake", "ingest")
    g.add_edge("ingest", "plan")
    g.add_edge("plan", "plan_review")
    g.add_conditional_edges("plan_review", route_plan, {"plan": "plan", "write": "write"})
    g.add_edge("write", "check")
    g.add_conditional_edges("check", route_check, {"revise": "revise", "gates": "gates"})
    g.add_edge("revise", "check")
    g.add_edge("gates", "human_review")
    g.add_conditional_edges("human_review", route_review,
                            {"publish": "publish", "apply_feedback": "apply_feedback", "blocked": "blocked", "rejected": "rejected"})
    g.add_edge("blocked", "human_review")
    g.add_edge("apply_feedback", "recheck")
    g.add_edge("recheck", "gates")
    g.add_edge("rejected", END)
    g.add_edge("publish", END)
    return g.compile(checkpointer=checkpointer)
