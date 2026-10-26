import time
from fastapi.testclient import TestClient
from pipeline.api import create_app
from .fakes import FakeLLM

H = {"X-Admin-Token": "tok"}
BODY = {"topic": "LangGraph state", "length": "short", "checkpoint_outline": False,
        "sources": [{"kind": "text", "title": "Docs", "url": "https://docs.example.com/s", "text": "State is a shared object. " * 40}]}


def wait(c, rid, want, t=15):
    end = time.time() + t
    while time.time() < end:
        r = c.get(f"/runs/{rid}", headers=H).json()
        if r["status"] in want:
            return r
        time.sleep(0.1)
    raise AssertionError(f"timeout, last status {r['status']}: {r.get('error')}")


def test_auth_and_full_cycle(settings):
    c = TestClient(create_app(settings, FakeLLM(), check_urls=False))
    assert c.get("/runs").status_code == 401
    assert c.get("/runs", headers={"X-Admin-Token": "nope"}).status_code == 401
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert r["status"] == "awaiting_review" and r["draft_html"].startswith("<p>") and r["sources"][0]["id"] == "S1"
    assert "text" not in r["sources"][0] and r["usage"]["calls"] > 0
    assert any(g["name"] == "schema" and g["status"] == "pass" for g in r["gates"])
    assert c.post(f"/runs/{rid}/resume", json={"action": "bogus"}, headers=H).status_code == 422
    assert c.post(f"/runs/{rid}/resume", json={"action": "approve"}, headers=H).status_code == 202
    r = wait(c, rid, {"published", "failed"})
    assert r["status"] == "published" and r["published"]["commit"]
    assert [x["id"] for x in c.get("/runs", headers=H).json()] == [rid]


def test_html_is_escaped(settings):
    class Evil(FakeLLM):
        def text(self, system, user, tier="strong", temperature=0.7):
            return "## A [S1]\n\n<script>alert(1)</script>\n\n## B [S1]\n\nx", {"input": 1, "output": 1, "calls": 1}
    c = TestClient(create_app(settings, Evil(False), check_urls=False))
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"awaiting_review", "failed"})
    assert "<script>" not in r["draft_html"]


def test_failed_run_can_retry(settings):
    class Flaky(FakeLLM):
        n = 0
        def structured(self, schema, system, user, tier="fast"):
            from pipeline.schemas import SEOPackage
            if schema is SEOPackage and Flaky.n == 0:
                Flaky.n = 1
                raise RuntimeError("model hiccup")
            return super().structured(schema, system, user, tier)
    c = TestClient(create_app(settings, Flaky(False), check_urls=False))
    rid = c.post("/runs", json=BODY, headers=H).json()["id"]
    r = wait(c, rid, {"failed", "awaiting_review"})
    assert r["status"] == "failed" and "hiccup" in r["error"]
    assert c.post(f"/runs/{rid}/retry", headers=H).status_code == 202
    assert wait(c, rid, {"awaiting_review", "failed"})["status"] == "awaiting_review"


def test_cors_allows_only_the_local_site(settings):
    c = TestClient(create_app(settings, FakeLLM(), check_urls=False))
    ok = c.options("/runs", headers={"Origin": "http://localhost:4321", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-admin-token,content-type"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:4321"
    bad = c.options("/runs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-admin-token"})
    assert "access-control-allow-origin" not in bad.headers
