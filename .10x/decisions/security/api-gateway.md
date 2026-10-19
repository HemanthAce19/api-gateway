# Security: api-gateway
- JWT: HS256 pinned, exp and sub required, alg none rejected, plan validated, secret min 32 chars enforced at startup.
- Spoofing: inbound X-User-Id and X-User-Plan dropped; Authorization not forwarded.
- Accepted risks (documented in README): no body size limit, XFF ignored, shared-secret HS256, DEMO_MODE token endpoint is unauthenticated by design, compose ships a demo-only default secret.
- Path forwarding uses the decoded request path with a single configured upstream; revisit if multiple upstreams or path rewriting are added.
