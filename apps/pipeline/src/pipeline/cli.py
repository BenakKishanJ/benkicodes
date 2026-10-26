from __future__ import annotations

import secrets
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="BenKi content pipeline")


def _ensure_token(env: Path) -> str:
    from .config import get_settings
    s = get_settings()
    if s.admin_token:
        return s.admin_token
    token = secrets.token_urlsafe(24)
    text = env.read_text() if env.exists() else ""
    if "ADMIN_TOKEN=" in text:
        lines = [f"ADMIN_TOKEN={token}" if l.startswith("ADMIN_TOKEN=") else l for l in text.splitlines()]
        env.write_text("\n".join(lines) + "\n")
    else:
        env.write_text(text + ("\n" if text and not text.endswith("\n") else "") + f"ADMIN_TOKEN={token}\n")
    get_settings.cache_clear()
    return token


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8787, reload: bool = False):
    """Run the local API. The admin page (http://localhost:4321/admin/) talks to it."""
    import uvicorn
    token = _ensure_token(Path(".env"))
    typer.echo(f"\n  API:    http://{host}:{port}\n  Token:  {token}   (paste it into the admin page the first time)\n")
    uvicorn.run("pipeline.api:create_app", factory=True, host=host, port=port, reload=reload)


@app.command()
def token():
    """Print (and create, if missing) the admin token."""
    typer.echo(_ensure_token(Path(".env")))


if __name__ == "__main__":
    app()
