"""Pydantic models: API input, LLM structured outputs, and the content contract with the Astro site.

Lean blog flow (03-prd §6): plan -> write -> check. `check` returns scores, issues,
unsupported statements AND the SEO package in one call.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
Category = Literal["news", "guide", "tutorial", "opinion", "tooling"]


# ---------------------------------------------------------------- API input
class SourceInput(BaseModel):
    kind: Literal["text", "url"]
    title: str = ""
    url: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.kind == "url" and not (self.url and self.url.startswith(("http://", "https://"))):
            raise ValueError("url sources need an http(s) url")
        if self.kind == "text" and not (self.text and self.text.strip()):
            raise ValueError("text sources need text")
        return self


class RunRequest(BaseModel):
    mode: Literal["blog"] = "blog"
    topic: str = Field(min_length=3, max_length=200)
    audience: str = "developers learning full-stack and AI engineering"
    angle: str | None = None
    length: Literal["short", "medium", "long"] = "medium"
    notes: str = ""                      # Ben's own opinions/experience; the only place first-person claims may come from
    sources: list[SourceInput] = Field(min_length=1, max_length=12)
    checkpoint_plan: bool | None = None  # pause for plan approval before writing
    budget_usd: float | None = None      # per-run cost cap; None -> Settings.blog_budget_usd


# ---------------------------------------------------------------- LLM outputs
class KeyPoint(BaseModel):
    point: str = Field(description="One specific idea this section will make, in your own words")
    source_ids: list[str] = Field(min_length=1, description="Source ids (S1, S2, ...) that support it")


class PlanSection(BaseModel):
    heading: str
    goal: str = Field(description="What the reader should understand after this section")
    key_points: list[KeyPoint] = Field(min_length=1)


class BlogPlan(BaseModel):
    angle: str = Field(description="What this article offers that the top search results do not")
    working_title: str
    sections: list[PlanSection] = Field(min_length=2, max_length=9)


class Scores(BaseModel):
    grounding: int = Field(ge=1, le=5)
    unique_value: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    voice: int = Field(ge=1, le=5)
    redundancy: int = Field(ge=1, le=5, description="5 = no repetition")
    accuracy: int = Field(ge=1, le=5)
    usefulness: int = Field(ge=1, le=5)


class Issue(BaseModel):
    severity: Literal["high", "medium", "low"]
    location: str = Field(description="Section heading or a short quote locating the problem")
    problem: str
    fix: str


class SEOItem(BaseModel):
    title: str = Field(max_length=70)
    description: str = Field(min_length=70, max_length=160)
    slug: str
    tags: list[str] = Field(min_length=1, max_length=6)
    category: Category
    cover_prompt: str = ""

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must be lowercase-kebab-case")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = re.sub(r"[^a-z0-9]+", "-", t.strip().lower()).strip("-")
            if t and t not in out:
                out.append(t)
        if not out:
            raise ValueError("need at least one tag")
        return out


class CheckResult(BaseModel):
    scores: Scores
    issues: list[Issue] = []
    unsupported_claims: list[str] = Field(default=[], description="Statements in the draft that no source supports")
    seo: SEOItem


# ---------------------------------------------------------------- human decisions (resume payloads)
class PlanDecision(BaseModel):
    action: Literal["approve", "revise"]
    comments: list[str] = []
    plan: dict | None = None             # Ben's edited plan wins when provided


class Decision(BaseModel):
    action: Literal["approve", "changes", "reject"]
    comments: list[str] = []
    edited_md: str | None = None         # Ben's direct edits are authoritative
    seo: dict | None = None              # optional overrides: title, description, slug, tags, category
    force: bool = False                  # publish even though a blocking gate failed


# ---------------------------------------------------------------- course pipeline (03-prd §7)
RefType = Literal["docs", "video", "article", "repo", "interactive", "book", "course", "roadmap"]


class RefInput(BaseModel):
    """A reference coming off the search call — or typed by hand in refs_review."""
    title: str
    url: str
    type: RefType = "article"
    illustrated: bool = False
    level: str = ""
    why: str = ""

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("reference url must be http(s)")
        return v


class CourseRunRequest(BaseModel):
    """POST /runs body for a course run (graph `course`). Mirrors the New-Course form."""
    mode: Literal["course"]
    subject: str = Field(min_length=3, max_length=200)
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    audience: str = "developers who learn best by building"
    docs_urls: list[str] = Field(min_length=1, max_length=8)   # official docs to ground the course
    min_parts: int = Field(ge=1, le=20, default=2)
    max_parts: int = Field(ge=1, le=20, default=6)
    hints: str = ""
    repo_name: str = Field(min_length=3, max_length=80, description="folder + GitHub repo name, e.g. langgraph-deep-research")
    remote_url: str | None = Field(default=None, description="empty public GitHub repo; verified by doctor")
    budget_usd: float | None = None      # None -> Settings.course_budget_usd

    @field_validator("docs_urls")
    @classmethod
    def _urls(cls, v: list[str]) -> list[str]:
        for u in v:
            if not u.startswith(("http://", "https://")):
                raise ValueError("docs_urls must be http(s) urls")
        return v

    @model_validator(mode="after")
    def _parts(self):
        if self.min_parts > self.max_parts:
            raise ValueError("min_parts must be <= max_parts")
        return self


class CourseRef(BaseModel):
    """A verified reference after research_refs (+ any Ben added in review)."""
    id: str                              # R1, R2, ...
    title: str
    url: str
    type: RefType
    illustrated: bool = False
    level: str = ""                      # free-form: beginner/…/n/a
    why: str = ""
    verified: bool = False               # fetched OK during research


class CommitStep(BaseModel):
    title: str
    intent: str = Field(description="What this commit accomplishes and why it comes here")
    files: list[str] = Field(default=[], description="Paths the commit is expected to touch")


class PlannedPart(BaseModel):
    n: int = Field(ge=1)
    slug: str
    title: str
    objectives: list[str] = Field(min_length=2, description="What the learner can do after this part")
    concepts: list[str] = []
    steps: list[CommitStep] = Field(min_length=1, max_length=4, description="2-4 planned commits")
    doc_urls: list[str] = Field(default=[], description="official docs URLs from the docs map")
    ref_ids: list[str] = Field(default=[], description="kept reference ids, each explained in resource_notes")
    resource_notes: dict[str, str] = Field(default={}, description="ref_id -> one-line why this reference belongs here")
    estimatedMinutes: int = Field(default=90, ge=20, le=240)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v.strip().lower()):
            raise ValueError("part slug must be lowercase-kebab-case")
        return v.strip().lower()


class CourseProject(BaseModel):
    name: str
    slug: str
    summary: str = Field(min_length=10, description='"You will build X" in one or two sentences')
    stack: list[str] = Field(min_length=1)
    architecture_md: str = Field(default="", description="Initial docs/ARCHITECTURE.md text")
    final_features: list[str] = Field(min_length=1, description="What exists at the last part")


class CoursePlan(BaseModel):
    project: CourseProject
    parts: list[PlannedPart] = Field(min_length=1)

    @model_validator(mode="after")
    def _order(self):
        ns = [p.n for p in self.parts]
        if sorted(ns) != list(range(1, len(ns) + 1)):
            raise ValueError("parts must be numbered 1..N in order")
        if len({p.slug for p in self.parts}) != len(self.parts):
            raise ValueError("part slugs must be unique")
        return self


class RefsDecision(BaseModel):
    """Resume payload for the refs_review interrupt."""
    keep: list[str] = Field(min_length=1, description="reference ids to keep")
    added: list[RefInput] = []
    inspired_by: list[str] = []          # ids of refs credited on the course page


class ResearchOutput(BaseModel):
    """Structured result of the search-enabled reference survey."""
    refs: list[RefInput] = Field(min_length=3, max_length=20)


class CoursePlanDecision(BaseModel):
    """Resume payload for the plan_review interrupt."""
    action: Literal["approve", "changes"]
    plan: dict | None = None             # Ben's edited CoursePlan wins when provided
    comments: list[str] = []


# ---------------------------------------------------------------- content contract (mirrors packages/content-schema)
class SourceRef(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    accessed: date | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("source url must be http(s)")
        return v


class Frontmatter(BaseModel):
    title: str = Field(max_length=70)
    description: str = Field(min_length=70, max_length=160)
    pubDate: date
    lastReviewed: date
    tags: list[str] = Field(min_length=1, max_length=6)
    category: Category
    draft: bool = False
    featured: bool = False
    sources: list[SourceRef] = Field(min_length=1)
    aiAssisted: bool = True
    reviewedBy: str = "Ben"
    pipelineRunId: str | None = None
