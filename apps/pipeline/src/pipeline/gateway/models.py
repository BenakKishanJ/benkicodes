"""Task configuration and the OpenRouter model catalog (cached)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import yaml

DEFAULT_TASKS = {
    "fast": {"model": "nvidia/nemotron-3-super-120b-a12b:free", "fallbacks": [], "temperature": 0.2},
    "plan": {"model": "deepseek/deepseek-v4-flash", "fallbacks": [], "temperature": 0.3},
    "plan_code": {"model": "deepseek/deepseek-v4-flash", "fallbacks": [], "temperature": 0.3},
    "write": {"model": "deepseek/deepseek-v4-flash", "fallbacks": [], "temperature": 0.7},
    "check": {"model": "z-ai/glm-5.3-flash", "fallbacks": [], "temperature": 0.2},
    "research": {"model": "z-ai/glm-5.3-flash", "fallbacks": [], "temperature": 0.3,
                 "plugins": [{"id": "web"}]},
}

def load_tasks(path: Path) -> dict[str, dict]:
    """task -> {model, fallbacks, temperature, plugins?}. Falls back to in-code defaults."""
    cfg: dict = {}
    try:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except OSError:
        pass
    tasks = {**DEFAULT_TASKS, **(cfg.get("tasks") or {})}
    for t in tasks.values():
        t.setdefault("fallbacks", [])
        t.setdefault("temperature", 0.2)
    return tasks


def fetch_catalog(cache: Path, ttl_s: float = 24 * 3600, timeout: float = 20.0) -> dict:
    """OpenRouter /models -> {id: {pricing, ...}}, cached under data/cache/.
    The catalog is public (no key needed). Failure falls back to a stale cache."""
    try:
        if cache.exists() and time.time() - cache.stat().st_mtime < ttl_s:
            return json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    r = httpx.get("https://openrouter.ai/api/v1/models", timeout=timeout,
                  headers={"User-Agent": "BenKiContentBot/0.1"})
    r.raise_for_status()
    catalog = {m["id"]: m for m in r.json()["data"]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(catalog))
    return catalog


def price_mtok(catalog: dict, model_id: str) -> tuple[float, float]:
    """(input $/Mtok, output $/Mtok). 0.0 when unknown -> estimated cost reads $0."""
    m = catalog.get(model_id) or {}
    p = m.get("pricing") or {}
    try:
        return float(p.get("prompt", 0) or 0) * 1e6, float(p.get("completion", 0) or 0) * 1e6
    except (TypeError, ValueError):
        return 0.0, 0.0
