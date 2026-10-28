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


# ---------------------------------------------------------------- part loop (03-prd §7.5–7.6)
class EditOp(BaseModel):
    """One in-file change for the `edit` op: search must match exactly once."""
    search: str = Field(min_length=1)
    replace: str


class FileEdit(BaseModel):
    path: str
    op: Literal["create", "replace", "edit", "delete"]
    content: str | None = None
    edits: list[EditOp] = Field(default=[])

    @model_validator(mode="after")
    def _shape(self):
        if self.op in ("create", "replace") and self.content is None:
            raise ValueError(f"{self.op} needs content ({self.path})")
        if self.op == "edit" and not self.edits:
            raise ValueError(f"edit needs at least one search/replace ({self.path})")
        if self.op in ("create", "replace") and self.edits:
            raise ValueError(f"{self.op} takes content, not edits ({self.path})")
        return self


class Dependency(BaseModel):
    name: str
    dev: bool = False


class CodeCommit(BaseModel):
    message: str = Field(min_length=8, max_length=200, description='Conventional subject line, e.g. "part-1: add argparse CLI skeleton"')
    edits: list[FileEdit] = Field(min_length=1)
    add_dependencies: list[Dependency] = []


class CodeStepOutput(BaseModel):
    commits: list[CodeCommit] = Field(min_length=2, max_length=4)
    architecture_update: str = ""        # replacement text for docs/ARCHITECTURE.md ("" = unchanged)
    notes_for_lesson: str = ""           # what to emphasise when teaching this part


class QuizOption(BaseModel):
    id: str = Field(pattern=r"^[a-f]$")
    text: str = Field(min_length=1, max_length=200)


class QuizQuestion(BaseModel):
    """Mirrors packages/content-schema common.quizQuestion (site contract)."""
    id: str = Field(pattern=r"^[a-z0-9_-]+$", max_length=24)
    question: str = Field(min_length=8, max_length=300)
    type: Literal["single", "multi"] = "single"
    options: list[QuizOption] = Field(min_length=3, max_length=6)
    correct: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=10, max_length=600)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    hint: str | None = None

    @model_validator(mode="after")
    def _correct_in_options(self):
        ids = {o.id for o in self.options}
        bad = [c for c in self.correct if c not in ids]
        if bad:
            raise ValueError(f"correct ids not in options: {', '.join(bad)}")
        if self.type == "single" and len(self.correct) != 1:
            raise ValueError("single-choice questions need exactly one correct id")
        return self


class QuizOutput(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=3, max_length=6)


class CheckIssue(BaseModel):
    severity: Literal["high", "medium", "low"]
    location: str
    problem: str
    fix: str


class LessonCheckOutput(BaseModel):
    scores: dict[str, int] = Field(description="1-5 per dimension: accuracy, clarity, code-correctness, coverage, tone")
    issues: list[CheckIssue] = []
    unsupported_claims: list[str] = []
    meta_description: str = Field(min_length=70, max_length=160)
    summary_for_next: str = Field(max_length=1000, description="<=120 words: what the next part can assume")

    @field_validator("scores")
    @classmethod
    def _scores(cls, v: dict) -> dict:
        bad = {k: x for k, x in v.items() if not (isinstance(x, int) and 1 <= x <= 5)}
        if bad:
            raise ValueError(f"scores must be ints 1-5, got {bad}")
        return v


class CodeReviewDecision(BaseModel):
    """Resume payload for the code_review interrupt."""
    action: Literal["accept", "fix"]
    comment: str | None = None           # fix: what to change (goes to code_fix)
    commit_message: str | None = None    # accept with manual edits: subject line for the commit

    @model_validator(mode="after")
    def _comment_required_on_fix(self):
        if self.action == "fix" and not (self.comment or "").strip():
            raise ValueError("a fix request needs a comment")
        return self


class LessonReviewDecision(BaseModel):
    """Resume payload for the lesson_review interrupt."""
    action: Literal["approve", "fix", "back_to_code"]
    edited_md: str | None = None         # Ben's direct edits are authoritative
    comment: str | None = None

    @model_validator(mode="after")
    def _comment_required_on_fix(self):
        if self.action == "fix" and not (self.comment or "").strip():
            raise ValueError("a fix request needs a comment")
        return self


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


# ---- roadmap/module frontmatter, mirrors packages/content-schema roadmap.ts/moduleSchema ----
def _gh_url(v: str) -> str:
    if not v.startswith("https://github.com/"):
        raise ValueError(f"must be a GitHub URL: {v}")
    return v


class ModuleSource(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    accessed: date | None = None

    @field_validator("url")
    @classmethod
    def _u(cls, v: str) -> str:
        return _gh_url(v) if v.startswith("https://github.com/") else v


class ModuleResource(BaseModel):
    title: str
    url: str
    type: Literal["docs", "video", "article", "repo", "interactive", "book"]
    why: str = Field(default="", max_length=200)
    illustrated: bool = False

    @field_validator("url")
    @classmethod
    def _u(cls, v: str) -> str:
        return v


class CodeCommitRef(BaseModel):
    sha: str = Field(min_length=7, max_length=40)
    message: str
    url: str

    @field_validator("url")
    @classmethod
    def _u(cls, v: str) -> str:
        return _gh_url(v)


class CodePanel(BaseModel):
    startTag: str
    endTag: str
    compareUrl: str
    treeUrl: str
    commits: list[CodeCommitRef] = Field(min_length=1)
    files: list[str] = []

    @field_validator("compareUrl", "treeUrl")
    @classmethod
    def _gh(cls, v: str) -> str:
        return _gh_url(v)


class ModuleFrontmatter(BaseModel):
    """Mirrors moduleSchema (02-prd §5.3) — the schema gate validates against this."""
    title: str = Field(max_length=70)
    order: int = Field(ge=1)
    estimatedMinutes: int = Field(ge=15, le=300)
    objectives: list[str] = Field(min_length=2)
    sources: list[ModuleSource] = Field(min_length=1)
    resources: list[ModuleResource] = []
    code: CodePanel
    quiz: list[QuizQuestion] = Field(min_length=3)
    lastReviewed: date
    draft: bool = False
    pipelineRunId: str | None = None


class RoadmapPlanned(BaseModel):
    slug: str
    title: str
    estimatedMinutes: int


class RoadmapProject(BaseModel):
    repo: str
    defaultBranch: str = "main"
    template: bool = False
    license: str | None = None
    stack: list[str] = []
    summary: str = Field(max_length=240)

    @field_validator("repo")
    @classmethod
    def _gh(cls, v: str) -> str:
        return _gh_url(v)


class RoadmapInspiredBy(BaseModel):
    title: str
    url: str
    author: str | None = None
    note: str | None = None


class RoadmapFrontmatter(BaseModel):
    """Mirrors roadmapSchema (02-prd §5.2)."""
    title: str = Field(max_length=70)
    description: str = Field(max_length=160)
    level: Literal["beginner", "intermediate", "advanced"]
    estimatedHours: float
    prerequisites: list[str] = []
    outcomes: list[str] = Field(min_length=3)
    tags: list[str] = []
    status: Literal["in-progress", "complete"] = "in-progress"
    planned: list[RoadmapPlanned] = []
    project: RoadmapProject
    inspiredBy: list[RoadmapInspiredBy] = []
    lastReviewed: date
    version: str = "1.0"
    draft: bool = False
    featured: bool = False
    pipelineRunId: str | None = None
