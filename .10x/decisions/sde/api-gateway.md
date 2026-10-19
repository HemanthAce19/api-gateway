# SDE: api-gateway (what was built)
- Built per plan: config, auth, Lua limiter, routes, proxy, app factory, demo service, scripts, Docker, CI, docs.
- Deviation from spec: responses are buffered (spec already said buffered; the early design note said "stream").
- Redis-py asyncio script object is registered once per limiter instance; Lua returns floats as strings.
- Tech debt: no request body size cap; no per-route limits; no metrics.
