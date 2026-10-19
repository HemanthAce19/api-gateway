# Senior Engineer: api-gateway
- Lua returns strings for floats because Redis truncates Lua numbers to integers in replies.
- Build responses from buffered upstream content; drop hop-by-hop and content-length-sensitive headers.
- Tests use ASGITransport so the demo app is the upstream with no network.
