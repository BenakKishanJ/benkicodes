"""tests for tools/repo.py (path safety, allowlist, secrets, tags) and tools/scaffold.py."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pipeline.tools.repo import CourseRepo, RepoError, doctor, repo_dir, secrets_scan
from pipeline.tools.scaffold import package_name, render_course_template


def _init_repo(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(p)], capture_output=True, check=True)
    (p / "README.md").write_text("# t\n")
    repo = CourseRepo(p)
    repo.stage_and_commit("init")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "demo-course"
    _init_repo(r)
    return CourseRepo(r)


# ---------------------------------------------------------------- path safety
def test_resolve_inside_only(repo):
    assert repo.resolve("src/app.py") == repo.root / "src" / "app.py"
    with pytest.raises(RepoError, match="escapes"):
        repo.resolve("../outside.py")
    with pytest.raises(RepoError, match="escapes"):
        repo.resolve("/etc/hosts")
    with pytest.raises(RepoError, match=".git"):
        repo.resolve(".git/config")
    with pytest.raises(RepoError, match=".git"):
        repo.resolve("sub/../.git/HEAD")


# ---------------------------------------------------------------- allowlist
def test_run_refuses_non_allowlisted(repo):
    with pytest.raises(RepoError, match="allowlist"):
        repo.run(["curl", "https://example.com"])
    with pytest.raises(RepoError):
        repo.run([])


def test_scrubbed_env_drops_keys():
    import pipeline.tools.repo as rp
    import os
    os.environ["BENKI_TEST_SECRET"] = "1"
    env = rp.scrubbed_env()
    assert "BENKI_TEST_SECRET" not in env
    assert "PATH" in env


# ---------------------------------------------------------------- secrets
def test_secrets_scan():
    assert secrets_scan("hello") == []
    hits = secrets_scan('sk-abcdefghtabcdefghabcdefgh\napi_key = "supersecretvalue123"')
    assert len(hits) >= 2
    assert secrets_scan("TOKENS = ['safe']") == []


def test_commit_blocked_on_secrets(repo):
    (repo.root / "leak.py").write_text("KEY = 'sk-abcdefghabcdefghabcdefgh'\n")
    with pytest.raises(RepoError, match="secret"):
        repo.stage_and_commit("oops", paths=["leak.py"])
    # nothing left staged
    assert repo.git("diff", "--staged").stdout == ""


def test_commit_adds_trailer(repo):
    (repo.root / "f.py").write_text("x = 1\n")
    sha = repo.stage_and_commit("part-1: first change", paths=["f.py"])
    msg = repo.git("log", "-1", "--format=%B").stdout
    assert sha == repo.head()
    assert "Assisted-by: content-pipeline" in msg


# ---------------------------------------------------------------- tags
def test_tag_order_enforced(repo):
    (repo.root / "g.py").write_text("y = 2\n")
    repo.stage_and_commit("part-1: change", paths=["g.py"])
    with pytest.raises(RepoError, match="part-1"):   # tag(2) needs part-1 first, not part-0
        repo.tag(2)
    repo.tag(0, msg := "part-0")
    repo.tag(1, "part-1")
    tags = repo.git("tag").stdout.split()
    assert "part-0" in tags and "part-1" in tags


# ---------------------------------------------------------------- doctor / repo_dir
def test_repo_dir_rules():
    assert repo_dir(Path("/tmp/courses"), "langgraph-deep-research") == Path("/tmp/courses/langgraph-deep-research")
    with pytest.raises(RepoError):
        repo_dir(Path("/tmp/courses"), "../escape")
    with pytest.raises(RepoError):
        repo_dir(Path("/tmp/courses"), "name.git")


def test_doctor_on_local_repo(tmp_path):
    r = tmp_path / "doc-check"
    _init_repo(r)
    out = doctor(r)
    assert out["branch_ok"] is True  # local checks still work without a remote
    assert out["empty_ok"] is False  # ls-remote without a remote fails


# ---------------------------------------------------------------- scaffold
def test_render_template(tmp_path):
    tpl = Path("templates/course-repo")
    dest = tmp_path / "out"
    n, pkg = render_course_template(tpl, dest, name="demo-course",
                                    project="Deep Research Agent", summary="You will build it", github_owner="ben")
    assert n >= 8 and pkg == package_name("demo-course") == "demo_course"
    toml = (dest / "pyproject.toml").read_text()
    assert 'name = "demo_course"' in toml and "__PKG__" not in toml
    readme = (dest / "README.md").read_text()
    assert "demo-course" in readme and "__NAME__" not in readme
    assert (dest / "src" / "demo_course" / "__init__.py").exists()
    with pytest.raises(FileExistsError):
        render_course_template(tpl, dest, name="demo-course", project="x", summary="y")
