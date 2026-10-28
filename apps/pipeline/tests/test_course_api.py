"""Phase-A acceptance, in-process (03-prd §7.3): course run from intake to an
approved plan and a repo on disk with tag `part-0` — with a stubbed gateway and
a stubbed crawl so no model calls or network happen."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from pipeline.graphs import course as course_graph
from pipeline.schemas import CoursePlan, ResearchOutput


class StubGateway:
    """Answers research + plan_course with canned, schema-valid output."""

    def __init__(self, docs_urls):
        self.docs_urls = docs_urls

    def structured(self, task, schema, system, user, *, budget=None, spent=0.0):
        if task == "research":
            return (ResearchOutput(refs=[
                {"title": f"Ref {i}", "url": f"https://example-source-{i}.com/guide",
                 "type": "article" if i % 2 else "repo",
                 "illustrated": i == 1, "level": "beginner", "why": f"reason {i}"}
                for i in range(1, 6)]), {"input": 10, "output": 10, "calls": 1, "usd": 0.01})
        assert task == "plan"
        plan = CoursePlan.model_validate({
            "project": {"name": "Toy Research Agent", "slug": "toy-research-agent",
                        "summary": "You will build a tiny research agent, part by part.",
                        "stack": ["python", "uv", "pytest"], "architecture_md": "A tiny agent.",
                        "final_features": ["searches", "writes a report"]},
            "parts": [
                {"n": n, "slug": f"part-{n}", "title": f"Part {n}",
                 "objectives": ["can do X", "can do Y"],
                 "concepts": ["concepts"], "steps": [{"title": "step", "intent": "why"}],
                 "doc_urls": self.docs_urls, "ref_ids": ["R1", "R2"],
                 "resource_notes": {"R1": "why here"}, "estimatedMinutes": 60}
                for n in (1, 2)]})
        return (plan, {"input": 20, "output": 20, "calls": 1, "usd": 0.02})

    def text(self, *a, **k):  # pragma: no cover - course planning never calls text
        raise AssertionError("course planning must not use text()")

    def credits(self):
        return {"credits": 10}


DOCS_URL = "https://langchain-ai.github.io/langgraph/"

@pytest.fixture
def run_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")
    templates = Path(__file__).parents[1] / "templates" / "course-repo"
    docs = [DOCS_URL]

    def fake_crawl(seed_urls, timeout=15.0, max_pages=30, allow_private=False):
        pages = [{"title": f"Doc {i}", "url": u, "text": f"Doc {i} page text. " * 40} for i, u in enumerate(seed_urls, 1)]
        return pages, []

    monkeypatch.setattr(course_graph, "crawl_docs", fake_crawl)
    from pipeline.config import Settings
    s = Settings(data_dir=data_dir, courses_dir=tmp_path / "courses", templates_dir=templates,
                 allow_private_urls=True, openrouter_api_key="x", admin_token="t")
    from pipeline.api import create_app
    return create_app(s, StubGateway(docs), check_urls=False)


def test_course_planning_run(run_env, monkeypatch):
    from fastapi.testclient import TestClient
    courses = run_env  # the fixture returns the app
    with TestClient(courses, base_url="http://test") as client:
        H = {"X-Admin-Token": "t"}
        r = client.post("/runs", headers=H, json={
            "mode": "course", "subject": "Build a toy research agent",
            "level": "intermediate", "min_parts": 2, "max_parts": 2,
            "docs_urls": ["https://langchain-ai.github.io/langgraph/"],
            "repo_name": "toy-agent", "remote_url": None, "budget_usd": 2})
        assert r.status_code == 202, r.text
        rid = r.json()["id"]

        def view():
            v = client.get(f"/runs/{rid}", headers=H).json()
            assert v["mode"] == "course"
            return v

        # -> docs map + research -> refs_review interrupt
        for _ in range(100):
            v = view()
            if v["pending"]:
                break
            time.sleep(0.05)
        assert v["pending"]["type"] == "refs", v["error"]
        assert len(v["course"]["docs"]) == 1 and len(v["course"]["refs"]) == 5

        # drop R5, keep the rest
        r2 = client.post(f"/runs/{rid}/resume", headers=H,
                         json={"keep": ["R1", "R2", "R3", "R4"], "added": [], "inspired_by": ["R1", "R2"]})
        assert r2.status_code == 202, r2.text
        for _ in range(100):
            v = view()
            if v["pending"]:
                break
            time.sleep(0.05)
        assert v["pending"]["type"] == "course_plan", v["error"]
        assert len(v["course"]["refs"]) == 4          # renumbered to R1..R4
        assert v["course"]["inspired_by"] == ["R1", "R2"]
        assert v["course"]["plan"]["parts"][0]["ref_ids"] == ["R1", "R2"]

        # request a change, get a (stub) revised plan again, then approve
        r3 = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "changes", "comments": ["shorter parts please"]})
        assert r3.status_code == 202
        for _ in range(100):
            v = view()
            if v["pending"]:
                break
            time.sleep(0.05)
        assert v["pending"]["type"] == "course_plan", v["error"]
        r4 = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "approve", "comments": []})
        assert r4.status_code == 202

        for _ in range(200):
            v = view()
            if v["status"] == "planning_done":
                break
            time.sleep(0.05)
        assert v["status"] == "planning_done", v["error"]

        # the repo exists with everything committed and tagged part-0
        repo_path = Path(v["course"]["repo"]["path"])
        assert (repo_path / "pyproject.toml").exists()
        assert "toy_agent" == v["course"]["repo"]["package"]
        out = __import__("subprocess").run(["git", "log", "--format=%s"], cwd=repo_path, capture_output=True, text=True)
        assert "part-0: scaffold the Toy Research Agent project" in out.stdout
        out2 = __import__("subprocess").run(["git", "tag"], cwd=repo_path, capture_output=True, text=True)
        assert "part-0" in out2.stdout.split()
        assert v["course"]["repo"]["remote_ok"] is False  # no remote given

        # blog default cap on a course run is the course budget (2.0)
        assert v["usage"]["budget"]["cap"] == 2.0
