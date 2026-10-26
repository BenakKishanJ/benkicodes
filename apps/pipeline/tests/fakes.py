import re

from pipeline.schemas import (
    BlogPlan,
    CheckResult,
    Issue,
    KeyPoint,
    PlanSection,
    Scores,
    SEOItem,
)

ARTICLE = """Learn how a LangGraph node reads and updates shared state. This article walks through the idea with a small, working example [S1].

## What state is

State is one object that every node can read, and each node returns only the keys it wants to change [S1]. That makes runs easy to pause and resume.

```python
def draft(state):
    return {"draft": "hello"}
```

## Why it matters

Because the state is saved after each step, a run can wait for a human and continue later [S1].
"""

TASKS = {t: {"model": "fake/model", "purpose": "test" if False else p}
         for t, p in (("plan", "planning"), ("write", "drafting"), ("check", "critique add seo"), ("fast", "misc"))}


def _usage(task: str, usd: float = 0.001) -> dict:
    return {"task": task, "model": "fake/model", "input": 100, "output": 200,
            "calls": 1, "usd": usd, "latency_ms": 5, "retries": 0, "fallback": False, "ts": "t"}


class FakeGateway:
    """Matches pipeline.gateway.common.Gateway. charge = $ per call (0 in the main flow)."""

    def __init__(self, fail_first_check: bool = False, charge: float = 0.0):
        self.fail_first = fail_first_check
        self.charge = charge
        self.checks = 0
        self.tasks = TASKS
        self.calls: list[tuple] = []

    def catalog(self) -> dict:
        return {}

    def credits(self) -> dict:
        return {"total_credits": "12.5"}

    def text(self, task, system, user, temperature=None, *, budget=None, spent=0.0):
        self.calls.append(("text", task))
        if user.startswith("Revise this draft"):
            return ARTICLE + "\nA short revised addition [S1].", _usage(task, self.charge)
        if user.startswith("The author reviewed"):
            m = re.search(r"COMMENTS:\n- (.*)", user)
            return ARTICLE + f"\nAuthor change applied: {m.group(1) if m else ''} [S1].", _usage(task, self.charge)
        return ARTICLE, _usage(task, self.charge)

    def structured(self, task, schema, system, user, *, budget=None, spent=0.0):
        self.calls.append(("structured", schema.__name__))
        u = _usage(task, self.charge)
        if schema is BlogPlan:
            return BlogPlan(angle="A worked example nobody else does", working_title="LangGraph state explained", sections=[
                PlanSection(heading="What state is", goal="define it", key_points=[
                    KeyPoint(point="State is one shared object", source_ids=["S1"]),
                    KeyPoint(point="Nodes return partial updates", source_ids=["S1"])]),
                PlanSection(heading="Why it matters", goal="motivate", key_points=[
                    KeyPoint(point="Saved state makes runs resumable", source_ids=["S1"])])]), u
        if schema is CheckResult:
            self.checks += 1
            bad = self.fail_first and self.checks == 1
            n = 2 if bad else 5
            return CheckResult(scores=Scores(grounding=n, unique_value=n, clarity=n, voice=n, redundancy=n, accuracy=n, usefulness=n),
                               issues=[Issue(severity="high", location="intro", problem="vague", fix="be specific")] if bad else [],
                               unsupported_claims=["a vague vibe claim"] if bad else [],
                               seo=SEOItem(title="LangGraph state explained",
                                           description="A practical walk through LangGraph state: how nodes read and update it, and why saved state makes runs resumable.",
                                           slug="langgraph-state-explained", tags=["langgraph", "ai"],
                                           category="guide", cover_prompt="pixel graph")), u
        raise AssertionError(schema)
