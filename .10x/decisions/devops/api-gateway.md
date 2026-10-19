# DevOps: api-gateway
- Dockerfile (python:3.12-slim, non-root). Compose: redis (healthcheck), demo-service, gateway (healthcheck).
- CI: test job (py3.10 and 3.12, Redis service, ruff + pytest), compose-smoke job (up --wait, demo.sh, down).
- Rollback: tag-based image rollback; nothing persistent (Redis holds only expiring buckets).
