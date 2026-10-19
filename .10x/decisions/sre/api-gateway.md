# SRE: api-gateway
- Observability today: one structured log line per request, /healthz.
- Failure behavior: Redis down = fail open (degraded header) or closed (503); upstream down = 502; slow = 504.
- Next steps if it were run for real: Prometheus metrics (allowed, denied, latency), alert on degraded rate, SLO on gateway added latency.
- Runbook: Redis outage -> check redis container health; gateway keeps serving in fail-open mode.
