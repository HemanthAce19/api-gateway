# ADR-001: Atomic token bucket implemented as a Redis Lua script

**Status:** Accepted
**Date:** 2026-10-19
**Feature:** api-gateway
**Author:** 10x-Team (Architect + Staff Engineer)

## Context
The gateway may run as several instances and must enforce one shared limit per caller. A limiter
that reads and writes in separate Redis calls lets concurrent requests all see the same token count.

## Decision
Implement the token bucket as one Lua script executed by Redis (refill, check, decrement, TTL),
using Redis `TIME` as the only clock. State lives in a hash per key.

## Alternatives Considered
| Alternative | Pros | Cons | Why Not |
|---|---|---|---|
| GET/SET from Python | Simple | Race condition under concurrency | Over-admits requests |
| WATCH/MULTI/EXEC | No Lua | Retry loops, more round trips | Slower and more code |
| Fixed-window INCR | Very simple | Burst at window edges | Weaker guarantee |
| In-process memory | No dependency | Not shared across instances | Wrong for a gateway |

## Consequences
### Positive
- Exactly `capacity` requests pass in a burst, regardless of concurrency or instance count.
- One round trip per request.
### Negative
- Lua logic is harder to debug than Python; mitigated by tests.
### Risks
- Redis outage: handled by configurable fail-open or fail-closed behavior.

## Dependencies
- Redis 6+ (7 in docker compose). Constrains future per-route limits to extend the same script.
