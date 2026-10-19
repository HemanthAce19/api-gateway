# DBA: api-gateway
- No relational schema. Redis keys: `rl:<user:SUB|ip:ADDR>` hash {tokens, ts}, TTL = 2 * capacity / rate seconds.
- Keys are bounded by active callers and expire when idle. Script touches one key, so it is Cluster-safe.
