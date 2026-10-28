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


# ---------------------------------------------------------------- part loop mechanics
def test_start_part_branches_from_previous_tag(repo):
    repo.tag(0, "part-0")
    sha = repo.start_part(1)
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "wip/part-1"
    assert sha == repo.head()
    # existing branch is reused
    repo.start_part(1)
    with pytest.raises(RepoError, match="uncommitted"):
        (repo.root / "dirty.txt").write_text("x")
        repo.start_part(2)


def test_apply_file_edit_ops(repo):
    repo.write_file("app.py", "a = 1\nb = 2\n")
    repo.stage_and_commit("part-0: base")
    # create
    repo.apply_file_edit("new.py", "create", content="x = 1\n")
    assert (repo.root / "new.py").read_text() == "x = 1\n"
    with pytest.raises(RepoError, match="already exists"):
        repo.apply_file_edit("new.py", "create", content="x = 1\n")
    # edit: search must match exactly once
    repo.apply_file_edit("app.py", "edit", edits=[{"search": "b = 2", "replace": "b = 3"}])
    assert "b = 3" in (repo.root / "app.py").read_text()
    with pytest.raises(RepoError, match="not found"):
        repo.apply_file_edit("app.py", "edit", edits=[{"search": "zzz", "replace": "y"}])
    repo.write_file("dup.py", "same\nsame\n")
    with pytest.raises(RepoError, match="2 times"):
        repo.apply_file_edit("dup.py", "edit", edits=[{"search": "same", "replace": "x"}])
    # replace + delete
    repo.apply_file_edit("app.py", "replace", content="a = 9\n")
    assert (repo.root / "app.py").read_text() == "a = 9\n"
    repo.apply_file_edit("new.py", "delete")
    assert not (repo.root / "new.py").exists()
    with pytest.raises(RepoError, match="does not exist"):
        repo.apply_file_edit("new.py", "delete")


def test_changed_lines_and_commit_list(repo):
    repo.tag(0, "part-0")
    repo.start_part(1)
    repo.write_file("big.py", "\n".join(f"x{i} = {i}" for i in range(30)) + "\n")
    repo.stage_and_commit("part-1: add big module")
    assert repo.changed_lines() >= 30
    commits = repo.commit_list("part-0..HEAD")
    assert [c["message"] for c in commits] == ["part-1: add big module"]
    numbered = repo.files_line_numbered(["big.py", "missing.py"])
    assert "x0 = 0" in numbered["big.py"] and "missing.py" not in numbered


def test_read_head_sees_committed_state(repo):
    repo.write_file("h.txt", "committed\n")
    repo.stage_and_commit("part-0: add h")
    (repo.root / "h.txt").write_text("dirty\n")
    assert repo.read_head("h.txt") == "committed\n"
    assert repo.read_head("nope.txt") is None


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


def test_render_template_long_or_quoted_summary(tmp_path):
    """Long summaries must not break the generated repo's own lint; quotes must not break TOML."""
    tpl = Path("templates/course-repo")
    long_summary = ("A command-line todo app built step by step with Python, argparse, JSON "
                    'persistence, and pytest, with "quotes" that would break plain TOML. ' * 2).strip()
    dest = tmp_path / "out"
    render_course_template(tpl, dest, name="demo-course", project="Demo", summary=long_summary, github_owner="ben")
    init_py = (dest / "src" / "demo_course" / "__init__.py").read_text()
    assert all(len(line) <= 110 for line in init_py.splitlines())
    toml = (dest / "pyproject.toml").read_text()
    assert '\\"quotes\\"' in toml  # TOML-safe escaping
    import tomllib
    parsed = tomllib.loads(toml)
    assert 'quotes' in parsed["project"]["description"]
