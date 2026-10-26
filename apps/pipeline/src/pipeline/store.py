"""Tiny run index (id, topic, status, timestamps). The full run state lives in the LangGraph checkpointer."""
from __future__ import annotations
import sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path


class RunStore:
    def __init__(self, path: Path):
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._c.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._c.execute("""CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, topic TEXT, mode TEXT, status TEXT, error TEXT,
                created_at TEXT, updated_at TEXT)""")
            self._c.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def create(self, run_id: str, topic: str, mode: str = "blog") -> None:
        with self._lock:
            self._c.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)", (run_id, topic, mode, "queued", None, self._now(), self._now()))
            self._c.commit()

    def update(self, run_id: str, status: str | None = None, error: str | None = ..., ) -> None:  # type: ignore[assignment]
        with self._lock:
            if status is not None:
                self._c.execute("UPDATE runs SET status=?, updated_at=? WHERE id=?", (status, self._now(), run_id))
            if error is not ...:
                self._c.execute("UPDATE runs SET error=?, updated_at=? WHERE id=?", (error, self._now(), run_id))
            self._c.commit()

    def get(self, run_id: str) -> dict | None:
        with self._lock:
            r = self._c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(r) if r else None

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 200")]

    def delete(self, run_id: str) -> None:
        with self._lock:
            self._c.execute("DELETE FROM runs WHERE id=?", (run_id,))
            self._c.commit()
