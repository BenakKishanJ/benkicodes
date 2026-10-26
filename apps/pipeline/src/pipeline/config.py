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
    budget_warn_at: float = 0.8

    data_dir: Path = Path("data")
    voice_file: Path = Path("voice/ben.md")
    banned_file: Path = Path("voice/banned.txt")

    site_repo_path: Path = Path("..")
    site_blog_dir: str = "apps/site/src/content/blog"
    site_base_url: str = "https://benkicodes.pages.dev"
    publish_mode: str = "git"        # git | files
    git_branch: str = "main"
    git_remote: str = "origin"

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
        """Detached publish worktree, inside the site repo (see tools/publisher.py)."""
        return self.data_dir / "publish-worktree"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
