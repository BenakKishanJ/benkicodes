"""Lean OpenRouter gateway (03-prd §4).

Interface used by graph nodes (protocol in client.py):
    text(task, system, user, temperature=None, budget=None, spent=0.0) -> (str, record)
    structured(task, schema, system, user, budget=None, spent=0.0) -> (model, record)

Rules encoded here:
- task → model routing comes from config/models.yaml, never hard-coded
- structured output requests `require_parameters` so OpenRouter only routes to
  endpoints that support JSON schema responses
- validation retries (2) with the error appended, then fallback model, then a
  clear failure
- every call returns a per-call cost record; per-run budget caps are checked
  *before* each model call and pause the run without losing state.
"""
