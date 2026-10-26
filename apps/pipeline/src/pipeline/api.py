"""Local HTTP API for the admin page. Single user, token-protected, CORS limited to the local site."""
from __future__ import annotations

import difflib
import json
import re
import secrets
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from markdown_it import MarkdownIt
from pydantic import ValidationError

from .config import Settings, get_settings
from .gateway.budget import BudgetPause
from .gateway.client import Gateway, get_gateway
from .gateway.models import price_mtok
from .graphs.blog import build_blog_graph
from .schemas import Decision, PlanDecision, RunRequest
from .store import RunStore

TERMINAL = {"published", "rejected", "failed"}
_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")  # raw HTML disabled: LLM output is untrusted


def create_app(settings: Settings | None = None, gw: Gateway | None = None, check_urls: bool = True) -> FastAPI:
    s = settings or get_settings()
    s.ensure_dirs()
    gateway = gw or get_gateway(s)
    graph = build_blog_graph(gateway, s, SqliteSaver(sqlite3.connect(s.data_dir / "checkpoints.db", check_same_thread=False)), check_urls)
    store = RunStore(s.data_dir / "runs.db")
    pool = ThreadPoolExecutor(max_workers=2)
    running: set[str] = set()
    lock = threading.Lock()

    app = FastAPI(title="BenKi content pipeline", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["X-Admin-Token", "Content-Type"])

    def auth(x_admin_token: str = Header(default="")):
        if not s.admin_token or not secrets.compare_digest(x_admin_token, s.admin_token):
            raise HTTPException(401, "bad or missing X-Admin-Token")

    cfg = lambda rid: {"configurable": {"thread_id": rid}}

    # ---------------------------------------------------------------- running graphs in the background
    def drive(rid: str, payload: Any) -> None:
        with lock:
            running.add(rid)
        try:
            graph.invoke(payload, cfg(rid))
            store.update(rid, error=None)
        except BudgetPause:
            store.update(rid, status="paused_budget", error=None)
        except Exception as e:  # noqa: BLE001 any failure shows in the run list
            store.update(rid, error=f"{type(e).__name__}: {e}"[:800])
        finally:
            with lock:
                running.discard(rid)
            store.update(rid, status=status_of(rid))  # keeps paused_budget intact (status_of handles it)

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
            return "working" if st in (None, "awaiting_plan", "awaiting_review") else st
        p = pending_of(snap)
        if p:
            return "awaiting_plan" if p.get("type") == "plan" else "awaiting_review"
        if row.get("status") == "paused_budget":
            return "paused_budget"
        if row.get("error"):
            return "failed"
        return (snap.values or {}).get("status", "queued")

    def usage_view(rid: str, u: dict) -> dict:
        row = store.get(rid) or {}
        cap = row.get("budget_cap") or s.blog_budget_usd
        spent = float(u.get("usd", 0.0))
        return {**u, "budget": {"cap": cap, "spent": round(spent, 4),
                                "warn": spent >= s.budget_warn_at * cap, "pause_exhausted": spent >= cap}}

    def view(rid: str) -> dict:
        row = store.get(rid)
        if not row:
            raise HTTPException(404, "run not found")
        snap = graph.get_state(cfg(rid))
        v = snap.values or {}   # right after creation there is no checkpoint yet
        draft = v.get("draft_md", "")
        prev = v.get("prev_draft")
        diff = "\n".join(difflib.unified_diff(prev.splitlines(), draft.splitlines(), "previous", "current", lineterm="", n=2)) if prev else ""
        check = v.get("check", {})
        return {
            "id": rid, "topic": row["topic"], "status": status_of(rid), "error": row.get("error"),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "pending": pending_of(snap),
            "events": v.get("events", []),
            "sources": [{**{k: x[k] for k in ("id", "kind", "title", "url", "trust", "flags", "chars")},
                         "excerpt": x["text"][:600]} for x in v.get("sources", [])],
            "plan": v.get("plan"), "plan_feedback": v.get("plan_feedback", []),
            "draft_md": draft, "draft_html": _md.render(draft) if draft else "", "diff": diff,
            "check": check if (check.get("scores") or check.get("seo")) else None,
            "gates": v.get("gates", []), "seo": (check or {}).get("seo"),
            "revision_count": v.get("revision_count", 0), "human_rounds": v.get("human_rounds", 0),
            "review_note": v.get("review_note", ""), "published": v.get("published"),
            "usage": usage_view(rid, v.get("usage", {})),
            "calls": list(reversed(v.get("calls", [])))[:12],
        }

    # ---------------------------------------------------------------- routes
    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/settings", dependencies=[Depends(auth)])
    def settings():
        tasks = {t: {k: v.get(k) for k in ("model", "fallbacks", "purpose")} for t, v in gateway.tasks.items()}
        return {"tasks": tasks, "publish_mode": s.publish_mode, "branch": s.git_branch,
                "checkpoint_plan": s.checkpoint_plan, "site_base_url": s.site_base_url,
                "default_budget_usd": s.blog_budget_usd,
                "api_key_configured": bool(s.openrouter_api_key)}

    @app.get("/credits", dependencies=[Depends(auth)])
    def credits():
        try:
            return gateway.credits()
        except Exception as e:
            raise HTTPException(502, f"credit lookup failed: {e}") from e

    @app.get("/models", dependencies=[Depends(auth)])
    def models(q: str = "", limit: int = 50, free: bool = False, structured: bool = False):
        cat = gateway.catalog()
        if not cat:
            raise HTTPException(503, "model catalog unavailable (offline?)")
        items = []
        for mid, m in cat.items():
            if q and q.lower() not in f'{mid} {m.get("name", "")}'.lower():
                continue
            if free and m.get("pricing", {}).get("prompt") not in ("0", "0.0", None) and m.get("pricing", {}).get("completion") not in ("0", "0.0", None):
                continue
            if structured and "structured_outputs" not in (m.get("supported_parameters") or []):
                continue
            inp, out = price_mtok(cat, mid)      # unknown ids price 0.0 (models.py swallows bad data)
            items.append({"id": mid, "name": m.get("name"), "context_length": m.get("context_length"),
                          "in_per_mtok": inp, "out_per_mtok": out,
                          "structured": "structured_outputs" in (m.get("supported_parameters") or [])})
        items.sort(key=lambda x: (x["out_per_mtok"], x["id"]))
        return items[: max(1, min(limit, 200))]

    @app.post("/models/{mid:path}/smoke", dependencies=[Depends(auth)])
    def smoke(mid: str):
        from langchain_openrouter import ChatOpenRouter
        t0 = time.monotonic()
        try:
            chat = ChatOpenRouter(model=mid, api_key=s.openrouter_api_key or None, temperature=0,
                                  timeout=30_000, max_retries=0, app_title=f"{s.app_title}-smoke")
            out = chat.invoke("Reply with exactly: OK")
            text = out.content if isinstance(out.content, str) else str(out.content)
        except Exception as e:
            raise HTTPException(502, f"{mid} smoke test failed: {e}") from e
        return {"id": mid, "ok": True, "latency_ms": int((time.monotonic() - t0) * 1000),
                "answer": text[:80], "usage": getattr(out, "usage_metadata", None)}

    @app.post("/runs", dependencies=[Depends(auth)], status_code=202)
    def create_run(req: RunRequest):
        rid = uuid.uuid4().hex[:10]
        store.create(rid, req.topic, budget_cap=req.budget_usd or s.blog_budget_usd)
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

    @app.get("/runs/{rid}/stream", dependencies=[Depends(auth)])
    def stream(rid: str) -> StreamingResponse:
        def gen() -> Iterator[str]:
            sent_n, last_status = 0, None
            while True:
                try:
                    v = view(rid)
                except HTTPException:
                    yield "event: gone\ndata: {}\n\n"
                    return
                fresh = v["events"][sent_n:]      # events only ever append
                sent_n = len(v["events"])
                msg = json.dumps({"status": v["status"], "events": fresh,
                                  "spent": v["usage"].get("usd", 0),
                                  "pending": (v["pending"] or {}).get("type")})
                yield f"data: {msg}\n\n"
                if v["status"] != last_status:
                    yield f"event: transition\ndata: {json.dumps({'status': v['status']})}\n\n"
                    last_status = v["status"]
                if v["status"] in TERMINAL:
                    yield "event: done\ndata: {}\n\n"
                    return
                time.sleep(1.2)
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/runs/{rid}/resume", dependencies=[Depends(auth)], status_code=202)
    def resume(rid: str, body: dict):
        if rid in running:
            raise HTTPException(409, "run is busy")
        p = pending_of(graph.get_state(cfg(rid)))
        if not p:
            raise HTTPException(409, "run is not waiting for input")
        try:
            decision = (PlanDecision if p.get("type") == "plan" else Decision).model_validate(body)
        except ValidationError as e:
            raise HTTPException(422, e.errors()[0]["msg"]) from e
        with lock:
            running.add(rid)
        pool.submit(drive, rid, Command(resume=decision.model_dump()))
        return {"ok": True}

    @app.post("/runs/{rid}/budget", dependencies=[Depends(auth)])
    def set_budget(rid: str, body: dict):
        """Raise the per-run cap (or just set it); auto-resumes a paused_budget run."""
        row = store.get(rid)
        if not row:
            raise HTTPException(404, "run not found")
        if rid in running:
            raise HTTPException(409, "run is busy")
        try:
            cap = float(body["budget_usd"])
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(422, "budget_usd (number) required") from e
        spent = float((graph.get_state(cfg(rid)).values or {}).get("usage", {}).get("usd", 0.0))
        if cap <= spent:
            raise HTTPException(422, f"new cap must exceed the ${spent:.2f} already spent")
        graph.update_state(cfg(rid), {"budget_usd": cap})
        store.update(rid, budget_cap=cap, error=None)
        resumed = row.get("status") == "paused_budget" or row.get("error")
        if resumed:
            with lock:
                running.add(rid)
            pool.submit(drive, rid, None)  # continue from the last checkpoint
        return {"ok": True, "resumed": bool(resumed), "budget_usd": cap}

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

    @app.get("/library", dependencies=[Depends(auth)])
    def library():
        """Posts that exist in the site repo's blog dir (drafts and published alike)."""
        from pathlib import Path

        import yaml
        blog = Path(s.site_repo_path).expanduser().resolve() / s.site_blog_dir
        if not blog.exists():
            return []
        out = []
        for p in sorted(blog.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            meta = yaml.safe_load(m.group(1)) if m else {}
            if not isinstance(meta, dict):
                meta = {}
            out.append({"file": p.name, "slug": p.stem, "title": meta.get("title", p.stem),
                        "description": meta.get("description", ""), "draft": bool(meta.get("draft")),
                        "pubDate": str(meta.get("pubDate", "")), "category": meta.get("category"), "tags": meta.get("tags", [])})
        out.sort(key=lambda x: x["pubDate"], reverse=True)
        return out

    @app.delete("/runs/{rid}", dependencies=[Depends(auth)])
    def delete_run(rid: str):
        if rid in running:
            raise HTTPException(409, "run is busy")
        store.delete(rid)
        with suppress(Exception):   # checkpointer may not expose delete_thread
            graph.checkpointer.delete_thread(rid)  # type: ignore[union-attr]
        return {"ok": True}

    return app
