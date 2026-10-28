from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=False)  # exposes OPENROUTER_API_KEY etc. to the pipeline


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_token: str = ""
    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"

    openrouter_api_key: str = ""          # OPENROUTER_API_KEY
    app_title: str = "benki-pipeline"
    models_file: Path = Path("config/models.yaml")   # task -> model routing
    blog_budget_usd: float = 1.0          # per-run cap default; overridable per run
    course_budget_usd: float = 2.0        # course runs are heavier (code model involved)
    budget_warn_at: float = 0.8

    data_dir: Path = Path("data")
    voice_file: Path = Path("voice/ben.md")
    banned_file: Path = Path("voice/banned.txt")

    site_repo_path: Path = Path("../..")   # repo root, relative to apps/pipeline where `pipeline serve` runs
    site_blog_dir: str = "apps/site/src/content/blog"
    site_roadmaps_dir: str = "apps/site/src/content/roadmaps"
    site_base_url: str = "https://benkicodes.pages.dev"
    publish_mode: str = "git"        # git | files
    git_branch: str = "main"
    git_remote: str = "origin"

    # course repos (03-prd §7.4): one git repo per course, sibling of the monorepo.
    # Relative to apps/pipeline cwd (where `pipeline serve` runs), like site_repo_path.
    courses_dir: Path = Path("../../..") / "courses"
    templates_dir: Path = Path("templates/course-repo")
    repo_cmds: list[str] = ["uv sync", "uv add", "uv run pytest", "uv run ruff check"]
    repo_cmd_timeout: float = 600.0   # pytest on a small project is fast; give sync room

    checkpoint_plan: bool = True
    max_auto_revisions: int = 1
    max_source_chars: int = 14000
    max_similarity: float = 0.18
    request_timeout: float = 15.0
    allow_private_urls: bool = False

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def worktree_dir(self) -> Path:
        """Detached publish worktree. Relative paths are anchored to the site repo root by publisher.publish_post."""
        return self.data_dir / "publish-worktree"

    @property
    def courses_root(self) -> Path:
        """Absolute COURSES_DIR (03-prd §7.4), resolved like site_repo_path from the cwd."""
        return self.courses_dir.expanduser().resolve()

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
