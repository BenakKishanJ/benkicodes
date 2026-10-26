import os
import sqlite3
import subprocess

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from pipeline.config import Settings

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, env=GIT_ENV)


@pytest.fixture(autouse=True)
def _git_env(monkeypatch):
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, GIT_ENV[k])


@pytest.fixture
def site(tmp_path):
    remote, work = tmp_path / "remote.git", tmp_path / "site"
    git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    git(tmp_path, "clone", str(remote), str(work))
    (work / "apps/site/src/content/blog").mkdir(parents=True)
    (work / "apps/site/src/content/blog/.gitkeep").write_text("")
    git(work, "checkout", "-b", "main")
    git(work, "add", "."); git(work, "commit", "-m", "init"); git(work, "push", "-u", "origin", "main")
    return work, remote


@pytest.fixture
def settings(tmp_path, site):
    voice = tmp_path / "voice.md"; voice.write_text("be direct")
    banned = tmp_path / "banned.txt"; banned.write_text("game-changer\n")
    return Settings(_env_file=None, admin_token="tok", data_dir=tmp_path / "data", voice_file=voice, banned_file=banned,
                    site_repo_path=site[0], site_base_url="http://test", publish_mode="git", git_branch="main",
                    openrouter_api_key="", checkpoint_plan=True)


@pytest.fixture
def saver():
    return SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
