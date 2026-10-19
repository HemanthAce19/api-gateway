# QA: api-gateway
- 47 pytest tests pass on fakeredis (Python 3.10) and on real Redis 7 (Python 3.13).
- Mutation checks: broken Lua = 11 failures; weakened JWT algorithm list = 2 failures. Tests can fail.
- Live run with real uvicorn servers and Redis: demo.sh scenes all matched expectations (200 concurrent = exactly 10 allowed).
- Not verified locally: Docker image build and compose run (no Docker daemon available). CI compose-smoke job covers it.
- Not covered: very large request bodies, HTTP/2, multi-process uvicorn workers against one Redis.
