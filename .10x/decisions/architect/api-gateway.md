# Architect: api-gateway
- Components: auth (JWT decode), ratelimit (Lua bucket), routes (yaml prefix match), proxy (httpx), main (app factory), demo_service.
- Boundaries: each module is testable alone; main wires them via an app factory taking injected redis and http clients.
- Failure modes: Redis down (fail-open default), upstream down (502), upstream slow (504), bad token (401).
- See ADR-001.
