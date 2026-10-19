# Staff Engineer: api-gateway
- Patterns: app factory with dependency injection, settings object read once from env, structured JSON-ish log line per request.
- Standards: ruff clean, type hints, no secrets in repo, tests for every module.
- Cross-cutting: logging and error responses share one JSON error shape `{"error": "...", "detail": "..."}`.
