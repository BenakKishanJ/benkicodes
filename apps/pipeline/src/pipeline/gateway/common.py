"""The gateway protocol, the OpenRouter implementation, and test fakes live here.

Call record shape (returned with every call and aggregated in run state):
    {"task", "model", "input", "output", "usd", "latency_ms", "calls", "retries", "fallback"}
"""
from __future__ import annotations