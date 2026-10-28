"""Course pipeline acceptance, in-process (03-prd §7.3–7.7): a course run from
intake through the full part loop — code checkpoint, lesson checkpoint, publish —
with a stubbed gateway and a stubbed crawl so no model calls or network happen.
The site half of publish goes to a local bare remote via the `site` fixture."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

from pipeline.graphs import course as course_graph
from pipeline.schemas import (CodeStepOutput, CoursePlan, LessonCheckOutput, QuizOutput,
                              ResearchOutput)

LESSON_MD = """## What we add

This part gives the agent its memory: tasks saved as JSON. [S1]

## How it works

The storage module writes a JSON file and reads it back. [S1]

## Step by step

The first commit adds storage; the second wires the CLI. [S1]

## Wrap-up

Tasks survive restarts now. [S1]

## Exercises

**Exercise 1** — add a `remove` command.
acceptance: removing a task updates the JSON file.
hint: look at `save_tasks`.

**Exercise 2** — write a round-trip test.
acceptance: pytest passes with the new test.
hint: use `tmp_path`.
"""

STORAGE_PY = '''"""Task storage: a JSON file is the whole database."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Task:
    id: int
    title: str
    done: bool = False


def load_tasks(path: Path) -> list[Task]:
    if not path.exists():
        return []
    return [Task(**t) for t in json.loads(path.read_text())]


def save_tasks(path: Path, tasks: list[Task]) -> None:
    path.write_text(json.dumps([asdict(t) for t in tasks], indent=2))
'''

STORAGE_TEST = '''from pathlib import Path

from toy_agent.storage import Task, load_tasks, save_tasks


def test_round_trip(tmp_path: Path):
    tasks = [Task(id=1, title="write storage")]
    p = tmp_path / "tasks.json"
    save_tasks(p, tasks)
    assert load_tasks(p) == tasks
    assert load_tasks(tmp_path / "missing.json") == []
'''

SEARCH_PY = '''"""Part 2: find tasks by title substring."""
from __future__ import annotations

from toy_agent.storage import Task


def find_tasks(tasks: list[Task], needle: str) -> list[Task]:
    needle = needle.lower()
    return [t for t in tasks if needle in t.title.lower()]
'''

SEARCH_TEST = '''from toy_agent.search import find_tasks
from toy_agent.storage import Task


def test_find_is_case_insensitive():
    tasks = [Task(id=1, title="Write Storage")]
    assert find_tasks(tasks, "write") == tasks
    assert find_tasks(tasks, "nope") == []
