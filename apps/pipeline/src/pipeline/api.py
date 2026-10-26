"""Local HTTP API for the admin page. Single user, token-protected, CORS limited to the local site."""
from __future__ import annotations
import difflib, secrets, sqlite3, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from markdown_it import MarkdownIt
from pydantic import ValidationError

from .config import Settings, get_settings
from .graphs.blog import build_blog_graph
from .llm import LLM, get_llm
from .schemas import Decision, OutlineDecision, RunRequest
from .store import RunStore

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")  # raw HTML disabled: LLM output is untrusted


def create_app(settings: Settings | None = None, llm: LLM | None = None, check_urls: bool = True) -> FastAPI:
    s = settings or get_settings()
    s.ensure_dirs()
    graph = build_blog_graph(llm or get_llm(s), s, SqliteSaver(sqlite3.connect(s.data_dir / "checkpoints.db", check_same_thread=False)), check_urls)
    store = RunStore(s.data_dir / "runs.db")
    pool = ThreadPoolExecutor(max_workers=2)
    running: set[str] = set()
    lock = threading.Lock()

    app = FastAPI(title="BenKi content pipeline", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST", "DELETE"], allow_headers=["X-Admin-Token", "Content-Type"])

    def auth(x_admin_token: str = Header(default="")):
        if not s.admin_token or not secrets.compare_digest(x_admin_token, s.admin_token):
            raise HTTPException(401, "bad or missing X-Admin-Token")

    cfg = lambda rid: {"configurable": {"thread_id": rid}}  # noqa: E731

    # ---------------------------------------------------------------- running graphs in the background
    def drive(rid: str, payload: Any) -> None:
        with lock:
            running.add(rid)
        try:
            graph.invoke(payload, cfg(rid))
            store.update(rid, error=None)
        except Exception as e:  # noqa: BLE001
            store.update(rid, error=f"{type(e).__name__}: {e}"[:800])
        finally:
            with lock:
                running.discard(rid)
            store.update(rid, status=status_of(rid))

    def pending_of(snap) -> dict | None:
        for t in snap.tasks:
            for i in t.interrupts:
                return i.value
        return None

    def status_of(rid: str) -> str:
        snap = graph.get_state(cfg(rid))
        row = store.get(rid) or {}
        if rid in running:
            st = (snap.values or {}).get("status")
            return "working" if st in (None, "awaiting_outline", "awaiting_review") else st
        p = pending_of(snap)
        if p:
            return "awaiting_outline" if p.get("type") == "outline" else "awaiting_review"
        if row.get("error"):
            return "failed"
        return (snap.values or {}).get("status", "queued")

    def usage_view(u: dict) -> dict:
        cost = (u.get("input", 0) * s.price_per_mtok_in + u.get("output", 0) * s.price_per_mtok_out) / 1e6
        return {**u, "estimated_usd": round(cost, 4) if cost else None}

    def view(rid: str) -> dict:
        row = store.get(rid)
        snap = graph.get_state(cfg(rid))
        if not row:
            raise HTTPException(404, "run not found")
        v = snap.values or {}   # right after creation there is no checkpoint yet
        draft = v.get("draft_md", "")
        prev = v.get("prev_draft")
        diff = "\n".join(difflib.unified_diff(prev.splitlines(), draft.splitlines(), "previous", "current", lineterm="", n=2)) if prev else ""
        return {
            "id": rid, "topic": row["topic"], "status": status_of(rid), "error": row.get("error"),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "pending": pending_of(snap),
            "events": v.get("events", []),
            "sources": [{**{k: x[k] for k in ("id", "kind", "title", "url", "summary", "trust", "flags", "chars")}, "excerpt": x["text"][:600]} for x in v.get("sources", [])],
            "claims": v.get("claims", []), "outline": v.get("outline"),
            "draft_md": draft, "draft_html": _md.render(draft) if draft else "", "diff": diff,
            "critique": v.get("critique"), "gates": v.get("gates", []), "seo": v.get("seo"),
            "revision_count": v.get("revision_count", 0), "human_rounds": v.get("human_rounds", 0),
            "review_note": v.get("review_note", ""), "published": v.get("published"),
            "usage": usage_view(v.get("usage", {})),
        }

    # ---------------------------------------------------------------- routes
    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/config", dependencies=[Depends(auth)])
    def config():
        return {"provider": s.llm_provider, "models": {"fast": s.model_fast, "strong": s.model_strong, "critic": s.model_critic},
                "publish_mode": s.publish_mode, "branch": s.git_branch, "checkpoint_outline": s.checkpoint_outline,
                "site_base_url": s.site_base_url}

    @app.post("/runs", dependencies=[Depends(auth)], status_code=202)
    def create_run(req: RunRequest):
        rid = uuid.uuid4().hex[:10]
        store.create(rid, req.topic)
        with lock:
            running.add(rid)
        pool.submit(drive, rid, {"run_id": rid, "mode": "blog", "inputs": req.model_dump()})
        return {"id": rid}

    @app.get("/runs", dependencies=[Depends(auth)])
    def list_runs():
        return [{**r, "status": status_of(r["id"])} for r in store.list()]

    @app.get("/runs/{rid}", dependencies=[Depends(auth)])
    def get_run(rid: str):
        return view(rid)

    @app.post("/runs/{rid}/resume", dependencies=[Depends(auth)], status_code=202)
    def resume(rid: str, body: dict):
        if rid in running:
            raise HTTPException(409, "run is busy")
        p = pending_of(graph.get_state(cfg(rid)))
        if not p:
            raise HTTPException(409, "run is not waiting for input")
        try:
            decision = (OutlineDecision if p.get("type") == "outline" else Decision).model_validate(body)
        except ValidationError as e:
            raise HTTPException(422, e.errors()[0]["msg"]) from e
        with lock:
            running.add(rid)
        pool.submit(drive, rid, Command(resume=decision.model_dump()))
        return {"ok": True}

    @app.post("/runs/{rid}/retry", dependencies=[Depends(auth)], status_code=202)
    def retry(rid: str):
        row = store.get(rid)
        if not row or not row.get("error"):
            raise HTTPException(409, "nothing to retry")
        if rid in running:
            raise HTTPException(409, "run is busy")
        store.update(rid, error=None)
        with lock:
            running.add(rid)
        pool.submit(drive, rid, None)  # continue from the last checkpoint
        return {"ok": True}

    @app.delete("/runs/{rid}", dependencies=[Depends(auth)])
    def delete_run(rid: str):
        if rid in running:
            raise HTTPException(409, "run is busy")
        store.delete(rid)
        try:
            graph.checkpointer.delete_thread(rid)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}

    return app
