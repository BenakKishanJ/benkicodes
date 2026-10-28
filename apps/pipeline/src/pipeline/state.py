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
    # -- part loop (03-prd §7.5–7.7)
    part_n: int                       # part currently in flight (0 = none started)
    part: dict                        # the PlannedPart dict in flight
    part_start_sha: str               # HEAD when the part started (branch-reset anchor)
    code: dict                        # CodeStepOutput as dict
    code_fixes: int                   # code_fix rounds used this part (max 2)
    code_feedback: list[str]          # Ben's code_review comments for the next code_step
    commits: list[dict]               # applied commits this part: [{sha, message}]
    tests: dict | None                # last repo/tests run: {ok, output, at}
    lesson_md: str                    # lesson body with {{code:…}} placeholders
    lesson_feedback: list[str]        # Ben's lesson_review comments for the next lesson_fix
    prev_lesson_md: str | None
    lesson_html: str                  # rendered lesson (snippets expanded) for review
    module_md: str                    # built module .md (frontmatter + expanded lesson), reused by publish
    quiz: list[dict]                  # QuizQuestion dicts for the module frontmatter
    check: dict                       # LessonCheckOutput as dict
    gates: list[dict]
    summary_for_next: str             # carried from lesson_check
    glossary: dict[str, str]          # term -> one-line definition (accumulated)
    lesson_fixes: int                 # lesson_fix rounds used this part
    review_rounds: int                # lesson_review rounds this part
    decision: dict | None
    review_note: str
    published_parts: list[dict]       # per-part: {n, slug, tag, tag_url, compare_url, lesson_url}
    # -- plumbing (shared with BlogState semantics)
    events: Annotated[list[dict], operator.add]
    usage: Annotated[dict, merge_usage]
    calls: Annotated[list[dict], operator.add]
