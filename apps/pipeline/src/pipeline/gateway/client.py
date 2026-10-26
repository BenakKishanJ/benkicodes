"""OpenRouter gateway implementation over langchain-openrouter's ChatOpenRouter."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from pydantic import BaseModel

from ..config import Settings
from .budget import ensure_allowed
from .models import fetch_catalog, load_tasks, price_mtok

T = TypeVar("T", bound=BaseModel)


class Gateway(Protocol):
    def text(self, task: str, system: str, user: str, temperature: float | None = None,
             *, budget: float | None = None, spent: float = 0.0
             ) -> tuple[str, dict]: ...
    def structured(self, task: str, schema: type[T], system: str, user: str,
                   *, budget: float | None = None, spent: float = 0.0
                   ) -> tuple[T, dict]: ...
    def credits(self) -> dict: ...


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _record(task: str, model: str, u: dict, latency_ms: int, retries: int = 0,
            fallback: bool = False) -> dict:
    return {"ts": _now(), "task": task, "model": model,
            "input": u.get("input", 0), "output": u.get("output", 0),
            "usd": round(u.get("usd", 0.0), 4), "latency_ms": latency_ms,
            "calls": 1, "retries": retries, "fallback": fallback}


def merge_usage(a: dict | None, b: dict | None) -> dict:
    a, b = a or {}, b or {}
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("input", "output", "calls", "usd")}


def _tokens_cost(catalog: dict, model: str, msg) -> dict:
    meta = getattr(msg, "usage_metadata", None) or {}
    inp, out = int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))
    in_p, out_p = price_mtok(catalog, model)
    usd = (inp * in_p + out * out_p) / 1e6
    # Prefer OpenRouter's own billed cost when reported.
    response_meta = getattr(msg, "response_metadata", None) or {}
    cost = response_meta.get("cost") if isinstance(response_meta, dict) else None
    if isinstance(cost, (int, float)) and cost > 0:
        usd = float(cost)
    return {"input": inp, "output": out, "calls": 1, "usd": usd}


class OpenRouterGateway:
    """task -> ChatOpenRouter routing from config/models.yaml with fallbacks."""

    def __init__(self, s: Settings):
        from langchain_openrouter import ChatOpenRouter
        self._Chat = ChatOpenRouter
        self.s = s
        self.tasks = load_tasks(s.models_file)
        self._cache: dict[tuple[str, str], object] = {}
        self._catalog: dict | None = None

    # ------------------------------------------------------------------ plumbing
    def catalog(self) -> dict:
        if self._catalog is None:
            try:
                self._catalog = fetch_catalog(self.s.data_dir / "cache" / "models.json")
            except Exception:  # noqa: BLE001 — catalog is best-effort; cost falls back to 0
                self._catalog = {}
        return self._catalog

    def _chat(self, task: str, temperature: float | None, structured: bool):
        rid = self.tasks[task]["model"]
        key = (rid, temperature if temperature is not None else structured)
        if key not in self._cache:
            self._cache[key] = self._Chat(
                model=rid,
                api_key=self.s.openrouter_api_key or None,
                temperature=temperature if temperature is not None else self.tasks[task].get("temperature", 0.2),
                timeout=120_000,
                max_retries=1,
                app_title="benki-pipeline",
                openrouter_provider={"require_parameters": True} if structured else None,
            )
        return self._cache[key]

    @staticmethod
    def _check_budget(budget: float | None, spent: float):
        ensure_allowed(spent, budget)

    @staticmethod
    def _as_text(msg) -> str:
        c = msg.content
        if isinstance(c, str):
            return c
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)

    # ------------------------------------------------------------------ public API
    def text(self, task: str, system: str, user: str, temperature: float | None = None,
             *, budget: float | None = None, spent: float = 0.0) -> tuple[str, dict]:
        self._check_budget(budget, spent)
        t0 = time.monotonic()
        out = self._chat(task, temperature, structured=False)
        msg = out.invoke([("system", system), ("user", user)])
        u = _tokens_cost(self.catalog(), self.tasks[task]["model"], msg)
        return self._as_text(msg).strip(), _record(task, self.tasks[task]["model"], u,
                                                   int((time.monotonic() - t0) * 1000))

    def structured(self, task: str, schema: type[T], system: str, user: str,
                   *, budget: float | None = None, spent: float = 0.0) -> tuple[T, dict]:
        if budget is not None:
            self._check_budget(budget, spent)
        tasks = self.tasks[task]
        prompt, last_err, total = user, "", {"input": 0, "output": 0, "calls": 0, "usd": 0.0}
        variants = [(tasks["model"], False)] + [(m, True) for m in tasks.get("fallbacks", [])]
        t0 = time.monotonic()
        for model_id, is_fallback in variants:
            chat = self._chat_task_model(task, model_id, structured=True)
            for attempt in (1, 2):     # two validation retries, then fail over
                runner = chat.with_structured_output(schema, method="json_schema", include_raw=True)
                out = runner.invoke([("system", system), ("user", prompt)])
                u = _tokens_cost(self.catalog(), model_id, out.get("raw"))
                total = {k: total[k] + u.get(k, 0) for k in total}
                if out.get("parsed") is not None:
                    rec = _record(task, model_id, total, int((time.monotonic() - t0) * 1000),
                                  retries=attempt - 1, fallback=is_fallback)
                    # merge the record into total cost: _record recomputes usd from merged totals
                    rec["usd"] = round(total["usd"], 4)
                    rec["input"], rec["output"], rec["calls"] = total["input"], total["output"], total["calls"]
                    return out["parsed"], rec
                last_err = str(out.get("parsing_error") or "unparseable output")[:600]
                prompt = (f"{user}\n\nYour previous answer was invalid ({last_err}). "
                          "Return a corrected object that satisfies every constraint.")
        raise RuntimeError(f"model returned invalid structured output twice per model: {last_err}")

    # Chat cache keyed by explicit model id (fallback variants reuse the same cache).
    def _chat_task_model(self, task: str, model_id: str, structured: bool):
        from langchain_openrouter import ChatOpenRouter
        key = (model_id, True)
        if key not in self._cache:
            self._cache[key] = ChatOpenRouter(
                model=model_id,
                api_key=self.s.openrouter_api_key or None,
                temperature=self.tasks[task].get("temperature", 0.2),
                timeout=120_000,
                max_retries=1,
                app_title="benki-pipeline",
                openrouter_provider={"require_parameters": True} if structured else None,
            )
        return self._cache[key]

    def credits(self) -> dict:
        """OpenRouter account credit passthrough (auth requires a key)."""
        import httpx
        if not self.s.openrouter_api_key:
            return {"error": "no OPENROUTER_API_KEY configured"}
        r = httpx.get("https://openrouter.ai/api/v1/credits",
                      headers={"Authorization": f"Bearer {self.s.openrouter_api_key}"},
                      timeout=15)
        r.raise_for_status()
        return r.json().get("data", {})


def get_gateway(settings: Settings) -> Gateway:
    return OpenRouterGateway(settings)
