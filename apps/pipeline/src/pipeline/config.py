from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=False)  # exposes GOOGLE_API_KEY etc. to the LangChain provider packages


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_token: str = ""
    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"

    llm_provider: str = "google_genai"
    model_fast: str = "gemini-3.1-flash-lite"
    model_strong: str = "gemini-3.5-flash"
    model_critic: str = "gemini-3.5-flash"
    price_per_mtok_in: float = 0.0   # optional, only used to show an estimated cost
    price_per_mtok_out: float = 0.0

    data_dir: Path = Path("data")
    voice_file: Path = Path("voice/ben.md")
    banned_file: Path = Path("voice/banned.txt")

    site_repo_path: Path = Path("..")
    site_blog_dir: str = "apps/site/src/content/blog"
    site_base_url: str = "https://benkicodes.pages.dev"
    publish_mode: str = "git"        # git | files
    git_branch: str = "main"
    git_remote: str = "origin"

    checkpoint_outline: bool = True
    max_auto_revisions: int = 2
    max_source_chars: int = 14000
    max_similarity: float = 0.18
    request_timeout: float = 15.0
    allow_private_urls: bool = False

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
