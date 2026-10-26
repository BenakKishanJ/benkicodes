from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

USAGE_KEYS = ("input", "output", "calls", "usd")


def merge_usage(a: dict | None, b: dict | None) -> dict:
    a, b = a or {}, b or {}
    return {k: a.get(k, 0) + b.get(k, 0) for k in USAGE_KEYS}


class BlogState(TypedDict, total=False):
    run_id: str
    mode: str
    inputs: dict[str, Any]            # the validated RunRequest as a dict
    budget_usd: float                 # effective per-run cap
    status: str
    sources: list[dict]               # {id, kind, title, url, text, flags, chars}
    plan: dict                        # BlogPlan as dict
    plan_feedback: list[str]
    draft_md: str
    prev_draft: str | None
    check: dict                       # CheckResult as dict (scores, issues, unsupported, seo)
    revision_count: int
    human_rounds: int
    gates: list[dict]
    decision: dict | None
    review_note: str
    published: dict
    events: Annotated[list[dict], operator.add]
    usage: Annotated[dict, merge_usage]
    calls: Annotated[list[dict], operator.add]   # per-model-call records (gateway)


def ev(node: str, msg: str, level: str = "info") -> dict:
    return {"t": datetime.now(UTC).isoformat(timespec="seconds"), "node": node, "msg": msg, "level": level}
