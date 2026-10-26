from __future__ import annotations
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict


def merge_usage(a: dict | None, b: dict | None) -> dict:
    a, b = a or {}, b or {}
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in ("input", "output", "calls")}


class BlogState(TypedDict, total=False):
    run_id: str
    mode: str
    inputs: dict[str, Any]            # the validated RunRequest as a dict
    status: str
    sources: list[dict]               # {id, kind, title, url, text, summary, trust, flags, chars}
    claims: list[dict]
    outline: dict
    outline_feedback: list[str]
    draft_md: str
    prev_draft: str | None
    critique: dict
    revision_count: int
    human_rounds: int
    seo: dict
    gates: list[dict]
    decision: dict | None
    review_note: str
    published: dict
    events: Annotated[list[dict], operator.add]
    usage: Annotated[dict, merge_usage]


def ev(node: str, msg: str, level: str = "info") -> dict:
    return {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "node": node, "msg": msg, "level": level}
