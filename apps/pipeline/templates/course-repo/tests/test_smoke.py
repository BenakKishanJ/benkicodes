"""Follow-along tests use a fake LLM: no network, no API keys, deterministic."""
from __future__ import annotations

import __PKG__ as pkg


def test_import():
    assert pkg is not None


def test_scaffold_is_clean():
    """Replace with real tests as parts land; keep runtime under one second."""
    assert pkg.__name__ == "__PKG__"
