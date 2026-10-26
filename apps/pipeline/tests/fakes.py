import re
from pipeline.schemas import (Claim, ClaimList, Critique, Issue, Outline, OutlineSection, SEOPackage, Scores, SourceSummary)

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


class FakeLLM:
    def __init__(self, fail_first_critique=True):
        self.calls = []
        self.critiques = 0
        self.fail_first = fail_first_critique

    def text(self, system, user, tier="strong", temperature=0.7):
        self.calls.append(("text", user[:30]))
        if user.startswith("Revise this draft"):
            return ARTICLE + "\nA short revised addition [S1].", {"input": 10, "output": 10, "calls": 1}
        if user.startswith("The author reviewed"):
            m = re.search(r"COMMENTS:\n- (.*)", user)
            return ARTICLE + f"\nAuthor change applied: {m.group(1) if m else ''} [S1].", {"input": 10, "output": 10, "calls": 1}
        return ARTICLE, {"input": 100, "output": 200, "calls": 1}

    def structured(self, schema, system, user, tier="fast"):
        self.calls.append(("structured", schema.__name__))
        u = {"input": 5, "output": 5, "calls": 1}
        if schema is SourceSummary:
            return SourceSummary(title="Example source", summary="It explains the idea.", trust="high"), u
        if schema is ClaimList:
            ids = re.findall(r'<source id="(S\d+)"', user) or ["S1"]
            return ClaimList(claims=[Claim(id=f"C{i}", text=f"Claim number {i} about state", source_ids=[ids[0]]) for i in range(1, 4)]), u
        if schema is Outline:
            return Outline(angle="A worked example", working_title="LangGraph state explained", sections=[
                OutlineSection(id="s1", heading="What state is", goal="define it", claim_ids=["C1"]),
                OutlineSection(id="s2", heading="Why it matters", goal="motivate", claim_ids=["C2", "C3"])]), u
        if schema is Critique:
            self.critiques += 1
            bad = self.fail_first and self.critiques == 1
            n = 2 if bad else 5
            return Critique(scores=Scores(grounding=n, unique_value=n, clarity=n, voice=n, redundancy=n, accuracy=n, usefulness=n),
                            issues=[Issue(severity="medium", location="intro", problem="vague", fix="be specific")] if bad else [],
                            unsupported_claims=[]), u
        if schema is SEOPackage:
            return SEOPackage(title="LangGraph state explained", description="A practical walk through LangGraph state: how nodes read and update it, and why saved state makes runs resumable.",
                              slug="langgraph-state-explained", tags=["langgraph", "ai"], category="guide", cover_prompt="pixel graph"), u
        raise AssertionError(schema)
