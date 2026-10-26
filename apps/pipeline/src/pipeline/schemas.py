"""Pydantic models: API input, LLM structured outputs, and the content contract with the Astro site."""
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
    topic: str = Field(min_length=3, max_length=200)
    audience: str = "developers learning full-stack and AI engineering"
    angle: str | None = None
    length: Literal["short", "medium", "long"] = "medium"
    notes: str = ""                      # Ben's own opinions/experience; the only place first-person claims may come from
    sources: list[SourceInput] = Field(min_length=1, max_length=12)
    checkpoint_outline: bool | None = None


# ---------------------------------------------------------------- LLM outputs
class SourceSummary(BaseModel):
    title: str = Field(description="A short descriptive title for the source")
    summary: str = Field(description="2-3 sentences: what this source says and why it is credible or not")
    trust: Literal["high", "medium", "low"]


class Claim(BaseModel):
    id: str
    text: str = Field(description="One atomic, checkable factual claim, in your own words")
    source_ids: list[str] = Field(min_length=1)


class ClaimList(BaseModel):
    claims: list[Claim] = Field(min_length=1)


class OutlineSection(BaseModel):
    id: str
    heading: str
    goal: str = Field(description="What the reader should understand after this section")
    claim_ids: list[str] = []


class Outline(BaseModel):
    angle: str = Field(description="What this article offers that top search results do not")
    working_title: str
    sections: list[OutlineSection] = Field(min_length=2, max_length=9)


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


class Critique(BaseModel):
    scores: Scores
    issues: list[Issue] = []
    unsupported_claims: list[str] = Field(default=[], description="Statements in the draft that no source supports")


class SEOPackage(BaseModel):
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


# ---------------------------------------------------------------- human decisions (resume payloads)
class OutlineDecision(BaseModel):
    action: Literal["approve", "revise"]
    comments: list[str] = []
    outline: dict | None = None          # Ben's edited outline wins when provided


class Decision(BaseModel):
    action: Literal["approve", "changes", "reject"]
    comments: list[str] = []
    edited_md: str | None = None         # Ben's direct edits are authoritative
    seo: dict | None = None              # optional overrides: title, description, slug, tags, category
    force: bool = False                  # publish even though a blocking gate failed


# ---------------------------------------------------------------- content contract (mirrors src/content.config.ts)
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
