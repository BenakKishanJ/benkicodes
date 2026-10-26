import subprocess

import yaml
from langgraph.types import Command

from pipeline.gateway.budget import BudgetPause
from pipeline.graphs.blog import build_blog_graph
from pipeline.schemas import Frontmatter

from .fakes import FakeGateway

REQ = {"topic": "LangGraph state", "audience": "devs", "angle": None, "length": "short", "notes": "", "checkpoint_plan": True,
       "sources": [{"kind": "text", "title": "LangGraph docs", "url": "https://docs.example.com/state", "text": "State is a shared object. " * 40}]}


def pending(g, cfg):
    snap = g.get_state(cfg)
    return [i.value for t in snap.tasks for i in t.interrupts]


def remote_show(work, rel):
    subprocess.run(["git", "fetch", "origin"], cwd=work, check=True, capture_output=True)  # no working-tree change
    return subprocess.run(["git", "show", f"origin/main:{rel}"], cwd=work, check=True, capture_output=True, text=True).stdout


def test_full_flow_publishes_commit(settings, saver, site):
    gw = FakeGateway(fail_first_check=True)
    g = build_blog_graph(gw, settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r1"}}

    g.invoke({"run_id": "r1", "mode": "blog", "inputs": REQ}, cfg)
    assert pending(g, cfg)[0]["type"] == "plan"

    g.invoke(Command(resume={"action": "revise", "comments": ["add a comparison"]}), cfg)   # plan regenerated, asks again
    assert pending(g, cfg)[0]["type"] == "plan"
    v = g.get_state(cfg).values
    assert any("add a comparison" in e["msg"] for e in v["events"] if e["node"] == "plan_review")

    g.invoke(Command(resume={"action": "approve"}), cfg)
    p = pending(g, cfg)[0]
    assert p["type"] == "review"
    v = g.get_state(cfg).values
    assert v["revision_count"] == 1                      # first check failed -> one auto revision -> pass
    assert v["status"] == "awaiting_review"
    names = {x["name"]: x["status"] for x in v["gates"]}
    assert names["schema"] == "pass" and names["citations"] == "pass" and names["similarity"] == "pass"

    g.invoke(Command(resume={"action": "changes", "comments": ["tighten the intro"]}), cfg)
    v = g.get_state(cfg).values
    assert "tighten the intro" in v["draft_md"] and v["human_rounds"] == 1 and v["prev_draft"]
    assert pending(g, cfg)[0]["round"] == 2

    g.invoke(Command(resume={"action": "approve"}), cfg)
    v = g.get_state(cfg).values
    assert v["status"] == "published" and v["published"]["commit"]
    rel = "apps/site/src/content/blog/langgraph-state-explained.md"
    post = remote_show(site[0], rel)                     # main worktree must stay untouched
    fm = yaml.safe_load(post.split("---\n", 2)[1])
    Frontmatter.model_validate(fm)                       # matches the site contract
    assert "[\\[1\\]](#sources-h)" in post and "[S1]" not in post
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=site[1], capture_output=True, text=True, check=False).stdout
    assert "content:" in log                             # pushed to the remote main


def test_reject_ends_run(settings, saver):
    g = build_blog_graph(FakeGateway(), settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r2"}}
    req = {**REQ, "checkpoint_plan": False}
    g.invoke({"run_id": "r2", "mode": "blog", "inputs": req}, cfg)
    assert pending(g, cfg)[0]["type"] == "review"
    g.invoke(Command(resume={"action": "reject"}), cfg)
    assert g.get_state(cfg).values["status"] == "rejected" and not g.get_state(cfg).next


def test_flow_makes_three_model_calls(settings, saver):
    gw = FakeGateway()
    g = build_blog_graph(gw, settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r9"}}
    req = {**REQ, "checkpoint_plan": False}
    g.invoke({"run_id": "r9", "mode": "blog", "inputs": req}, cfg)
    v = g.get_state(cfg).values
    assert v["check"]["passed"] is True
    assert [c["task"] for c in v["calls"]] == ["plan", "write", "check"]   # one plan, one write, one check incl. SEO


def test_missing_url_blocks_even_with_force(settings, saver):
    g = build_blog_graph(FakeGateway(), settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r3"}}
    req = {**REQ, "checkpoint_plan": False, "sources": [{"kind": "text", "title": "my notes", "url": None, "text": "State is a shared object. " * 40}]}
    g.invoke({"run_id": "r3", "mode": "blog", "inputs": req}, cfg)
    g.invoke(Command(resume={"action": "approve", "force": True}), cfg)
    v = g.get_state(cfg).values
    assert v["status"] != "published"
    assert "citations" in v["review_note"]
    assert pending(g, cfg)[0]["type"] == "review"        # back at review with the note


def test_user_edit_is_authoritative(settings, saver):
    g = build_blog_graph(FakeGateway(), settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r4"}}
    g.invoke({"run_id": "r4", "mode": "blog", "inputs": {**REQ, "checkpoint_plan": False}}, cfg)
    edited = "## Mine\n\nMy own text [S1].\n\n## Also mine\n\nMore [S1].\n"
    g.invoke(Command(resume={"action": "changes", "edited_md": edited}), cfg)
    assert g.get_state(cfg).values["draft_md"] == edited.strip()


def test_budget_pauses_after_cap(settings, saver):
    g = build_blog_graph(FakeGateway(charge=0.7), settings, saver, check_urls=False)
    cfg = {"configurable": {"thread_id": "r5"}}
    req = {**REQ, "checkpoint_plan": False, "budget_usd": 1.0}
    try:
        g.invoke({"run_id": "r5", "mode": "blog", "inputs": req}, cfg)
        raise AssertionError("expected BudgetPause")
    except BudgetPause as e:
        assert isinstance(e, BudgetPause), e
    v = g.get_state(cfg).values
    assert v["draft_md"] and v["status"] == "checking"   # saved after write; nothing lost
