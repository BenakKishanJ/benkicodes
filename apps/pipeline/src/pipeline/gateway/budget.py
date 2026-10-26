"""Per-run budget caps (03-prd §4.6). Checked before every model call."""
from __future__ import annotations


class BudgetPause(Exception):
    """Raised when a run reaches its cap. The run pauses with no data loss:
    the LangGraph checkpoint survives, and resuming raises the cap first."""


def ensure_allowed(spent: float, cap: float | None = None, warn_at: float = 0.8) -> bool:
    """True when the run may make another model call. Raises BudgetPause at 100%.
    Returns False instead of raising when no cap is configured (never blocks)."""
    if cap is None or cap <= 0:
        return True
    if spent >= cap:
        raise BudgetPause(f"budget cap reached: ${spent:.2f} of ${cap:.2f} programmed for this run")
    return spent >= warn_at * cap  # True means warn
