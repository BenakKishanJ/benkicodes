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


class CourseState(TypedDict, total=False):
    run_id: str
    mode: str
    inputs: dict[str, Any]            # validated CourseRunRequest as a dict
    budget_usd: float                 # effective per-run cap
    status: str
    # -- planning
    docs: list[dict]                  # docs map: [{id, title, url, chars}] (page text cached on disk)
    refs: list[dict]                  # CourseRef dicts (verified, before review)
    inspired_by: list[str]            # ref ids credited on the course page
    plan: dict                        # CoursePlan as dict; slugs/order frozen after plan_review
    plan_feedback: list[str]
    repo: dict                        # {path, name, remote_url, remote_ok, empty_ok, tagged: [part-0]}
    # -- part loop (Phase B fills these in)
    part_n: int                       # part currently in flight
    code_fixes: int                   # code_fix rounds used this part (max 2)
    lesson_fixes: int                 # lesson_fix rounds used this part
    published_parts: list[dict]       # per-part: {n, slug, tag, tag_url, compare_url, lesson_url}
    # -- plumbing (shared with BlogState semantics)
    events: Annotated[list[dict], operator.add]
    usage: Annotated[dict, merge_usage]
    calls: Annotated[list[dict], operator.add]