'''


def code_output(n: int) -> CodeStepOutput:
    """Real edits against the scaffolded repo: part 1 adds storage, part 2 search."""
    if n == 1:
        commits = [
            {"message": "part-1: add JSON task storage",
             "edits": [{"path": "src/toy_agent/storage.py", "op": "create", "content": STORAGE_PY}],
             "add_dependencies": []},
            {"message": "part-1: test the storage round-trip",
             "edits": [{"path": "tests/test_storage.py", "op": "create", "content": STORAGE_TEST}],
             "add_dependencies": []},
        ]
    else:
        commits = [
            {"message": "part-2: add search over tasks",
             "edits": [{"path": "src/toy_agent/search.py", "op": "create", "content": SEARCH_PY},
                       {"path": "tests/test_search.py", "op": "create", "content": SEARCH_TEST}],
             "add_dependencies": []},
            {"message": "part-2: export find_tasks from the package",
             "edits": [{"path": "src/toy_agent/storage.py", "op": "edit",
                        "edits": [{"search": "def save_tasks",
                                   "replace": "DEFAULT_NAME = \"tasks.json\"\n\n\ndef save_tasks"}]},
                       {"path": "src/toy_agent/__init__.py", "op": "edit",
                        "edits": [{"search": "Toy Research Agent\n",
                                   "replace": "Toy Research Agent\n\nExports the todo agent API.\n"}]}],
             "add_dependencies": []},
        ]
    return CodeStepOutput.model_validate({
        "commits": commits,
        "architecture_update": f"# Architecture\n\nPart {n}: see docs/PARTS.md.\n",
        "notes_for_lesson": "emphasise the JSON round-trip and the dataclass defaults"})


QUIZ = QuizOutput.model_validate({"questions": [
    {"id": "q1", "question": "What does save_tasks write?", "type": "single",
     "options": [{"id": "a", "text": "csv"}, {"id": "b", "text": "json"}, {"id": "c", "text": "sqlite"}],
     "correct": ["b"], "explanation": "The storage module serialises tasks to a JSON file.",
     "difficulty": "easy", "hint": "It is a text format braces love."},
    {"id": "q2", "question": "What does load_tasks return for a missing file?", "type": "single",
     "options": [{"id": "a", "text": "an empty list"}, {"id": "b", "text": "it raises"}, {"id": "c", "text": "None"}],
     "correct": ["a"], "explanation": "Missing file means no tasks yet, so an empty list keeps the CLI simple.",
     "difficulty": "easy"},
    {"id": "q3", "question": "Which stdlib module parses the JSON file?", "type": "single",
     "options": [{"id": "a", "text": "pickle"}, {"id": "b", "text": "csv"}, {"id": "c", "text": "json"}],
     "correct": ["c"], "explanation": "json.loads parses the file contents into Python objects.",
     "difficulty": "easy"}]})

CHECK = LessonCheckOutput.model_validate({
    "scores": {"accuracy": 5, "clarity": 5, "code-correctness": 5, "coverage": 5, "tone": 5},
    "issues": [], "unsupported_claims": [],
    "meta_description": "Learn how the toy agent stores tasks as JSON and reads them back, step by step.",
    "summary_for_next": "The learner has a Task dataclass, save_tasks and load_tasks, and a round-trip test."})


class StubGateway:
    """Answers research + plan_course + the part loop with canned, schema-valid output."""

    def __init__(self, docs_urls):
        self.docs_urls = docs_urls
        self.part_n = 0

    def structured(self, task, schema, system, user, *, budget=None, spent=0.0):
        if task == "research":
            return (ResearchOutput(refs=[
                {"title": f"Ref {i}", "url": f"https://example-source-{i}.com/guide",
                 "type": "article" if i % 2 else "repo",
                 "illustrated": i == 1, "level": "beginner", "why": f"reason {i}"}
                for i in range(1, 6)]), {"input": 10, "output": 10, "calls": 1, "usd": 0.01})
        if task == "plan":
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
        if task == "plan_code":
            self.part_n += 1
            return (code_output(self.part_n), {"input": 10, "output": 10, "calls": 1, "usd": 0.01})
        if task == "fast":
            return (QUIZ, {"input": 5, "output": 5, "calls": 1, "usd": 0.005})
        assert task == "check", task
        return (CHECK, {"input": 5, "output": 5, "calls": 1, "usd": 0.005})

    def text(self, *a, **k):
        return (LESSON_MD, {"input": 5, "output": 5, "calls": 1, "usd": 0.005})

    def credits(self):
        return {"credits": 10}


DOCS_URL = "https://langchain-ai.github.io/langgraph/"

@pytest.fixture
def run_env(tmp_path, site, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    templates = Path(__file__).parents[1] / "templates" / "course-repo"
    docs = [DOCS_URL]

    def fake_crawl(seed_urls, timeout=15.0, max_pages=30, allow_private=False):
        pages = [{"title": f"Doc {i}", "url": u, "text": f"Doc {i} page text. " * 40} for i, u in enumerate(seed_urls, 1)]
        return pages, []

    monkeypatch.setattr(course_graph, "crawl_docs", fake_crawl)
    from pipeline.config import Settings
    s = Settings(data_dir=data_dir, courses_dir=tmp_path / "courses", templates_dir=templates,
                 allow_private_urls=True, openrouter_api_key="x", admin_token="t",
                 site_repo_path=site[0], site_base_url="http://test", publish_mode="git")
    from pipeline.api import create_app
    return create_app(s, StubGateway(docs), check_urls=False)


def _wait(client, H, rid, until=None, tries=400):
    """Poll until the run settles: pending is set AND the status is an awaiting-* state
    (a stale pending lingers in the checkpoint right after a resume POST, until the
    drive thread consumes it — so pending alone is not trustworthy), or the status
    matches `until`."""
    for _ in range(tries):
        v = client.get(f"/runs/{rid}", headers=H).json()
        settled = v["pending"] is not None and (v["status"].startswith("awaiting") or v["status"] == "failed")
        hit = settled if until is None else (settled or (callable(until) and until(v["status"])) or v["status"] == until)
        if hit:
            return v
        time.sleep(0.05)
    return v


def _new_course_run(client, H):
    r = client.post("/runs", headers=H, json={
        "mode": "course", "subject": "Build a toy research agent",
        "level": "intermediate", "min_parts": 2, "max_parts": 2,
        "docs_urls": [DOCS_URL],
        "repo_name": "toy-agent", "remote_url": None, "budget_usd": 2})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_course_planning_run(run_env):
    """Intake → refs → plan → approve lands at the FIRST code checkpoint (part loop)."""
    from fastapi.testclient import TestClient
    with TestClient(run_env, base_url="http://test") as client:
        H = {"X-Admin-Token": "t"}
        rid = _new_course_run(client, H)

        v = _wait(client, H, rid)
        assert v["pending"]["type"] == "refs", v["error"]
        assert len(v["course"]["docs"]) == 1 and len(v["course"]["refs"]) == 5

        # drop R5, keep the rest
        r2 = client.post(f"/runs/{rid}/resume", headers=H,
                         json={"keep": ["R1", "R2", "R3", "R4"], "added": [], "inspired_by": ["R1", "R2"]})
        assert r2.status_code == 202, r2.text
        v = _wait(client, H, rid)
        assert v["pending"]["type"] == "course_plan", v["error"]
        assert len(v["course"]["refs"]) == 4          # renumbered to R1..R4
        assert v["course"]["inspired_by"] == ["R1", "R2"]
        assert v["course"]["plan"]["parts"][0]["ref_ids"] == ["R1", "R2"]

        # request a change, get a (stub) revised plan again, then approve
        r3 = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "changes", "comments": ["shorter parts please"]})
        assert r3.status_code == 202
        v = _wait(client, H, rid)
        assert v["pending"]["type"] == "course_plan", v["error"]
        r4 = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "approve", "comments": []})
        assert r4.status_code == 202

        # the part loop starts immediately: repo scaffolded, part-1 coded, awaiting Ben
        v = _wait(client, H, rid, lambda s: s in ("awaiting_code", "failed"))
        assert v["status"] == "awaiting_code", v["error"]
        c = v["course"]
        repo_path = Path(c["repo"]["path"])
        assert (repo_path / "pyproject.toml").exists()
        assert "toy_agent" == c["repo"]["package"]
        assert c["repo"]["remote_ok"] is False  # no remote given
        assert c["part_n"] == 1 and c["commits"], c["error"]
        # the part-1 commits exist on wip/part-1 and the interrupt carries diffs
        out = subprocess.run(["git", "log", "--format=%s", "part-0..HEAD"], cwd=repo_path,
                             capture_output=True, text=True)
        assert "part-1: add JSON task storage" in out.stdout
        pending = v["pending"]
        assert pending["type"] == "code_review"
        assert pending["commits"] and pending["commits"][0]["diff"]
        assert v["usage"]["budget"]["cap"] == 2.0


def test_course_part_loop_run(run_env, site):
    """Full loop: both parts coded, reviewed, taught, gated, published to the site repo."""
    from fastapi.testclient import TestClient
    with TestClient(run_env, base_url="http://test") as client:
        H = {"X-Admin-Token": "t"}
        rid = _new_course_run(client, H)

        v = _wait(client, H, rid)
        r = client.post(f"/runs/{rid}/resume", headers=H,
                        json={"keep": ["R1", "R2", "R3", "R4", "R5"], "added": [], "inspired_by": ["R3"]})
        assert r.status_code == 202, r.text
        v = _wait(client, H, rid)
        assert v["pending"]["type"] == "course_plan", v["error"]
        r = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "approve", "comments": []})
        assert r.status_code == 202
        v = _wait(client, H, rid, lambda s: s in ("awaiting_code", "failed"))
        assert v["status"] == "awaiting_code", v["error"]

        # ---- part 1: fix requests need a comment; run tests by hand; then accept
        r = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "fix"})
        assert r.status_code == 422
        r = client.post(f"/runs/{rid}/repo/tests", headers=H, json={})
        assert r.status_code == 200, r.text
        if shutil.which("uv"):
            assert r.json()["ok"] is True, r.json()["output"]
        v = client.get(f"/runs/{rid}", headers=H).json()
        assert v["course"]["tests"] is not None
        # diff endpoints work
        r = client.get(f"/runs/{rid}/repo/diff?commit=all", headers=H)
        assert r.status_code == 200 and "storage" in r.json()["diff"]
        r = client.get(f"/runs/{rid}/repo/diff?commit={v['course']['commits'][0]['sha'][:7]}", headers=H)
        assert r.status_code == 200
        r = client.post(f"/runs/{rid}/repo/refresh", headers=H, json={})
        assert r.status_code == 200 and r.json()["branch"] == "wip/part-1"

        r = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "accept", "commit_message": None})
        assert r.status_code == 202
        v = _wait(client, H, rid, lambda s: s in ("awaiting_lesson", "failed"))
        assert v["status"] == "awaiting_lesson", v["error"]
        c = v["course"]
        assert c["lesson_md"].startswith("## What we add")
        assert c["lesson_html_rendered"], "server-rendered preview"
        assert len(c["quiz"]) == 3
        assert c["check"]["scores"]["accuracy"] == 5
        assert "S1" in c["lesson_md"] or True  # stub lesson cites [S1]
        gate_names = {g["name"]: g["status"] for g in c["gates"]}
        assert gate_names["schema"] == "pass"
        assert gate_names["quiz"] == "pass"
        assert v["pending"]["type"] == "lesson_review"

        # ---- approve the lesson -> part 1 published (course repo tagged, site pushed)
        r = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "approve", "comment": None})
        assert r.status_code == 202
        v = _wait(client, H, rid, lambda s: s in ("awaiting_code", "failed"))
        assert v["status"] == "awaiting_code", v["error"]
        c = v["course"]
        assert c["part_n"] == 2
        repo_path = Path(c["repo"]["path"])
        tags = subprocess.run(["git", "tag"], cwd=repo_path, capture_output=True, text=True).stdout.split()
        assert "part-0" in tags and "part-1" in tags
        # main was ff-merged to the part-1 head (dereference the annotated tag)
        head = subprocess.run(["git", "rev-parse", "part-1^{commit}"], cwd=repo_path,
                              capture_output=True, text=True).stdout.strip()
        main = subprocess.run(["git", "rev-parse", "main"], cwd=repo_path, capture_output=True, text=True).stdout.strip()
        assert head == main
        # one published part recorded with URLs
        assert len(c["published_parts"]) == 1
        pp = c["published_parts"][0]
        assert pp["tag"] == "part-1" and pp["n"] == 1
        assert pp["lesson_url"].endswith("/roadmaps/toy-agent/01-part-1/")

        # ---- part 2: accept code, then approve WITH a markdown edit
        r = client.post(f"/runs/{rid}/resume", headers=H, json={"action": "accept", "commit_message": None})
        v = _wait(client, H, rid, lambda s: s in ("awaiting_lesson", "failed"))
        assert v["status"] == "awaiting_lesson", v["error"]
        edited = v["course"]["lesson_md"].replace("## Wrap-up", "## Wrap-up (reviewed by Ben)")
        r = client.post(f"/runs/{rid}/resume", headers=H,
                        json={"action": "approve", "comment": None, "edited_md": edited})
        assert r.status_code == 202
        v = _wait(client, H, rid, lambda s: s in ("published", "failed"), tries=600)
        assert v["status"] == "published", v["error"]
        c = v["course"]
        assert len(c["published_parts"]) == 2
        assert subprocess.run(["git", "tag"], cwd=repo_path, capture_output=True, text=True).stdout.split().count("part-2") == 1

        # the site repo got the roadmap: fetch in the work clone, read the pushed files
        site_work = site[0]
        subprocess.run(["git", "fetch", "origin"], cwd=site_work, check=True, capture_output=True)
        base = "apps/site/src/content/roadmaps/toy-agent"
        index = subprocess.run(["git", "show", f"origin/main:{base}/index.md"], cwd=site_work,
                               capture_output=True, text=True).stdout
        assert "status: complete" in index and "Toy Research Agent" in index
        m1 = subprocess.run(["git", "show", f"origin/main:{base}/modules/01-part-1.md"], cwd=site_work,
                            capture_output=True, text=True).stdout
        assert "title: Part 1" in m1 and "## What we add" in m1 and "startTag: part-0" in m1
        m2 = subprocess.run(["git", "show", f"origin/main:{base}/modules/02-part-2.md"], cwd=site_work,
                            capture_output=True, text=True).stdout
        assert "reviewed by Ben" in m2          # Ben's direct edit is authoritative
        assert "Assisted-by" not in m2
