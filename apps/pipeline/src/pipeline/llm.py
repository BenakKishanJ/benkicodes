"""Thin LLM layer. Nodes only ever call .text() and .structured(), so the provider is swappable
(Gemini by default; anthropic/openai via env) and tests can inject a fake."""
from __future__ import annotations
from typing import Protocol, TypeVar
from pydantic import BaseModel
from .config import Settings

T = TypeVar("T", bound=BaseModel)
Usage = dict  # {"input": int, "output": int, "calls": int}


class LLM(Protocol):
    def text(self, system: str, user: str, tier: str = "strong", temperature: float = 0.7) -> tuple[str, Usage]: ...
    def structured(self, schema: type[T], system: str, user: str, tier: str = "fast") -> tuple[T, Usage]: ...


class LangChainLLM:
    def __init__(self, settings: Settings):
        self.s = settings
        self._cache: dict[tuple[str, float], object] = {}

    def _model(self, tier: str, temperature: float):
        from langchain.chat_models import init_chat_model
        name = {"fast": self.s.model_fast, "strong": self.s.model_strong, "critic": self.s.model_critic}[tier]
        key = (name, temperature)
        if key not in self._cache:
            self._cache[key] = init_chat_model(name, model_provider=self.s.llm_provider, temperature=temperature)
        return self._cache[key]

    @staticmethod
    def _usage(msg) -> Usage:
        u = getattr(msg, "usage_metadata", None) or {}
        return {"input": int(u.get("input_tokens", 0)), "output": int(u.get("output_tokens", 0)), "calls": 1}

    @staticmethod
    def _as_text(msg) -> str:
        c = msg.content
        if isinstance(c, str):
            return c
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)  # content blocks

    def text(self, system, user, tier="strong", temperature=0.7):
        from langchain_core.messages import HumanMessage, SystemMessage
        msg = self._model(tier, temperature).invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return self._as_text(msg).strip(), self._usage(msg)

    def structured(self, schema, system, user, tier="fast"):
        from langchain_core.messages import HumanMessage, SystemMessage
        runner = self._model(tier, 0.2).with_structured_output(schema, include_raw=True)
        total = {"input": 0, "output": 0, "calls": 0}
        prompt, last_err = user, ""
        for _ in range(3):
            out = runner.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
            u = self._usage(out.get("raw"))
            total = {k: total[k] + u[k] for k in total}
            if out.get("parsed") is not None:
                return out["parsed"], total
            last_err = str(out.get("parsing_error") or "unparseable output")[:600]
            prompt = f"{user}\n\nYour previous answer was invalid ({last_err}). Return a corrected object that satisfies every constraint."
        raise RuntimeError(f"model returned invalid structured output 3 times: {last_err}")


def get_llm(settings: Settings) -> LLM:
    return LangChainLLM(settings)
