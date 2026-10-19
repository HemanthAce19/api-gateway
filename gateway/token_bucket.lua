-- Atomic token bucket. Runs inside Redis, so concurrent callers cannot race.
-- KEYS[1] = bucket key
-- ARGV[1] = capacity (max tokens), ARGV[2] = refill rate (tokens per second), ARGV[3] = cost
-- Returns { allowed (1|0), tokens_left (string), retry_after_seconds (string) }
-- Floats are returned as strings because Redis truncates Lua numbers to integers in replies.

local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local cost     = tonumber(ARGV[3])

-- Redis is the only clock, so gateway instances cannot disagree about time.
local t   = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local data   = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts     = tonumber(data[2])

if tokens == nil or ts == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
local retry_after = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after = (cost - tokens) / rate
end

redis.call('HSET', key, 'tokens', tostring(tokens), 'ts', tostring(now))
-- An idle bucket is full again after capacity/rate seconds, so keeping it longer is pointless.
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)

return { allowed, tostring(tokens), tostring(retry_after) }
