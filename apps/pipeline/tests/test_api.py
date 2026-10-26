import time

from fastapi.testclient import TestClient

from pipeline.api import create_app

from .fakes import FakeGateway

H = {"X-Admin-Token": "tok"}
BODY = {"topic": "LangGraph state", "length": "short", "checkpoint_plan": False,
        "sources": [{"kind": "text", "title": "Docs", "url": "https://docs.example.com/s", "text": "State is a shared object. " * 40}]}


def wait(c, rid, want, t=15):
    r = {}
    end = time.time() + t
    while time.time() < end:
        r = c.get(f"/runs/{rid}", headers=H).json()
        if r["status"] in want:
            return r
        time.sleep(0.1)
    raise AssertionError(f"timeout, last status {r['status']}: {r.get('error')}")


def test_auth_and_full_cycle(settings):
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    assert c.get("/runs").status_code == 401
    assert c.get("/runs", headers={"X-Admin-Token": "nope"}).status_code == 401
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert r["status"] == "awaiting_review" and r["draft_html"].startswith("<p>") and r["sources"][0]["id"] == "S1"
    assert "text" not in r["sources"][0] and r["usage"]["calls"] >= 3
    assert {x["task"] for x in r["calls"]} >= {"plan", "write", "check"}
    assert any(g["name"] == "schema" and g["status"] == "pass" for g in r["gates"])
    assert c.post(f"/runs/{rid}/resume", json={"action": "bogus"}, headers=H).status_code == 422
    r_full = c.get(f"/runs/{rid}", headers=H).json()
    assert r_full["check"]["seo"]["slug"] == "langgraph-state-explained"
    assert c.post(f"/runs/{rid}/resume", json={"action": "approve"}, headers=H).status_code == 202
    r = wait(c, rid, {"published", "failed"})
    assert r["status"] == "published" and r["published"]["commit"]
    assert [x["id"] for x in c.get("/runs", headers=H).json()] == [rid]


def test_plan_checkpoint_flow(settings):
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    rid = c.post("/runs", json={**BODY, "checkpoint_plan": True}, headers=H).json()["id"]
    r = wait(c, rid, {"awaiting_plan", "failed"})
    assert r["status"] == "awaiting_plan" and r["pending"]["type"] == "plan"
    assert r["plan"]["working_title"] == "LangGraph state explained"
    assert c.post(f"/runs/{rid}/resume", json={"action": "approve"}, headers=H).status_code == 202
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert r["status"] == "awaiting_review"


def test_html_is_escaped(settings):
    class Evil(FakeGateway):
        def text(self, task, system, user, temperature=None, *, budget=None, spent=0.0):
            return "## A [S1]\n\n<script>alert(1)</script>\n\n## B [S1]\n\nx", {"input": 1, "output": 1, "calls": 1, "usd": 0}
    c = TestClient(create_app(settings, Evil(False), check_urls=False))
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert "<script>" not in r["draft_html"]


def test_failed_run_can_retry(settings):
    class Flaky(FakeGateway):
        n = 0
        def structured(self, task, schema, system, user, *, budget=None, spent=0.0):
            if schema.__name__ == "CheckResult" and Flaky.n == 0:
                Flaky.n = 1
                raise RuntimeError("model hiccup")
            return super().structured(task, schema, system, user, budget=budget, spent=spent)
    c = TestClient(create_app(settings, Flaky(False), check_urls=False))
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"failed", "awaiting_review"})
    assert r["status"] == "failed" and "hiccup" in r["error"]
    assert c.post(f"/runs/{rid}/retry", headers=H).status_code == 202
    assert wait(c, rid, {"awaiting_review", "failed"})["status"] == "awaiting_review"


def test_budget_pause_resume_via_endpoint(settings):
    c = TestClient(create_app(settings, FakeGateway(charge=0.7), check_urls=False))
    rid = c.post("/runs", json={**BODY, "budget_usd": 1.0}, headers=H).json()["id"]
    r = wait(c, rid, {"paused_budget", "failed", "awaiting_review"})
    assert r["status"] == "paused_budget" and r["usage"]["budget"]["pause_exhausted"]
    too_small = c.post(f"/runs/{rid}/budget", json={"budget_usd": 0.5}, headers=H)
    assert too_small.status_code == 422                     # below what was already spent
    resp = c.post(f"/runs/{rid}/budget", json={"budget_usd": 3.0}, headers=H).json()
    assert resp["resumed"] is True
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert r["status"] == "awaiting_review"
    assert r["usage"]["budget"]["cap"] == 3.0


def test_settings_models_credits(settings):
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    s = c.get("/settings", headers=H).json()
    assert set(s["tasks"]) == {"plan", "write", "check"} | {"fast"}
    assert s["api_key_configured"] is False
    assert c.get("/models", headers=H).status_code == 503            # FakeGateway has no catalog
    assert c.get("/credits", headers=H).json()["total_credits"] == "12.5"


def test_stream_reports_published(settings):
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    wait(c, rid, {"awaiting_review"})
    c.post(f"/runs/{rid}/resume", json={"action": "approve"}, headers=H)
    wait(c, rid, {"published"})
    with c.stream("GET", f"/runs/{rid}/stream", headers=H) as r:
        body = "".join(x for x in r.iter_text())
    assert "event: done" in body and "published" in body


def test_library_lists_site_posts(settings, site):
    (site[0] / "apps/site/src/content/blog/hello.md").write_text(
        "---\ntitle: Hello\ndescription: a\npubDate: 2026-01-01\ncategory: guide\ntags: [x]\ndraft: true\n---\nbody")
    (site[0] / "apps/site/src/content/blog/not-a-post.txt").write_text("nope")
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    lib = c.get("/library", headers=H).json()
    assert [x["file"] for x in lib] == ["hello.md"] and lib[0]["draft"] is True


def test_cors_allows_only_the_local_site(settings):
    c = TestClient(create_app(settings, FakeGateway(), check_urls=False))
    ok = c.options("/runs", headers={"Origin": "http://localhost:4321", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-admin-token,content-type"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:4321"
    bad = c.options("/runs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-admin-token"})
    assert "access-control-allow-origin" not in bad.headers
